"""Redimensionar um móvel arrastando um lado: o oposto fica parado."""

import pytest
from apoio import CASA

from interiores_core import edicao_moveis as em
from interiores_core import geometria
from interiores_core.carregar import carregar
from interiores_core.edicao import EdicaoInvalidaError
from interiores_core.modelo import Movel


def _movel(ed: em.EdicaoMoveis, id_: str) -> Movel:
    return next(m for m in ed.dados.moveis if m.id == id_)


@pytest.mark.parametrize("lado", ["esquerda", "direita", "frente", "costas"])
def test_lado_oposto_fica_parado(lado: str) -> None:
    c = carregar(CASA)
    dados = c.dados_comodos["quarto"]
    antes = next(m for m in dados.moveis if m.id == "guarda-roupa")
    oposto = {"esquerda": "direita", "direita": "esquerda", "frente": "costas", "costas": "frente"}[
        lado
    ]
    campo = "largura" if lado in ("esquerda", "direita") else "profundidade"
    novo = getattr(antes, campo).valor + 300
    ed = em.redimensionar_movel(c.projeto, "quarto", dados, "guarda-roupa", lado, novo)
    depois = _movel(ed, "guarda-roupa")
    assert getattr(depois, campo).valor == novo
    assert getattr(depois, campo).origem == "projeto"

    def meio(m: Movel, qual: str) -> tuple[float, float]:
        from interiores_core.regras.contexto import lado_local

        (a, b), _ = lado_local(m, qual)
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    # o lado oposto continua no mesmo lugar (com folga do arredondamento do centro)
    pa, pd = meio(antes, oposto), meio(depois, oposto)
    assert abs(pa[0] - pd[0]) <= 1 and abs(pa[1] - pd[1]) <= 1
    assert geometria.poligono_movel(depois).area > geometria.poligono_movel(antes).area


def test_chute_guarda_o_valor_anterior_e_minimo() -> None:
    c = carregar(CASA)
    dados = c.dados_comodos["quarto"]
    ed = em.redimensionar_movel(c.projeto, "quarto", dados, "cama", "direita", 1600)
    cama = _movel(ed, "cama")
    assert cama.largura.obs and "antes:" in cama.largura.obs
    with pytest.raises(EdicaoInvalidaError, match="mínimo"):
        em.redimensionar_movel(c.projeto, "quarto", dados, "cama", "direita", 50)
    with pytest.raises(EdicaoInvalidaError, match="inválido"):
        em.redimensionar_movel(c.projeto, "quarto", dados, "cama", "cima", 900)
