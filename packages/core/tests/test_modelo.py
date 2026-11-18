from collections.abc import Callable
from typing import Any

import pytest
from apoio import item, pav
from pydantic import ValidationError

from interiores_core.modelo import Janela, Porta, Projeto, TipoComodo


def test_casa_carrega(montar: Callable[[], Projeto]) -> None:
    projeto = montar()
    p = projeto.pavimentos[0]
    assert [c.id for c in p.comodos] == ["quarto", "banheiro"]
    assert p.comodo("banheiro") is not None
    assert p.comodo("banheiro").tipo is TipoComodo.BANHEIRO  # type: ignore[union-attr]
    assert isinstance(p.aberturas[0], Porta)
    assert any(isinstance(a, Janela) for a in p.aberturas)
    assert projeto.pavimento_do_comodo("quarto") is p
    assert projeto.pavimento_do_comodo("cozinha") is None
    assert p.parede("nao-existe") is None


@pytest.mark.parametrize(
    "mutacao",
    [
        lambda d: d.update(schema_version=2),
        lambda d: d.update(projeto="Casa Com Espaço"),
        lambda d: pav(d)["paredes"][0].update(inicio=[0.5, 0]),
        lambda d: pav(d)["aberturas"][0].update(tipo="alçapão"),
        lambda d: item(pav(d)["comodos"], "quarto").update(tipo="sotao"),
        lambda d: item(pav(d)["comodos"], "quarto").update(pavimento="terreo"),
        lambda d: item(pav(d)["aberturas"], "janela-quarto").pop("peitoril"),
    ],
)
def test_formato_invalido(
    casa_dict: dict[str, Any],
    montar: Callable[[], Projeto],
    mutacao: Callable[[dict[str, Any]], Any],
) -> None:
    mutacao(casa_dict)
    with pytest.raises(ValidationError):
        montar()
