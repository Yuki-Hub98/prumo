import pytest
from pydantic import ValidationError

from interiores_core.medidas import Medida, Origem, medidas_em, medidas_estimadas
from interiores_core.modelo import Parede


def test_medida_valida() -> None:
    m = Medida.model_validate(
        {"valor": 3150, "origem": "trena", "obs": "rodapé", "data": "2026-11-17"}
    )
    assert m.valor == 3150
    assert m.origem is Origem.TRENA
    assert not m.estimada


@pytest.mark.parametrize(
    "bruto",
    [
        {"valor": 315.0, "origem": "trena"},  # decimal: unidade interna é mm inteiro
        {"valor": "3150", "origem": "trena"},  # texto
        {"valor": -1, "origem": "trena"},
        {"valor": 3150, "origem": "chute"},  # origem fora da lista
        {"valor": 3150},  # sem origem
        {"valor": 3150, "origem": "trena", "unidade": "cm"},  # campo desconhecido
    ],
)
def test_medida_invalida(bruto: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Medida.model_validate(bruto)


def test_medidas_em_usa_ids_no_caminho() -> None:
    parede = Parede.model_validate(
        {
            "id": "p1",
            "inicio": [0, 0],
            "fim": [1000, 0],
            "espessura": {"valor": 150, "origem": "estimada"},
            "altura": {"valor": 2600, "origem": "trena"},
            "lado_a": "quarto",
            "lado_b": "externo",
        }
    )
    caminhos = dict(medidas_em([parede], "paredes"))
    assert set(caminhos) == {"paredes[p1].espessura", "paredes[p1].altura"}
    assert [c for c, _ in medidas_estimadas([parede], "paredes")] == ["paredes[p1].espessura"]
