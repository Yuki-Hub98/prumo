"""Cotas da planta para a tela."""

from collections.abc import Callable
from typing import Any

from shapely import Point

from interiores_core import cotas, geometria
from interiores_core.modelo import Projeto
from interiores_core.tela import pavimento_para_tela


def test_cotas_do_comodo_por_dentro(montar: Callable[[], Projeto]) -> None:
    pav = montar().pavimentos[0]
    quarto = next(c for c in pav.comodos if c.id == "quarto")
    ks = cotas.cotas_do_comodo(pav, quarto)
    faces = [k for k in ks if k.tipo == "comodo"]
    assert len(faces) >= 4 and all(k.comodo == "quarto" for k in ks)
    # o lado aponta para dentro do cômodo: o meio da cota afastada cai na área útil
    util = geometria.poligono_util(pav, quarto)
    assert util is not None
    for k in faces:
        mx, my = (k.de[0] + k.ate[0]) / 2, (k.de[1] + k.ate[1]) / 2
        assert util.contains(Point(mx + k.lado[0] * 200, my + k.lado[1] * 200))
    # face com abertura: a cadeia soma o total e o total vai para a 2ª fileira
    trechos = [k for k in ks if k.tipo == "trecho"]
    assert trechos
    for f in (k for k in faces if k.fileira == 1):
        da_face = [t for t in trechos if t.lado == f.lado and _na_linha(t, f)]
        assert abs(sum(t.valor for t in da_face) - f.valor) <= len(da_face)


def _na_linha(t: cotas.Cota, f: cotas.Cota) -> bool:
    (x0, y0), (x1, y1) = f.de, f.ate
    return all(abs((x1 - x0) * (p[1] - y0) - (y1 - y0) * (p[0] - x0)) < 1e-3 for p in (t.de, t.ate))


def test_cotas_gerais_e_na_tela(montar: Callable[[], Projeto]) -> None:
    pav = montar().pavimentos[0]
    gerais = cotas.cotas_gerais(pav)
    totais = [k for k in gerais if k.tipo == "geral"]
    assert len(totais) == 2 and all(k.fileira == 1 for k in totais)
    eixos = [k for k in gerais if k.tipo == "eixo" and k.lado == (0.0, -1.0)]
    assert eixos and sum(k.valor for k in eixos) < totais[0].valor  # eixo a eixo < por fora
    tela = pavimento_para_tela(pav)
    assert len(tela.cotas) == len(cotas.cotas_do_pavimento(pav))


def test_origem_da_cota(casa_dict: dict[str, Any], montar: Callable[[], Projeto]) -> None:
    """Qualquer chute faz da cota um chute; tudo medido, medida; senão, quero assim."""
    assert cotas.origem_de() == "projeto"
    pav = montar().pavimentos[0]
    assert "estimada" in {k.origem for k in cotas.cotas_do_pavimento(pav)}

    def trocar(x: Any) -> Any:
        if isinstance(x, dict):
            if "origem" in x and "valor" in x:
                return {**x, "origem": "trena"}
            return {k: trocar(v) for k, v in x.items()}
        if isinstance(x, list):
            return [trocar(v) for v in x]
        return x

    medido = Projeto.model_validate(trocar(casa_dict)).pavimentos[0]
    assert {k.origem for k in cotas.cotas_do_pavimento(medido)} == {"trena"}
    tela = pavimento_para_tela(medido)
    assert {k.origem for k in tela.cotas} == {"trena"}
