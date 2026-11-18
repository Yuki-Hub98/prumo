from collections.abc import Callable
from typing import Any

import pytest
from apoio import item, pav

from interiores_core import geometria
from interiores_core.modelo import Projeto


def test_poligono_do_quarto_em_l(montar: Callable[[], Projeto]) -> None:
    p = montar().pavimentos[0]
    quarto = p.comodo("quarto")
    assert quarto is not None
    poligono = geometria.poligono_eixo(p, quarto)
    assert poligono is not None
    assert poligono.area == 3500 * 4750 - 2095 * (4750 - 2635)


def test_area_util_desconta_paredes(montar: Callable[[], Projeto]) -> None:
    p = montar().pavimentos[0]
    banheiro = p.comodo("banheiro")
    assert banheiro is not None
    # medida interna informada: 1,96 x 1,98
    assert geometria.area_util_m2(p, banheiro) == pytest.approx(1.96 * 1.98, abs=0.01)


def test_comodo_nao_fechado(casa_dict: dict[str, Any], montar: Callable[[], Projeto]) -> None:
    item(pav(casa_dict)["comodos"], "banheiro")["paredes"].remove("p4")
    p = montar().pavimentos[0]
    banheiro = p.comodo("banheiro")
    assert banheiro is not None
    assert geometria.poligono_eixo(p, banheiro) is None
    assert geometria.area_util_m2(p, banheiro) is None


def test_lados_da_parede(montar: Callable[[], Projeto]) -> None:
    p = montar().pavimentos[0]
    p1 = p.parede("p1")  # (0,0) → (3500,0): esquerda é +y
    assert p1 is not None
    assert geometria.ponto_ao_lado(p1, "a").y > 0
    assert geometria.ponto_ao_lado(p1, "b").y < 0


def test_recorte_do_comodo(montar: Callable[[], Projeto]) -> None:
    p = montar().pavimentos[0]
    r = geometria.recorte_do_comodo(p, "banheiro")
    assert {x.id for x in r.paredes} == {"p4", "p5", "p7", "p8"}
    assert {x.id for x in r.aberturas} == {"porta-banheiro", "basculante-banheiro"}
    assert "tomada-cama-esq" not in {x.id for x in r.instalacoes}
    assert "ralo-box" in {x.id for x in r.instalacoes}
    with pytest.raises(KeyError):
        geometria.recorte_do_comodo(p, "cozinha")


def test_recorte_inclui_estrutura_e_trechos(
    casa_dict: dict[str, Any], montar: Callable[[], Projeto]
) -> None:
    alt = {"valor": 300, "origem": "estimada"}
    pav(casa_dict)["estrutura"] = [
        {"id": "pl1", "tipo": "pilar", "centro": [3500, 0], "largura": alt, "profundidade": alt},
        {
            "id": "v1",
            "tipo": "viga",
            "inicio": [0, 2635],
            "fim": [2095, 2635],
            "largura": alt,
            "altura": alt,
        },
    ]
    pav(casa_dict)["instalacoes"].append(
        {
            "id": "cano",
            "forma": "trecho",
            "tipo": "agua_fria",
            "caminho": [[1000, 4750], [1000, 3000]],
            "altura": alt,
        }
    )
    p = montar().pavimentos[0]
    banheiro = geometria.recorte_do_comodo(p, "banheiro")
    quarto = geometria.recorte_do_comodo(p, "quarto")
    assert {e.id for e in banheiro.estrutura} == {"v1"}
    assert {e.id for e in quarto.estrutura} == {"pl1", "v1"}
    assert "cano" in {i.id for i in banheiro.instalacoes}
    assert "cano" not in {i.id for i in quarto.instalacoes}
