"""Rascunho: testar mudanças à vontade e só depois salvar.

Toda edição feita pela tela entra como **passo de rascunho**: uma versão normal (com
snapshot e histórico), mas acima de ``projeto.rascunho_desde`` (a versão salva onde o
rascunho começou). Enquanto há rascunho:

- **desfazer** volta um passo de verdade: restaura o conteúdo da versão anterior e
  *desce* a versão; o passo desfeito fica guardado acima da atual para o **refazer**,
  até a próxima edição (que o apaga, ver :func:`repositorio.gravar`);
- **salvar** fecha o rascunho: cada passo que ficou vira uma versão comum (a
  exportação para ``projetos/`` fica com quem chama);
- **descartar** volta para a versão salva e apaga os passos.

Fora do rascunho, desfazer/refazer seguem :mod:`interiores_banco.versoes` (gravam versão
nova, nada é apagado).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from interiores_banco import repositorio
from interiores_banco import tabelas as t


class SemRascunhoError(ValueError):
    """Não há rascunho (ou passo) para a operação pedida."""


@dataclass(frozen=True)
class Estado:
    desde: int
    """Versão salva onde o rascunho começou."""
    passos: int
    """Passos ainda valendo (versão atual menos ``desde``)."""
    refazer: bool
    """Há passo desfeito para refazer."""


def _linha(sessao: Session, codigo: str, versao_esperada: int | None) -> t.Projeto:
    linha = repositorio.linha_para_gravar(sessao, codigo)
    if linha is None:
        raise repositorio.ProjetoInexistenteError(f"projeto '{codigo}' não está no banco")
    if versao_esperada is not None and versao_esperada != linha.versao:
        raise repositorio.ConflitoDeVersaoError(codigo, versao_esperada, linha.versao)
    return linha


def _tem_snapshot(sessao: Session, projeto_id: int, versao: int) -> bool:
    return (
        sessao.scalar(
            select(t.Snapshot.id).where(
                t.Snapshot.projeto_id == projeto_id, t.Snapshot.versao == versao
            )
        )
        is not None
    )


def estado(sessao: Session, codigo: str) -> Estado | None:
    """Rascunho aberto (``None`` se não há)."""
    linha = sessao.scalars(select(t.Projeto).where(t.Projeto.codigo == codigo)).first()
    if linha is None:
        raise repositorio.ProjetoInexistenteError(f"projeto '{codigo}' não está no banco")
    if linha.rascunho_desde is None:
        return None
    return Estado(
        desde=linha.rascunho_desde,
        passos=linha.versao - linha.rascunho_desde,
        refazer=_tem_snapshot(sessao, linha.id, linha.versao + 1),
    )


def _ir_para(sessao: Session, linha: t.Projeto, codigo: str, versao: int) -> None:
    conteudo = repositorio.snapshot(sessao, codigo, versao)
    repositorio.substituir(sessao, linha, conteudo)
    linha.versao = versao
    sessao.flush()


def desfazer_passo(sessao: Session, codigo: str, versao_esperada: int) -> int:
    """Volta um passo do rascunho. Devolve a versão nova (uma a menos)."""
    linha = _linha(sessao, codigo, versao_esperada)
    if linha.rascunho_desde is None or linha.versao <= linha.rascunho_desde:
        raise SemRascunhoError("não há passo de rascunho para desfazer")
    _ir_para(sessao, linha, codigo, linha.versao - 1)
    return linha.versao


def refazer_passo(sessao: Session, codigo: str, versao_esperada: int) -> int:
    """Refaz o último passo desfeito do rascunho. Devolve a versão nova."""
    linha = _linha(sessao, codigo, versao_esperada)
    if linha.rascunho_desde is None or not _tem_snapshot(sessao, linha.id, linha.versao + 1):
        raise SemRascunhoError("não há passo de rascunho para refazer")
    _ir_para(sessao, linha, codigo, linha.versao + 1)
    return linha.versao


def salvar(sessao: Session, codigo: str, versao_esperada: int) -> int:
    """Fecha o rascunho: os passos que ficaram viram versões comuns. Devolve a versão."""
    linha = _linha(sessao, codigo, versao_esperada)
    if linha.rascunho_desde is None:
        raise SemRascunhoError("não há rascunho para salvar")
    repositorio.apagar_acima(sessao, linha.id, linha.versao)  # desfeitos: não voltam mais
    linha.rascunho_desde = None
    sessao.flush()
    return linha.versao


def descartar(sessao: Session, codigo: str, versao_esperada: int) -> int:
    """Volta para a versão salva e apaga todos os passos. Devolve a versão salva."""
    linha = _linha(sessao, codigo, versao_esperada)
    if linha.rascunho_desde is None:
        raise SemRascunhoError("não há rascunho para descartar")
    desde = linha.rascunho_desde
    if linha.versao != desde:
        _ir_para(sessao, linha, codigo, desde)
    repositorio.apagar_acima(sessao, linha.id, desde)
    linha.rascunho_desde = None
    sessao.flush()
    return desde
