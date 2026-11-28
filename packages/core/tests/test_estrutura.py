"""Estrutura do pavimento: pilares, vigas e lajes (aba Estruturas)."""

from collections.abc import Callable
from typing import Any

import pytest
from apoio import pav

from interiores_core import edicao, geometria
from interiores_core.edicao import EdicaoInvalidaError
from interiores_core.modelo import Laje, Pilar, Projeto, Viga
from interiores_core.validacao import validar


def M(v: int, origem: str = "estimada") -> dict[str, Any]:  # noqa: N802 - atalho de Medida
    return {"valor": v, "origem": origem}


PILAR = {
    "id": "p-1",
    "tipo": "pilar",
    "centro": [100, 100],
    "largura": M(200),
    "profundidade": M(200),
}
VIGA = {
    "id": "v-1",
    "tipo": "viga",
    "inicio": [0, 0],
    "fim": [3000, 0],
    "largura": M(150),
    "altura": M(300),
}
LAJE = {"id": "laje-terreo", "tipo": "laje", "espessura": M(120)}


def _codigos(p: Projeto, tipo: str | None = None) -> set[str]:
    return {x.codigo for x in validar(p) if tipo is None or x.severidade == tipo}


def test_adicionar_alterar_remover(montar: Callable[[], Projeto]) -> None:
    p = montar()
    for e in (PILAR, VIGA, LAJE):
        p = edicao.adicionar_estrutura(p, "terreo", e).projeto
    tipos = [type(e) for e in p.pavimentos[0].estrutura]
    assert tipos == [Pilar, Viga, Laje]
    laje = p.pavimentos[0].estrutura[2]
    assert isinstance(laje, Laje) and laje.sistema == "pre_moldada" and laje.contorno is None

    r = edicao.alterar_estrutura(p, "terreo", "p-1", {"largura": M(250, "trena")})
    pilar = r.projeto.pavimentos[0].estrutura[0]
    assert isinstance(pilar, Pilar) and pilar.largura.valor == 250
    assert "antes: 200 mm (estimada)" in (pilar.largura.obs or "")  # a anterior fica na obs

    r = edicao.alterar_estrutura(
        p,
        "terreo",
        "laje-terreo",
        {"furos": [[[500, 500], [1500, 500], [1500, 3000], [500, 3000]]], "sistema": "macica"},
    )
    laje = r.projeto.pavimentos[0].estrutura[2]
    assert isinstance(laje, Laje) and laje.sistema == "macica" and len(laje.furos) == 1

    sem = edicao.remover_estrutura(r.projeto, "terreo", "v-1").projeto
    assert [e.id for e in sem.pavimentos[0].estrutura] == ["p-1", "laje-terreo"]


def test_erros_de_edicao(montar: Callable[[], Projeto]) -> None:
    p = edicao.adicionar_estrutura(montar(), "terreo", PILAR).projeto
    with pytest.raises(EdicaoInvalidaError):
        edicao.adicionar_estrutura(p, "terreo", PILAR)  # id repetido
    with pytest.raises(EdicaoInvalidaError):
        edicao.alterar_estrutura(p, "terreo", "p-1", {"espessura": M(100)})  # campo de laje
    with pytest.raises(KeyError):
        edicao.remover_estrutura(p, "terreo", "nao-existe")


def test_laje_sem_contorno_cobre_o_pavimento_por_fora(montar: Callable[[], Projeto]) -> None:
    p = edicao.adicionar_estrutura(montar(), "terreo", LAJE).projeto
    pv = p.pavimentos[0]
    laje = pv.estrutura[0]
    contorno = geometria.contorno_pavimento(pv)
    assert contorno is not None and not contorno.interiors  # sem buracos
    # cobre todas as paredes (por fora) e todos os cômodos
    for parede in pv.paredes:
        assert contorno.buffer(1).contains(geometria.corpo(parede))
    g = geometria.poligono_estrutura(pv, laje)
    assert g is not None and g.area == pytest.approx(contorno.area)


def test_furo_e_projecao_de_pilar_e_viga(montar: Callable[[], Projeto]) -> None:
    furo = [[500, 500], [1500, 500], [1500, 3000], [500, 3000]]
    p = montar()
    for e in (PILAR, VIGA, {**LAJE, "furos": [furo]}):
        p = edicao.adicionar_estrutura(p, "terreo", e).projeto
    pv = p.pavimentos[0]
    pilar, viga, laje = pv.estrutura
    assert geometria.poligono_estrutura(pv, pilar).area == 200 * 200  # type: ignore[union-attr]
    assert geometria.poligono_estrutura(pv, viga).area == pytest.approx(3000 * 150)  # type: ignore[union-attr]
    cheia = geometria.contorno_pavimento(pv)
    assert cheia is not None
    assert geometria.poligono_estrutura(pv, laje).area == pytest.approx(cheia.area - 1000 * 2500)  # type: ignore[union-attr]
    # o recorte do quarto leva o que toca nele (a laje cobre tudo)
    recorte = geometria.recorte_do_comodo(pv, "quarto")
    assert {e.id for e in recorte.estrutura} >= {"laje-terreo"}


def test_validacao(casa_dict: dict[str, Any], montar: Callable[[], Projeto]) -> None:
    assert "sem_estrutura" in _codigos(montar())
    pav(casa_dict)["estrutura"] = [
        {**LAJE, "contorno": [[0, 0], [1000, 1000], [1000, 0], [0, 1000]]},  # gravata: se cruza
        {**LAJE, "id": "laje-2", "furos": [[[-5000, -5000], [-4000, -5000], [-4000, -4000]]]},
        {**LAJE, "id": "laje-3"},
        {**VIGA, "fim": [0, 0]},
    ]
    codigos = _codigos(montar())
    assert {
        "laje_invalida",
        "furo_fora_da_laje",
        "lajes_sobrepostas",
        "viga_sem_comprimento",
    } <= codigos
    assert "sem_estrutura" not in codigos


def test_laje_precisa_de_contorno_com_3_pontos(
    casa_dict: dict[str, Any], montar: Callable[[], Projeto]
) -> None:
    pav(casa_dict)["estrutura"] = [{**LAJE, "contorno": [[0, 0], [10, 0]]}]
    with pytest.raises(ValueError):
        montar()
