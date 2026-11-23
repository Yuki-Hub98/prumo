"""Lista de corte do móvel planejado (.xlsx): peças, ferragens e chapas."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from interiores_core import bancada
from interiores_core.carregar import ProjetoCarregado
from interiores_core.medidas import medidas_estimadas
from interiores_core.planejado import calcular
from interiores_core.regras import VERSAO_REGRAS, checar
from interiores_relatorios import __version__

VERSAO_LISTA = f"interiores-relatorios {__version__} · lista de corte v1 · {VERSAO_REGRAS}"
AVISO_OBRA = "PRELIMINAR — NÃO USAR PARA OBRA"
"""Mesmo aviso dos desenhos: há medida estimada no móvel."""

NEGRITO = Font(bold=True)
TITULO = Font(bold=True, size=14)
VERMELHO = Font(bold=True, color="C00000", size=12)
CABECALHO = PatternFill("solid", fgColor="DDDDDD")
LEGENDA_FITA = "Fita: 1C = um lado comprido; 2C2L = os quatro lados; C = comprimento, L = largura"


def _cabecalho(ws: Worksheet, linha: int, titulos: list[str]) -> None:
    for col, titulo in enumerate(titulos, 1):
        cel = ws.cell(linha, col, titulo)
        cel.font = NEGRITO
        cel.fill = CABECALHO
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _larguras(ws: Worksheet, larguras: list[int]) -> None:
    for col, largura in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(col)].width = largura


def montar_planilha(
    carregado: ProjetoCarregado, comodo: str, movel_id: str, data: date | None = None
) -> Workbook:
    """Planilha com as abas Resumo, Peças e Ferragens.

    Levanta ``KeyError`` se o móvel não existir e ``ValueError`` se não tiver
    construção (ou ``ConstrucaoInvalidaError`` se ela não couber).
    """
    dados = carregado.dados_comodos.get(comodo)
    movel = next((m for m in dados.moveis if m.id == movel_id), None) if dados else None
    if movel is None:
        raise KeyError(f"móvel '{movel_id}' não existe no cômodo '{comodo}'")
    # ValueError se não for planejado nem bancada
    calc = bancada.calcular(movel) if movel.bancada is not None else calcular(movel)
    data = data or date.today()
    estimadas = medidas_estimadas(movel, f"comodos/{comodo}.moveis[{movel.id}]")
    problemas = [
        p
        for p in checar(carregado.projeto, carregado.dados_comodos, carregado.regras, comodo)
        if p.elemento == movel.id
    ]

    wb = Workbook()
    wb.properties.creator = "interiores"
    wb.properties.created = wb.properties.modified = datetime(data.year, data.month, data.day)

    # ------------------------------------------------------------ resumo
    ws = wb.active
    assert ws is not None
    ws.title = "Resumo"
    ws["A1"] = f"Lista de corte — {movel.nome or movel.id}"
    ws["A1"].font = TITULO
    linha = 2
    if estimadas:
        ws.cell(linha, 1, f"{AVISO_OBRA}: {len(estimadas)} medida(s) estimada(s)").font = VERMELHO
        linha += 1
    info = [
        ("Projeto", carregado.projeto.projeto),
        ("Cômodo", comodo),
        ("Móvel", f"{movel.id} ({movel.tipo})"),
        (
            "Medidas externas (mm)",
            f"{movel.largura.valor} × {movel.profundidade.valor} × {movel.altura.valor}",
        ),
        ("Portas", movel.portas or "sem portas"),
        ("Data", data.isoformat()),
        ("Hash do JSON", carregado.hash_curto),
        ("Gerador", VERSAO_LISTA),
    ]
    for rotulo, valor in info:
        ws.cell(linha, 1, rotulo).font = NEGRITO
        ws.cell(linha, 2, valor)
        linha += 1

    linha += 1
    ws.cell(linha, 1, "Chapas (estimativa com 15% de perda, sem plano de corte)").font = NEGRITO
    linha += 1
    _cabecalho(ws, linha, ["Material", "Espessura (mm)", "Área (m²)", "Chapas", "Fita (m)"])
    for ch in calc.chapas:
        linha += 1
        linha_chapa: list[object] = [
            ch.material,
            ch.espessura,
            ch.area_m2,
            ch.chapas,
            ch.fita_metros,
        ]
        for col, conteudo in enumerate(linha_chapa, 1):
            ws.cell(linha, col, conteudo)
    linha += 2
    ws.cell(linha, 1, "Checagens").font = NEGRITO
    for p in problemas or []:
        linha += 1
        ws.cell(linha, 1, f"[{p.severidade}] {p.codigo}")
        ws.cell(linha, 2, p.mensagem)
    if not problemas:
        ws.cell(linha + 1, 1, "Nenhum problema nas checagens.")
    if estimadas:
        linha += 2
        ws.cell(linha, 1, "Medidas estimadas").font = NEGRITO
        for caminho, m in estimadas:
            linha += 1
            ws.cell(linha, 1, caminho)
            ws.cell(linha, 2, f"{m.valor} mm" + (f" ({m.obs})" if m.obs else ""))
    _larguras(ws, [42, 70, 12, 10, 10])

    # ------------------------------------------------------------ peças
    ws = wb.create_sheet("Peças")
    titulos = [
        "Nº",
        "Peça",
        "Material",
        "Esp. (mm)",
        "Comp. (mm)",
        "Larg. (mm)",
        "Qtd",
        "Fita",
        "Fita (m)",
        "Área (m²)",
        "Obs.",
    ]
    _cabecalho(ws, 1, titulos)
    for i, peca in enumerate(calc.pecas, 1):
        valores: list[object] = [
            i,
            peca.nome,
            peca.material,
            peca.espessura,
            round(peca.comprimento, 1),
            round(peca.largura, 1),
            peca.quantidade,
            peca.fita,
            round(peca.fita_metros, 2),
            round(peca.area_m2, 3),
            peca.obs,
        ]
        for col, conteudo in enumerate(valores, 1):
            ws.cell(i + 1, col, conteudo)
    total = len(calc.pecas) + 2
    ws.cell(total, 2, "Total").font = NEGRITO
    ws.cell(total, 7, sum(x.quantidade for x in calc.pecas)).font = NEGRITO
    ws.cell(total, 9, round(sum(x.fita_metros for x in calc.pecas), 2)).font = NEGRITO
    ws.cell(total, 10, round(sum(x.area_m2 for x in calc.pecas), 3)).font = NEGRITO
    ws.cell(total + 2, 1, LEGENDA_FITA)
    ws.freeze_panes = "A2"
    _larguras(ws, [5, 32, 16, 9, 11, 11, 6, 7, 9, 10, 30])

    # ------------------------------------------------------------ ferragens
    ws = wb.create_sheet("Ferragens")
    _cabecalho(ws, 1, ["Item", "Qtd", "Obs."])
    for i, f in enumerate(calc.ferragens, 2):
        ws.cell(i, 1, f.nome)
        ws.cell(i, 2, f.quantidade)
        ws.cell(i, 3, f.obs)
    ws.freeze_panes = "A2"
    _larguras(ws, [48, 8, 36])
    return wb


def gerar_lista(
    carregado: ProjetoCarregado,
    pasta: Path,
    comodo: str,
    movel_id: str,
    forcar: bool = False,
    data: date | None = None,
) -> tuple[Path, bool]:
    """Grava ``planejado-<movel>-corte.xlsx`` em ``pasta``; devolve (caminho, gerou?).

    Pula a geração se o hash da entrada e a versão do gerador não mudaram.
    """
    xlsx = pasta / f"planejado-{movel_id}-corte.xlsx"
    meta = pasta / f"planejado-{movel_id}-corte.json"
    chave = hashlib.sha256(
        f"{carregado.hash_entrada}\0{VERSAO_LISTA}\0{movel_id}".encode()
    ).hexdigest()
    atual = (
        not forcar
        and xlsx.exists()
        and meta.exists()
        and json.loads(meta.read_text(encoding="utf-8")).get("chave") == chave
    )
    if atual:
        return xlsx, False
    wb = montar_planilha(carregado, comodo, movel_id, data)
    pasta.mkdir(parents=True, exist_ok=True)
    wb.save(xlsx)
    meta.write_text(
        json.dumps({"chave": chave, "gerador": VERSAO_LISTA}, indent=2) + "\n", encoding="utf-8"
    )
    return xlsx, True
