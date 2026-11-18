"""Desenho técnico do móvel planejado."""

import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from ezdxf import bbox

from interiores_cad.estilo import AVISO_OBRA, NOMES_CAMADAS
from interiores_cad.gerar import Situacao, gerar_movel
from interiores_cad.movel import desenhar_movel
from interiores_core import planejado
from interiores_core.carregar import carregar
from interiores_core.modelo import Movel

DADOS = Path(__file__).parent / "dados" / "casa"
DATA = date(2026, 11, 17)


@pytest.fixture
def casa(tmp_path: Path) -> Path:
    """Cópia com o guarda-roupa (1800 × 550 × 2300) planejado pela sugestão padrão."""
    destino = tmp_path / "casa"
    shutil.copytree(DADOS, destino)
    arq = destino / "comodos" / "quarto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    gr = d["moveis"][1]
    gr["portas"] = "correr"
    gr["construcao"] = planejado.construcao_sugerida(Movel.model_validate(gr))
    arq.write_text(json.dumps(d), encoding="utf-8")
    return destino


def test_desenho_do_movel(casa: Path) -> None:
    desenho = desenhar_movel(carregar(casa), "quarto", "guarda-roupa", DATA)
    doc = desenho.doc
    msp = doc.modelspace()
    assert {e.dxf.layer for e in msp} <= NOMES_CAMADAS
    textos = [e.dxf.text for e in msp.query("TEXT")]
    assert "Móvel planejado — Guarda-roupa" in textos
    assert "gaveta 180" in textos and "nicho 400" in textos and "cabideiro 1368" in textos
    painel = " ".join(textos)
    assert "guarda-roupa: largura" in painel and "vão 1 espaço 4 altura" in painel
    assert desenho.preliminar and AVISO_OBRA in textos
    cotas = {round(d.get_measurement()) for d in msp.query("DIMENSION")}
    assert {1800, 2300, 550, 873, 1368, 180, 400, 100} <= cotas
    # vista frontal em escala real: a caixa ocupa 0..1800 × 0..2300
    frente = bbox.extents(
        e
        for e in msp.query('LWPOLYLINE[layer=="MOVEL"]')
        if e.dxf.linetype != "TRACEJADO" and max(p[0] for p in e.get_points("xy")) <= 1800
    )
    assert (round(frente.extmin.x), round(frente.extmin.y)) == (0, 0)
    assert (round(frente.extmax.x), round(frente.extmax.y)) == (1800, 2300)
    assert msp.query('LWPOLYLINE[linetype=="TRACEJADO"]')  # portas tracejadas


def test_erros_do_desenho(casa: Path) -> None:
    c = carregar(casa)
    with pytest.raises(KeyError):
        desenhar_movel(c, "quarto", "nada")
    with pytest.raises(ValueError, match="não tem construção"):
        desenhar_movel(c, "quarto", "cama")


def test_gerar_movel_com_cache(casa: Path, tmp_path: Path) -> None:
    c = carregar(casa)
    r = gerar_movel(c, tmp_path / "out", "quarto", "guarda-roupa", data=DATA)
    assert r.situacao is Situacao.GERADO and r.escala in (20, 25, 50)
    assert [a.name for a in r.arquivos] == [
        "planejado-guarda-roupa.dxf",
        "planejado-guarda-roupa.pdf",
        "planejado-guarda-roupa.json",
    ]
    assert r.arquivos[0].parent == tmp_path / "out/casa/terreo/quarto/base"
    r2 = gerar_movel(c, tmp_path / "out", "quarto", "guarda-roupa", data=DATA)
    assert r2.situacao is Situacao.INALTERADO
    with pytest.raises(KeyError):
        gerar_movel(c, tmp_path / "out", "cozinha", "x")
