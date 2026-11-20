"""Cálculo de tinta: áreas por cômodo e cor, litros e latas."""

import pytest
from apoio import CASA

from interiores_core import geometria, tinta
from interiores_core.carregar import carregar
from interiores_core.modelo import CoresVariacao


@pytest.fixture
def pav():  # type: ignore[no-untyped-def]
    return carregar(CASA).projeto.pavimentos[0]


def test_superficies_do_quarto(pav) -> None:  # type: ignore[no-untyped-def]
    sup = {(s.comodo, s.nome): s for s in tinta.superficies(pav)}
    paredes, teto = sup[("quarto", "Paredes")], sup[("quarto", "Teto")]
    assert (paredes.tinta, teto.tinta, sup[("quarto", "Rodapé")].tinta) == (
        "latex",
        "latex",
        "esmalte",
    )
    quarto = pav.comodo("quarto")
    assert teto.area_m2 == pytest.approx(geometria.area_util_m2(pav, quarto), abs=0.01)
    # perímetro × pé-direito menos janela, porta e faixa de rodapé: menos que o bruto
    util = geometria.poligono_util(pav, quarto)
    pe = pav.pe_direito.valor / 1000
    assert 0.6 * util.length / 1000 * pe < paredes.area_m2 < util.length / 1000 * pe
    portas = [s for s in sup.values() if s.nome.startswith("Porta")]
    assert portas and all(s.tinta == "esmalte" for s in portas)


def test_parede_de_destaque_vira_outra_cor(pav) -> None:  # type: ignore[no-untyped-def]
    sem = {s.nome: s.area_m2 for s in tinta.superficies(pav) if s.comodo == "quarto"}
    cores = CoresVariacao(parede="#eeeeee", paredes={"p2": "#c46b4f"}, teto="#fafafa")
    com = [s for s in tinta.superficies(pav, {"quarto": cores}) if s.comodo == "quarto"]
    paredes = next(s for s in com if s.nome == "Paredes")
    destaque = next(s for s in com if s.nome.startswith("Parede p2"))
    assert (paredes.cor, destaque.cor) == ("#eeeeee", "#c46b4f")
    assert paredes.area_m2 + destaque.area_m2 == pytest.approx(sem["Paredes"])
    assert next(s for s in com if s.nome == "Teto").cor == "#fafafa"


def test_litros_e_latas() -> None:
    p = tinta.Parametros()
    assert tinta.litros(50, "latex", p) == pytest.approx(50 * 2 / 10 * 1.1)
    assert tinta.latas(15.1, p.latas_latex) == {18.0: 1}
    assert tinta.latas(20, p.latas_latex) == {18.0: 1, 3.6: 1}
    assert tinta.latas(0.3, p.latas_latex) == {0.9: 1}
    assert tinta.latas(0, p.latas_latex) == {}
    assert tinta.latas(2.15, p.latas_esmalte) == {0.9: 2, 0.225: 2}


def test_calcular_agrupa_por_tinta_e_cor_e_le_o_regras_toml(pav) -> None:  # type: ignore[no-untyped-def]
    r = tinta.calcular(pav)
    assert {(g.tinta, g.cor) for g in r.grupos} == {("latex", None), ("esmalte", None)}
    latex = next(g for g in r.grupos if g.tinta == "latex")
    assert latex.litros == pytest.approx(
        tinta.litros(latex.area_m2, "latex", r.parametros), abs=0.05
    )
    mais = tinta.calcular(pav, regras={"tinta": {"demaos_latex": 3, "latas_latex": [18, 3.6]}})
    latex3 = next(g for g in mais.grupos if g.tinta == "latex")
    assert latex3.litros == pytest.approx(latex.litros * 1.5, rel=0.01)
    assert mais.parametros.latas_latex == (18.0, 3.6)
