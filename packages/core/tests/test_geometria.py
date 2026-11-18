from collections.abc import Callable
from typing import Any

import pytest
from apoio import CASA, item, pav
from shapely import Polygon

from interiores_core import geometria
from interiores_core.modelo import DadosComodo, Movel, Projeto


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


def test_poligono_util_sem_vertices_colineares(montar: Callable[[], Projeto]) -> None:
    """Cada face de parede é um lado só (as cotas da planta dependem disso)."""
    p = montar().pavimentos[0]
    banheiro, quarto = p.comodo("banheiro"), p.comodo("quarto")
    assert banheiro is not None and quarto is not None
    util_b = geometria.poligono_util(p, banheiro)
    util_q = geometria.poligono_util(p, quarto)
    assert isinstance(util_b, Polygon) and isinstance(util_q, Polygon)
    assert len(util_b.exterior.coords) == 5  # retângulo
    assert len(util_q.exterior.coords) == 7  # L


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


def _movel(rotacao: int) -> Movel:
    m = {"valor": 1, "origem": "projeto"}
    return Movel.model_validate(
        {
            "id": "m",
            "tipo": "cama",
            "centro": [1000, 2000],
            "rotacao": rotacao,
            "largura": {**m, "valor": 1400},
            "profundidade": {**m, "valor": 1900},
            "altura": {**m, "valor": 500},
        }
    )


@pytest.mark.parametrize(
    ("rotacao", "frente", "costas_centro"),
    [
        (0, (0, 1), (1000, 1050)),
        (90, (-1, 0), (1950, 2000)),
        (180, (0, -1), (1000, 2950)),
        (270, (1, 0), (50, 2000)),
    ],
)
def test_convencao_de_frente_do_movel(
    rotacao: int, frente: tuple[int, int], costas_centro: tuple[int, int]
) -> None:
    """Rotação 0: costas em -y, frente em +y; a rotação gira no sentido anti-horário."""
    m = _movel(rotacao)
    assert geometria.frente_movel(m) == frente
    (x0, y0), (x1, y1), *_ = geometria.cantos_movel(m)  # os dois primeiros são as costas
    assert (round((x0 + x1) / 2), round((y0 + y1) / 2)) == costas_centro
    assert geometria.poligono_movel(m).area == 1400 * 1900


def test_moveis_do_exemplo_de_costas_para_a_parede() -> None:
    """Cama com cabeceira na parede leste; guarda-roupa com portas para dentro do quarto."""
    dados = DadosComodo.model_validate_json((CASA / "comodos" / "quarto.json").read_text("utf-8"))
    moveis = {m.id: m for m in dados.moveis}
    assert geometria.frente_movel(moveis["cama"]) == (-1, 0)
    assert geometria.frente_movel(moveis["guarda-roupa"]) == (1, 0)


def test_recorte_respeita_comodo_do_ponto(
    casa_dict: dict[str, Any], montar: Callable[[], Projeto]
) -> None:
    """Ponto da pia na parede quarto|banheiro só entra no banheiro."""
    item(pav(casa_dict)["instalacoes"], "agua-pia")["comodo"] = "banheiro"
    p = montar().pavimentos[0]
    ids_quarto = {i.id for i in geometria.recorte_do_comodo(p, "quarto").instalacoes}
    ids_banheiro = {i.id for i in geometria.recorte_do_comodo(p, "banheiro").instalacoes}
    assert "agua-pia" not in ids_quarto and "agua-pia" in ids_banheiro
    item(pav(casa_dict)["instalacoes"], "agua-pia").pop("comodo")
    p = montar().pavimentos[0]
    assert "agua-pia" in {i.id for i in geometria.recorte_do_comodo(p, "quarto").instalacoes}
