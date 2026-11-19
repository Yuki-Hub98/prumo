"""Sincronização entre o banco (fonte da verdade) e ``projetos/<p>/`` (exportação).

- :func:`exportar` grava o conteúdo atual do banco nos arquivos.
- :func:`importar` traz para o banco uma edição feita direto nos arquivos (CLI,
  Claude, editor de texto).

Nenhum dos dois sobrescreve mudança do outro lado em silêncio: o banco guarda a
versão e o hash dos arquivos da última sincronização. Se os dois lados mudaram
desde então, levanta :class:`ConflitoDeSincronizacaoError` (use ``forcar`` para
escolher um lado).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from interiores_banco import repositorio
from interiores_banco import tabelas as t
from interiores_banco.mapear import Conteudo
from interiores_core.carregar import carregar


class ConflitoDeSincronizacaoError(RuntimeError):
    """Banco e arquivos mudaram desde a última sincronização."""


@dataclass(frozen=True)
class Sincronizado:
    codigo: str
    versao: int
    mudou: bool
    """Se algo foi gravado (no banco, ao importar; nos arquivos, ao exportar)."""


def _json(caminho: Path, dados: Any) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _hash_arquivos(pasta: Path) -> str | None:
    return carregar(pasta).hash_entrada if (pasta / "projeto.json").is_file() else None


def _linha(sessao: Session, codigo: str) -> t.Projeto | None:
    return sessao.scalars(select(t.Projeto).where(t.Projeto.codigo == codigo)).first()


def escrever(conteudo: Conteudo, pasta: Path) -> None:
    """Escreve o conteúdo em ``pasta`` (projeto.json, comodos/, variacoes/, regras.toml).

    Remove ``comodos/*.json`` e ``variacoes/*/*.json`` que não existem mais no
    conteúdo; ``referencias/`` e outros arquivos não são tocados.
    """
    d = conteudo.como_dict()
    _json(pasta / "projeto.json", d["projeto"])
    for nome, dados in d["comodos"].items():
        _json(pasta / "comodos" / f"{nome}.json", dados)
    for arq in (pasta / "comodos").glob("*.json"):
        if arq.stem not in d["comodos"]:
            arq.unlink()
    for comodo, vs in d["variacoes"].items():
        for nome, dados in vs.items():
            _json(pasta / "variacoes" / comodo / f"{nome}.json", dados)
    for arq in (pasta / "variacoes").glob("*/*.json"):
        if arq.stem not in d["variacoes"].get(arq.parent.name, {}):
            arq.unlink()
    regras = pasta / "regras.toml"
    if conteudo.regras_toml is None:
        regras.unlink(missing_ok=True)
    else:
        regras.write_text(conteudo.regras_toml, encoding="utf-8")


def exportar(sessao: Session, codigo: str, pasta: Path | str, forcar: bool = False) -> Sincronizado:
    """Grava ``projetos/<codigo>/`` a partir do banco."""
    pasta = Path(pasta)
    conteudo, versao = repositorio.ler(sessao, codigo)
    linha = _linha(sessao, codigo)
    assert linha is not None
    atual = _hash_arquivos(pasta)
    if atual is not None and atual == linha.hash_exportado and linha.versao_exportada == versao:
        return Sincronizado(codigo, versao, False)
    if atual is not None and atual != linha.hash_exportado and not forcar:
        raise ConflitoDeSincronizacaoError(
            f"{pasta} foi editado fora do banco desde a última sincronização "
            "(importe antes, ou use forcar para sobrescrever os arquivos)"
        )
    escrever(conteudo, pasta)
    novo = _hash_arquivos(pasta)
    assert novo is not None
    repositorio.marcar_exportado(sessao, codigo, versao, novo)
    return Sincronizado(codigo, versao, True)


def importar(sessao: Session, pasta: Path | str, forcar: bool = False) -> Sincronizado:
    """Traz ``projetos/<p>/`` para o banco como nova versão (ou cria o projeto)."""
    pasta = Path(pasta)
    carregado = carregar(pasta)
    conteudo = Conteudo.de_carregado(carregado)
    codigo = conteudo.projeto.projeto
    linha = _linha(sessao, codigo)
    if linha is not None:
        if carregado.hash_entrada == linha.hash_exportado:
            return Sincronizado(codigo, linha.versao, False)
        mudou_no_banco = (
            linha.versao_exportada is not None and linha.versao != linha.versao_exportada
        )
        if mudou_no_banco and not forcar:
            raise ConflitoDeSincronizacaoError(
                f"'{codigo}' mudou no banco (versão {linha.versao}) e nos arquivos desde "
                f"a última sincronização (versão {linha.versao_exportada}); use forcar "
                "para ficar com os arquivos"
            )
    gravado = repositorio.gravar(sessao, conteudo, fonte="importacao", operacao="importar")
    repositorio.marcar_exportado(sessao, codigo, gravado.versao, carregado.hash_entrada)
    return Sincronizado(codigo, gravado.versao, bool(gravado.alteracoes))
