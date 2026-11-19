"""Geometria para a tela."""

from apoio import CASA

from interiores_core.carregar import carregar
from interiores_core.tela import pavimento_para_tela


def test_casa_na_tela() -> None:
    c = carregar(CASA)
    tela = pavimento_para_tela(c.projeto.pavimentos[0], c.dados_comodos)
    assert {p.id for p in tela.paredes} == {f"p{i}" for i in range(1, 9)}
    p1 = next(p for p in tela.paredes if p.id == "p1")
    xs, ys = [x for x, _ in p1.corpo], [y for _, y in p1.corpo]
    assert (min(xs), max(xs), min(ys), max(ys)) == (-75, 3575, -75, 75)
    porta = next(a for a in tela.aberturas if a.id == "porta-quarto")
    assert porta.giro is not None and len(porta.giro) > 3
    janela = next(a for a in tela.aberturas if a.id == "janela-quarto")
    assert janela.giro is None and len(janela.vao) == 4
    quarto = next(x for x in tela.comodos if x.id == "quarto")
    assert quarto.area_m2 == 11.04 and quarto.poligono and quarto.centro
    cama = next(m for m in tela.moveis if m.id == "cama")
    assert cama.comodo == "quarto" and len(cama.cantos) == 4 and not cama.elevado
    assert tela.limites == ((-75, -75), (3575, 4825))
    assert {i.tipo for i in tela.instalacoes} >= {"tomada", "ponto_luz", "esgoto"}


def test_comodo_que_nao_fecha_e_pavimento_vazio() -> None:
    c = carregar(CASA)
    pav = c.projeto.pavimentos[0].model_copy(update={"paredes": [], "aberturas": []})
    tela = pavimento_para_tela(pav)
    assert tela.limites is None and tela.paredes == [] and tela.moveis == []
    assert all(x.poligono is None and x.centro is None for x in tela.comodos)
