"""Escadas de alvenaria: conta dos degraus, formas, furo na laje e checagens."""

import math
from collections.abc import Callable
from typing import Any

import pytest
from apoio import pav
from shapely import Point, Polygon

from interiores_core import edicao, escadas, geometria
from interiores_core.modelo import Escada, Pavimento, Projeto
from interiores_core.regras import checar


def M(v: int, origem: str = "projeto") -> dict[str, Any]:  # noqa: N802 - atalho de Medida
    return {"valor": v, "origem": origem}


PAV = Pavimento.model_validate({"id": "t", "cota_piso": M(0), "pe_direito": M(2700)})


def escada(**extra: Any) -> Escada:
    return Escada.model_validate(
        {"id": "esc", "tipo": "escada", "inicio": [0, 0], "largura": M(900), **extra}
    )


def test_conta_dos_degraus() -> None:
    # sem laje: pé-direito + 12 cm estimados = 2820 → 16 espelhos de 176,25; piso por Blondel
    n, espelho, piso = escadas.espelhos_e_piso(2820)
    assert (n, round(espelho, 2), piso) == (16, 176.25, 280)
    assert escadas.espelhos_e_piso(2000)[1] <= escadas.ESPELHO_MAX
    assert escadas.espelhos_e_piso(2820, piso=300)[2] == 300  # piso informado vale


@pytest.mark.parametrize(
    ("forma", "lances", "caixa"),
    [("reta", (15,), (4200, 900)), ("L", (7, 7), (2860, 2860)), ("U", (7, 7), (2860, 1900))],
)
def test_formas(forma: str, lances: tuple[int, ...], caixa: tuple[int, int]) -> None:
    c = escadas.calcular(PAV, escada(forma=forma))
    assert c.lances == lances and len(c.degraus) == 15
    x0, y0, x1, y1 = c.contorno.bounds
    assert (round(x1 - x0), round(y1 - y0)) == caixa
    # sobe sempre: cada degrau 1 espelho acima do anterior; o último chega 1 espelho abaixo
    assert [round(d.z) for d in c.degraus] == [round((i + 1) * c.espelho) for i in range(15)]
    assert sum(d.patamar for d in c.degraus) == (0 if forma == "reta" else 1)


def test_direcao_gira_e_primeiro_lance() -> None:
    norte = escadas.calcular(PAV, escada(direcao=90))
    assert norte.contorno.bounds[3] == pytest.approx(4200)  # sobe para +y
    esq = escadas.calcular(PAV, escada(forma="L"))
    dir_ = escadas.calcular(PAV, escada(forma="L", gira="direita"))
    assert esq.contorno.bounds[3] > 0 > dir_.contorno.bounds[1]  # vira para lados opostos
    assert escadas.calcular(PAV, escada(forma="L", degraus_primeiro_lance=3)).lances == (3, 11)
    assert escadas.calcular(PAV, escada(forma="U", degraus_primeiro_lance=99)).lances == (13, 1)


def test_caracol() -> None:
    c = escadas.calcular(PAV, escada(forma="caracol", inicio=[1000, 1000]))
    assert c.nucleo is not None and c.giro is not None
    # piso medido na linha do meio do degrau: giro = pisos × piso / raio da linha
    assert c.giro == pytest.approx(math.degrees(15 * 280 / 550))
    assert c.contorno.centroid.distance(c.nucleo.centroid) < 50  # tudo em volta do centro


def test_furo_na_laje(montar: Callable[[], Projeto]) -> None:
    f = escadas.furo(PAV, escada())
    assert f is not None
    # degraus a menos de 2,10 m da laje (2,70 m): do 4º em diante (z > 600)
    assert f.bounds[0] == pytest.approx(3 * 280, abs=2) and f.bounds[2] == pytest.approx(4200)

    p = montar()
    for e in (
        {"id": "laje-1", "tipo": "laje", "espessura": M(120)},
        {"id": "esc", "tipo": "escada", "inicio": [500, 300], "direcao": 90, "largura": M(900)},
    ):
        p = edicao.adicionar_estrutura(p, "terreo", e).projeto
    pv = p.pavimentos[0]
    laje = next(x for x in pv.estrutura if x.tipo == "laje")
    cheia = geometria.contorno_pavimento(pv)
    furada = geometria.poligono_estrutura(pv, laje)
    assert cheia is not None and furada is not None
    assert furada.area < cheia.area - 0.9 * 1e6  # perdeu o vão da escada
    assert geometria.furos_de_escada(pv)


def test_furo_da_u_sem_tira_entre_os_lances() -> None:
    f = escadas.furo(PAV, escada(forma="U"))
    assert f is not None and not f.interiors
    # a folga de 10 cm entre os lances fica aberta junto (sem tira de laje no meio)
    meio_y = 450 + escadas.FOLGA_U / 2
    assert f.contains(Point(2000, meio_y))


def _codigos(p: Projeto) -> set[str]:
    return {x.codigo for x in checar(p)}


def test_checagens(casa_dict: dict[str, Any], montar: Callable[[], Projeto]) -> None:
    base = {"id": "esc", "tipo": "escada", "inicio": [700, 300], "direcao": 90}
    # em U, cabe no quarto de 3,50 × 2,63 m (2,97 × 1,90 m com o pé-direito de 2,60)
    pav(casa_dict)["estrutura"] = [
        {**base, "forma": "U", "inicio": [400, 600], "direcao": 0, "largura": M(900)}
    ]
    assert not {c for c in _codigos(montar()) if c.startswith("escada")}

    pav(casa_dict)["estrutura"] = [
        {**base, "largura": M(700), "piso": M(220)},  # estreita, piso curto
        {**base, "id": "fora", "inicio": [-3000, 300], "largura": M(900)},
        {
            **base,
            "id": "parede",
            "inicio": [2000, 300],
            "direcao": 90,
            "largura": M(900),
            "desnivel": M(6000),  # mais alta: a conta põe mais degraus
        },  # atravessa a parede do meio
    ]
    codigos = _codigos(montar())
    assert {"escada_estreita", "escada_piso", "escada_fora", "escada_na_parede"} <= codigos


def test_andar_de_cima_ve_a_escada_chegando(montar: Callable[[], Projeto]) -> None:
    from interiores_core.tela import pavimento_para_tela

    p = edicao.adicionar_estrutura(
        montar(), "terreo",
        {"id": "esc", "tipo": "escada", "forma": "U", "inicio": [400, 600], "largura": M(900)},
    ).projeto  # fmt: skip
    terreo = p.pavimentos[0]
    cima = Pavimento.model_validate({"id": "cima", "cota_piso": M(2720), "pe_direito": M(2600)})
    assert (
        geometria.pavimento_abaixo(p.model_copy(update={"pavimentos": [terreo, cima]}), cima)
        is terreo
    )
    tela = pavimento_para_tela(cima, abaixo=terreo)
    chegando = [e for e in tela.estrutura if e.tipo == "escada_abaixo"]
    assert len(chegando) == 1 and chegando[0].escada is not None
    vao = escadas.furo(terreo, terreo.estrutura[0])  # type: ignore[arg-type]
    assert vao is not None and Polygon(chegando[0].contorno).area == pytest.approx(
        vao.area, rel=0.01
    )
