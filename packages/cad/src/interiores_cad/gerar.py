"""Gera as plantas em ``out/`` com cache por hash (CLAUDE.md §2.3 e §5.5).

Cada saída grava um ``<nome>.json`` com o hash da entrada e a versão do gerador.
Se os dois não mudaram e os arquivos existem, a geração é pulada.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

from interiores_cad.pdf import salvar_pdf
from interiores_cad.planta import VERSAO_GERADOR, desenhar_planta
from interiores_core.carregar import ProjetoCarregado

VARIACAO_BASE = "base"
"""Variação usada enquanto o cômodo não tiver arquivos em ``variacoes/``."""
PASTA_GERAL = "_geral"


class Situacao(StrEnum):
    GERADO = "gerado"
    INALTERADO = "inalterado"


@dataclass(frozen=True)
class Resultado:
    situacao: Situacao
    arquivos: tuple[Path, ...]
    preliminar: bool
    escala: int
    folha: str


def pasta_saida(
    saida: Path, projeto: str, pavimento: str, comodo: str | None, variacao: str = VARIACAO_BASE
) -> Path:
    """``out/<projeto>/<pavimento>/<comodo>/<variacao>/`` ou ``.../<pavimento>/_geral/``."""
    base = saida / projeto / pavimento
    return base / PASTA_GERAL if comodo is None else base / comodo / variacao


def chave(hash_entrada: str) -> str:
    """Hash da entrada combinado com a versão do gerador."""
    return hashlib.sha256(f"{hash_entrada}\0{VERSAO_GERADOR}".encode()).hexdigest()


def gerar_planta(
    carregado: ProjetoCarregado,
    saida: Path,
    pavimento: str,
    comodo: str | None = None,
    variacao: str = VARIACAO_BASE,
    forcar: bool = False,
    data: date | None = None,
) -> Resultado:
    """Grava ``planta.dxf``, ``planta.pdf`` e ``planta.json`` na pasta do escopo."""
    pasta = pasta_saida(saida, carregado.projeto.projeto, pavimento, comodo, variacao)
    dxf, pdf, meta = pasta / "planta.dxf", pasta / "planta.pdf", pasta / "planta.json"
    arquivos = (dxf, pdf, meta)
    minha_chave = chave(carregado.hash_entrada)

    if not forcar and all(a.exists() for a in arquivos):
        anterior = json.loads(meta.read_text(encoding="utf-8"))
        if anterior.get("chave") == minha_chave:
            return Resultado(
                Situacao.INALTERADO,
                arquivos,
                anterior["preliminar"],
                anterior["escala"],
                anterior["folha"],
            )

    desenho = desenhar_planta(carregado, pavimento, comodo, data)
    pasta.mkdir(parents=True, exist_ok=True)
    desenho.doc.saveas(dxf)
    salvar_pdf(desenho, pdf)
    meta.write_text(
        json.dumps(
            {
                "chave": minha_chave,
                "hash_entrada": carregado.hash_entrada,
                "gerador": VERSAO_GERADOR,
                "escopo": {"pavimento": pavimento, "comodo": comodo, "variacao": variacao},
                "escala": desenho.folha.escala,
                "folha": desenho.folha.formato.nome,
                "preliminar": desenho.preliminar,
                "estimadas": [c for c, _ in desenho.estimadas],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return Resultado(
        Situacao.GERADO,
        arquivos,
        desenho.preliminar,
        desenho.folha.escala,
        desenho.folha.formato.nome,
    )
