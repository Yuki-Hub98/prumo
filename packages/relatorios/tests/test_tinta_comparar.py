"""Planilha de tinta e comparação lado a lado das variações."""

from datetime import date
from pathlib import Path

import pytest
from openpyxl import load_workbook
from PIL import Image

from interiores_core.carregar import carregar
from interiores_core.modelo import Variacao
from interiores_relatorios.comparar import colunas_para, gerar_comparacao, montar
from interiores_relatorios.tinta import AVISO_OBRA, gerar_tinta

DADOS = Path(__file__).resolve().parents[2] / "core" / "tests" / "dados" / "casa"
DIA = date(2026, 11, 20)


def _com_variacao():  # type: ignore[no-untyped-def]
    c = carregar(DADOS)
    c.variacoes.setdefault("quarto", {})["escura"] = Variacao.model_validate(
        {"schema_version": 1, "comodo": "quarto", "nome": "Escura",
         "cores": {"parede": "#7a8b94", "paredes": {"p2": "#c46b4f"}}}
    )  # fmt: skip
    return c


def test_planilha_de_tinta(tmp_path: Path) -> None:
    c = _com_variacao()
    xlsx, gerou = gerar_tinta(c, tmp_path, "terreo", {"quarto": "escura"}, data=DIA)
    assert gerou and xlsx == tmp_path / "casa" / "terreo" / "_geral" / "tinta.xlsx"
    wb = load_workbook(xlsx)
    assert wb.sheetnames == ["Comprar", "Por cômodo"]
    comprar = [[v for v in r if v is not None] for r in wb["Comprar"].iter_rows(values_only=True)]
    assert comprar[1][0].startswith(AVISO_OBRA)  # medidas estimadas no exemplo
    cores = {r[1] for r in comprar if r and str(r[0]).startswith(("Látex", "Esmalte"))}
    assert {"#7A8B94", "#C46B4F", "cor padrão"} <= cores
    detalhe = [r for r in wb["Por cômodo"].iter_rows(values_only=True)][1:]
    assert any(r[1] == "Parede p2 (destaque)" and r[3] == "#C46B4F" for r in detalhe)
    # mesma entrada: não refaz; outra escolha de variação: refaz
    assert not gerar_tinta(c, tmp_path, "terreo", {"quarto": "escura"}, data=DIA)[1]
    assert gerar_tinta(c, tmp_path, "terreo", {}, data=DIA)[1]
    with pytest.raises(KeyError, match="nao-existe"):
        gerar_tinta(c, tmp_path, "terreo", {"quarto": "nao-existe"}, forcar=True)


def test_montar_grade() -> None:
    assert [colunas_para(n) for n in (1, 2, 3, 4, 5, 6)] == [1, 2, 2, 2, 3, 3]
    quadros = [(f"v{i}", Image.new("RGB", (1600, 1000), (i * 40, 80, 120))) for i in range(3)]
    img = montar(quadros, "titulo", "rodape")
    assert img.width == 16 + 2 * (800 + 16)
    assert img.height > 2 * 500  # duas linhas de quadros reduzidos para 800 × 500
    with pytest.raises(ValueError, match="nada"):
        montar([], "x")


def test_comparacao_das_variacoes(tmp_path: Path) -> None:
    c = _com_variacao()
    pasta = tmp_path / "casa" / "terreo" / "quarto"
    for var, sub, cor in (("base", "", (200, 190, 180)), ("escura", "rascunho", (60, 70, 80))):
        destino = pasta / var / sub
        destino.mkdir(parents=True)
        Image.new("RGB", (1600, 1000), cor).save(destino / "render-perspectiva.png")
    png, faltando = gerar_comparacao(c, tmp_path, "quarto", ["base", "escura", "clara"], data=DIA)
    assert png == pasta / "_comparacao" / "comparacao-perspectiva.png"
    assert faltando == ["clara"]
    with Image.open(png) as img:
        assert img.width == 16 + 2 * (800 + 16)
        # cada quadro com a cor da sua variação, na ordem pedida
        assert img.getpixel((16 + 400, 44 + 16 + 44 + 250)) == (200, 190, 180)
        assert img.getpixel((16 + 816 + 400, 44 + 16 + 44 + 250)) == (60, 70, 80)
    with pytest.raises(ValueError, match="duas variações"):
        gerar_comparacao(c, tmp_path, "quarto", ["base", "clara"])
