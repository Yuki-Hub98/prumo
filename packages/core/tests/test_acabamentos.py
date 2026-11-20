"""Acabamento, puxador e pés: opções, edição e o que vai para o 3D."""

from interiores_core import catalogo
from interiores_core.acabamentos import ACABAMENTOS, PES, PUXADORES, opcoes_do_movel
from interiores_core.modelo import Movel
from interiores_core.partes import partes_do_movel


def _m(tipo: str, **extra: object) -> Movel:
    med = {"valor": 800, "origem": "projeto"}
    return Movel.model_validate(
        {
            "id": "x",
            "tipo": tipo,
            "centro": [0, 0],
            "largura": med,
            "profundidade": med,
            "altura": med,
            **extra,
        }
    )


def test_opcoes_por_tipo() -> None:
    assert opcoes_do_movel(_m("guarda_roupa")) == ("acabamento", "puxador")
    assert opcoes_do_movel(_m("comoda")) == ("acabamento", "puxador", "pes")
    assert opcoes_do_movel(_m("mesa")) == ("acabamento", "pes")
    assert opcoes_do_movel(_m("cama")) == ("acabamento",)


def test_rodape_tira_os_pes_das_partes() -> None:
    assert "pes" in partes_do_movel(_m("comoda"))
    assert "pes" not in partes_do_movel(_m("comoda", pes="rodape"))


def test_catalogo_leva_as_opcoes() -> None:
    cat = catalogo.exportar()
    assert cat["acabamentos"]["madeira_clara"] == ACABAMENTOS["madeira_clara"].nome
    assert set(cat["puxadores"]) == set(PUXADORES) and set(cat["pes"]) == set(PES)
