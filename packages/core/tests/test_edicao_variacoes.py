"""Validação de variações de cor."""

import pytest
from apoio import CASA

from interiores_core.edicao import EdicaoInvalidaError, ler_projeto
from interiores_core.edicao_variacoes import validar_variacao
from interiores_core.modelo import Variacao


def test_parede_de_destaque_valida() -> None:
    p = ler_projeto(CASA)
    var = validar_variacao(p, "quarto", "destaque", {"cores": {"paredes": {"p2": "#c46b4f"}}})
    assert var.cores.paredes == {"p2": "#c46b4f"} and var.comodo == "quarto"
    pronta = Variacao(schema_version=1, comodo="quarto")
    assert validar_variacao(p, "quarto", "vazia", pronta) is pronta


def test_recusas() -> None:
    p = ler_projeto(CASA)
    with pytest.raises(EdicaoInvalidaError, match="p4"):  # p4 é só do banheiro
        validar_variacao(p, "quarto", "x", {"cores": {"paredes": {"p4": "#000000"}}})
    with pytest.raises(EdicaoInvalidaError, match="reservado"):
        validar_variacao(p, "quarto", "base", {})
    with pytest.raises(EdicaoInvalidaError, match="inválido"):
        validar_variacao(p, "quarto", "Minha Cor", {})
    with pytest.raises(EdicaoInvalidaError, match="dados inválidos"):
        validar_variacao(p, "quarto", "x", {"cores": {"parede": "vermelho"}})
    with pytest.raises(EdicaoInvalidaError, match="banheiro"):
        validar_variacao(p, "quarto", "x", Variacao(schema_version=1, comodo="banheiro"))
    with pytest.raises(KeyError):
        validar_variacao(p, "cozinha", "x", {})
