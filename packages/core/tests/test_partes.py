"""Partes dos móveis com cor própria (portas, gavetas, travesseiros...)."""

from collections.abc import Callable

import pytest

from interiores_core.edicao import EdicaoInvalidaError
from interiores_core.edicao_variacoes import validar_variacao
from interiores_core.modelo import Movel, Projeto
from interiores_core.partes import CORPO, PARTES, POR_SIMBOLO, parte_da_peca, partes_do_movel


@pytest.mark.parametrize(
    ("peca", "parte"),
    [
        ("folha0", "portas"),
        ("porta3", "portas"),
        ("gaveta2", "gavetas"),
        ("puxador1", "puxadores"),
        ("travesseiro0", "travesseiros"),
        ("edredom", "roupa_de_cama"),
        ("dobra", "roupa_de_cama"),
        ("colchao", "colchao"),
        ("almofada1", "almofadas"),
        ("encosto0", "almofadas"),  # almofada das costas do sofá
        ("encosto", "encosto"),
        ("pe2", "pes"),
        ("tampo", "tampo"),
        ("corpo", CORPO),
        ("rodape", CORPO),
        ("base", CORPO),
    ],
)
def test_parte_da_peca(peca: str, parte: str) -> None:
    assert parte_da_peca(peca) == parte


def test_partes_por_tipo() -> None:
    def movel(tipo: str) -> Movel:
        return Movel.model_validate(
            {"id": "x", "tipo": tipo, "centro": [0, 0], "rotacao": 0,
             "largura": {"valor": 1000, "origem": "projeto"},
             "profundidade": {"valor": 500, "origem": "projeto"},
             "altura": {"valor": 800, "origem": "projeto"}}
        )  # fmt: skip

    assert partes_do_movel(movel("guarda_roupa")) == ("portas", "puxadores")
    assert partes_do_movel(movel("cama")) == (
        "cabeceira",
        "colchao",
        "roupa_de_cama",
        "travesseiros",
    )
    assert partes_do_movel(movel("comoda")) == ("gavetas", "puxadores", "pes")
    assert partes_do_movel(movel("nao-existe")) == ()
    assert all(p in PARTES for ps in POR_SIMBOLO.values() for p in ps)


def test_variacao_recusa_parte_desconhecida(montar: Callable[[], Projeto]) -> None:
    projeto = montar()
    ok = {"cores": {"pecas": {"guarda-roupa": {"portas": "#ffffff"}}}}
    assert validar_variacao(projeto, "quarto", "x", ok).cores.pecas["guarda-roupa"]["portas"]
    ruim = {"cores": {"pecas": {"guarda-roupa": {"telhado": "#ffffff"}}}}
    with pytest.raises(EdicaoInvalidaError, match="telhado"):
        validar_variacao(projeto, "quarto", "x", ruim)
