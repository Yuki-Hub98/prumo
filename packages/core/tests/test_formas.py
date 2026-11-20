"""Formas dos móveis: retângulo, cantos arredondados, redondo/oval e L."""

import math

import pytest
from pydantic import ValidationError

from interiores_core import geometria
from interiores_core.modelo import Movel


def movel(tipo: str = "mesa", **extra: object) -> Movel:
    med = {"origem": "projeto"}
    return Movel.model_validate(
        {"id": "m", "tipo": tipo, "centro": [1000, 2000], "rotacao": 0,
         "largura": {"valor": 1200, **med}, "profundidade": {"valor": 800, **med},
         "altura": {"valor": 750, **med}, **extra}
    )  # fmt: skip


def test_retangulo_continua_igual() -> None:
    m = movel()
    assert m.forma is None
    assert geometria.poligono_movel(m).area == pytest.approx(1200 * 800)


def test_arredondado_redondo_e_l() -> None:
    r = 150
    arred = geometria.poligono_movel(
        movel(forma="arredondado", raio={"valor": r, "origem": "projeto"})
    )
    assert arred.area == pytest.approx(1200 * 800 - (4 - math.pi) * r * r, rel=0.01)
    assert arred.bounds == pytest.approx((400, 1600, 1600, 2400))

    oval = geometria.poligono_movel(movel(forma="redondo"))
    assert oval.area == pytest.approx(math.pi * 600 * 400, rel=0.01)

    b = 300
    em_l = geometria.poligono_movel(movel(forma="L", braco={"valor": b, "origem": "projeto"}))
    assert em_l.area == pytest.approx(1200 * b + b * (800 - b))
    # braço para a frente (+y) do lado esquerdo de quem olha de frente (+x)
    assert em_l.contains(geometria.Point(1500, 2300)) and not em_l.contains(
        geometria.Point(500, 2300)
    )
    direita = geometria.poligono_movel(
        movel(forma="L", lado_l="direita", braco={"valor": b, "origem": "projeto"})
    )
    assert direita.contains(geometria.Point(500, 2300))


def test_forma_gira_com_o_movel() -> None:
    m = movel(forma="L", rotacao=90)
    caixa = geometria.poligono_movel(m).bounds
    assert caixa == pytest.approx((600, 1400, 1400, 2600))  # largura passa a correr em y


def test_formas_possiveis_e_limites() -> None:
    assert len(geometria.formas_possiveis(movel("mesa"))) == 4
    assert len(geometria.formas_possiveis(movel("sob_medida"))) == 4
    assert geometria.formas_possiveis(movel("cama")) == ("retangular",)
    with pytest.raises(ValidationError, match="raio"):
        movel(forma="arredondado", raio={"valor": 500, "origem": "projeto"})
    with pytest.raises(ValidationError, match="braço"):
        movel(forma="L", braco={"valor": 900, "origem": "projeto"})
