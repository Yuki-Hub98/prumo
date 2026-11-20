"""Planilha de tinta (.xlsx) do pavimento: o que comprar por cor e o detalhe por cômodo.

Os números saem de :mod:`interiores_core.tinta` (regra de negócio no core); aqui só se
escreve a planilha. Cores: a variação escolhida em cada cômodo (``variacoes``); sem ela,
"cor padrão". Sai com o aviso de obra se houver medida estimada no pavimento.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from interiores_core import tinta
from interiores_core.carregar import ProjetoCarregado
from interiores_core.modelo import CoresVariacao
from interiores_relatorios import __version__

VERSAO_TINTA = f"interiores-relatorios {__version__} · tinta v1"
AVISO_OBRA = "PRELIMINAR — NÃO USAR PARA OBRA"
NOME_TINTA = {"latex": "Látex (paredes e teto)", "esmalte": "Esmalte (portas e rodapé)"}

NEGRITO = Font(bold=True)
TITULO = Font(bold=True, size=14)
VERMELHO = Font(bold=True, color="C00000", size=12)
CABECALHO = PatternFill("solid", fgColor="DDDDDD")


def cores_das_variacoes(
    carregado: ProjetoCarregado, variacoes: Mapping[str, str] | None
) -> dict[str, CoresVariacao | None]:
    """Cômodo → cores da variação pedida (``base`` ou ausente = cor padrão)."""
    saida: dict[str, CoresVariacao | None] = {}
    for comodo, nome in (variacoes or {}).items():
        if nome == "base":
            continue
        var = carregado.variacoes.get(comodo, {}).get(nome)
        if var is None:
            raise KeyError(f"variação '{nome}' não existe em '{comodo}'")
        saida[comodo] = var.cores
    return saida


def _texto_cor(cor: str | None) -> str:
    return cor.upper() if cor else "cor padrão"


def _texto_latas(latas: Mapping[float, int]) -> str:
    return " + ".join(f"{n} × {f'{t:g}'.replace('.', ',')} L" for t, n in latas.items()) or "—"


def _cabecalho(ws: Worksheet, linha: int, titulos: list[str]) -> None:
    for col, titulo in enumerate(titulos, 1):
        cel = ws.cell(linha, col, titulo)
        cel.font = NEGRITO
        cel.fill = CABECALHO
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _amostra(ws: Worksheet, linha: int, col: int, cor: str | None) -> None:
    if cor:
        ws.cell(linha, col).fill = PatternFill("solid", fgColor=cor.lstrip("#").upper())


def montar_planilha(
    carregado: ProjetoCarregado,
    pavimento: str,
    variacoes: Mapping[str, str] | None = None,
    data: date | None = None,
) -> Workbook:
    """Abas "Comprar" (por tinta e cor, com latas) e "Por cômodo" (cada superfície)."""
    pav = next((p for p in carregado.projeto.pavimentos if p.id == pavimento), None)
    if pav is None:
        raise KeyError(f"pavimento '{pavimento}' não existe no projeto")
    r = tinta.calcular(pav, cores_das_variacoes(carregado, variacoes), carregado.regras)
    data = data or date.today()
    estimadas = carregado.estimadas_pavimento(pavimento)
    nomes = {c.id: c.nome for c in pav.comodos}
    p = r.parametros

    wb = Workbook()
    wb.properties.creator = "interiores"
    wb.properties.created = wb.properties.modified = datetime(data.year, data.month, data.day)

    ws = wb.active
    assert ws is not None
    ws.title = "Comprar"
    ws["A1"] = f"Tinta — {carregado.projeto.projeto} · {pav.nome or pav.id}"
    ws["A1"].font = TITULO
    linha = 2
    if estimadas:
        ws.cell(linha, 1, f"{AVISO_OBRA}: {len(estimadas)} medida(s) estimada(s)").font = VERMELHO
        linha += 1
    escolhidas = ", ".join(f"{nomes.get(c, c)}: {v}" for c, v in sorted((variacoes or {}).items()))
    info = [
        ("Variações", escolhidas or "cores padrão"),
        (
            "Látex",
            f"{p.demaos_latex} demãos, rende {p.rendimento_latex:g} m²/L por demão",
        ),
        (
            "Esmalte",
            f"{p.demaos_esmalte} demãos, rende {p.rendimento_esmalte:g} m²/L por demão",
        ),
        ("Perda", f"{p.perda:.0%} (rolo, bandeja, retoque)"),
        ("Data", data.isoformat()),
        ("Hash do JSON", carregado.hash_curto),
        ("Gerador", VERSAO_TINTA),
    ]
    for rotulo, valor in info:
        ws.cell(linha, 1, rotulo).font = NEGRITO
        ws.cell(linha, 2, valor)
        linha += 1
    ws.cell(
        linha,
        1,
        "Rendimento é estimativa de rótulo: confira a lata e ajuste em [tinta] do regras.toml.",
    )
    linha += 2
    _cabecalho(ws, linha, ["Tinta", "Cor", "Amostra", "Área (m²)", "Litros", "Latas"])
    for g in r.grupos:
        linha += 1
        for col, valor in enumerate(
            [
                NOME_TINTA[g.tinta],
                _texto_cor(g.cor),
                "",
                g.area_m2,
                g.litros,
                _texto_latas(g.latas),
            ],
            1,
        ):
            ws.cell(linha, col, valor)
        _amostra(ws, linha, 3, g.cor)
    for col, largura in enumerate([28, 16, 10, 12, 10, 30], 1):
        ws.column_dimensions[get_column_letter(col)].width = largura
    ws.column_dimensions["B"].width = max(ws.column_dimensions["B"].width, 34)

    ws = wb.create_sheet("Por cômodo")
    _cabecalho(ws, 1, ["Cômodo", "Superfície", "Tinta", "Cor", "Amostra", "Área (m²)", "Litros"])
    for i, (s, litros) in enumerate(zip(r.superficies, r.litros_por_superficie, strict=True), 2):
        valores = [nomes.get(s.comodo, s.comodo), s.nome, s.tinta, _texto_cor(s.cor), "",
                   round(s.area_m2, 2), litros]  # fmt: skip
        for col, valor in enumerate(valores, 1):
            ws.cell(i, col, valor)
        _amostra(ws, i, 5, s.cor)
    for col, largura in enumerate([20, 32, 10, 14, 10, 12, 10], 1):
        ws.column_dimensions[get_column_letter(col)].width = largura
    return wb


def gerar_tinta(
    carregado: ProjetoCarregado,
    saida: Path,
    pavimento: str,
    variacoes: Mapping[str, str] | None = None,
    forcar: bool = False,
    data: date | None = None,
) -> tuple[Path, bool]:
    """Grava ``out/<projeto>/<pavimento>/_geral/tinta.xlsx``; devolve (caminho, gerou?).

    Pula se o hash da entrada, as variações e o gerador não mudaram.
    """
    pasta = saida / carregado.projeto.projeto / pavimento / "_geral"
    xlsx, meta = pasta / "tinta.xlsx", pasta / "tinta.json"
    escolha = json.dumps(dict(sorted((variacoes or {}).items())), ensure_ascii=False)
    chave = hashlib.sha256(
        f"{carregado.hash_entrada}\0{VERSAO_TINTA}\0{pavimento}\0{escolha}".encode()
    ).hexdigest()
    if (
        not forcar
        and xlsx.exists()
        and meta.exists()
        and json.loads(meta.read_text(encoding="utf-8")).get("chave") == chave
    ):
        return xlsx, False
    wb = montar_planilha(carregado, pavimento, variacoes, data)
    pasta.mkdir(parents=True, exist_ok=True)
    wb.save(xlsx)
    meta.write_text(
        json.dumps({"chave": chave, "gerador": VERSAO_TINTA}, indent=2) + "\n", encoding="utf-8"
    )
    return xlsx, True
