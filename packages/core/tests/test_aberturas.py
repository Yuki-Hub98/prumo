"""Tipos de porta e janela: camarão, estilos, aberturas de janela e o catálogo comercial."""

import math
from collections.abc import Callable
from typing import Any

import pytest
from apoio import item, pav

from interiores_core import catalogo_aberturas as cat
from interiores_core import edicao, geometria, tinta
from interiores_core.modelo import Janela, Porta, Projeto
from interiores_core.validacao import validar


def test_porta_camarao_varre_meia_largura(
    casa_dict: dict[str, Any], montar: Callable[[], Projeto]
) -> None:
    giro = montar()
    porta = next(a for a in giro.pavimentos[0].aberturas if a.id == "porta-quarto")
    assert isinstance(porta, Porta)
    area_giro = geometria.giro_porta(giro.pavimentos[0], porta).area  # type: ignore[union-attr]
    item(pav(casa_dict)["aberturas"], "porta-quarto")["folha"] = "camarao"
    camarao = montar()
    porta = next(a for a in camarao.pavimentos[0].aberturas if a.id == "porta-quarto")
    assert isinstance(porta, Porta)
    varre = geometria.giro_porta(camarao.pavimentos[0], porta)
    assert varre is not None
    # quarto de círculo de raio L/2 tem 1/4 da área do de raio L
    assert varre.area == pytest.approx(area_giro / 4, rel=0.02)
    assert varre.area == pytest.approx(math.pi * (porta.largura.valor / 2) ** 2 / 4, rel=0.03)


def test_camarao_precisa_de_sentido_e_dobradica(
    casa_dict: dict[str, Any], montar: Callable[[], Projeto]
) -> None:
    porta = item(pav(casa_dict)["aberturas"], "porta-quarto")
    porta["folha"] = "camarao"
    porta.pop("abre_para")
    porta.pop("dobradica")
    codigos = {p.codigo for p in validar(montar())}
    assert {"porta_sentido", "porta_dobradica"} <= codigos


def test_campos_novos_sao_opcionais_e_editaveis(montar: Callable[[], Projeto]) -> None:
    p = montar()
    janela = next(a for a in p.pavimentos[0].aberturas if a.id == "janela-quarto")
    assert isinstance(janela, Janela) and janela.abertura is None and janela.folhas is None
    r = edicao.alterar_abertura(p, "terreo", "janela-quarto", {"abertura": "abrir", "folhas": 2})
    j = next(a for a in r.projeto.pavimentos[0].aberturas if a.id == "janela-quarto")
    assert isinstance(j, Janela) and (j.abertura, j.folhas) == ("abrir", 2)
    r = edicao.alterar_abertura(
        p, "terreo", "porta-quarto", {"estilo": "vidro", "modelo": "vidro-80"}
    )
    po = next(a for a in r.projeto.pavimentos[0].aberturas if a.id == "porta-quarto")
    assert isinstance(po, Porta) and (po.estilo, po.modelo) == ("vidro", "vidro-80")
    with pytest.raises(Exception):  # noqa: B017 - campo de janela numa porta
        edicao.alterar_abertura(p, "terreo", "porta-quarto", {"abertura": "abrir"})


def test_camarao_entra_na_tinta(casa_dict: dict[str, Any], montar: Callable[[], Projeto]) -> None:
    item(pav(casa_dict)["aberturas"], "porta-quarto")["folha"] = "camarao"
    nomes = {s.nome for s in tinta.superficies(montar().pavimentos[0])}
    assert "Porta porta-quarto (dois lados)" in nomes


def test_catalogo_de_aberturas() -> None:
    assert {m.folha for m in cat.PORTAS} == {"giro", "correr", "camarao"}
    assert {m.abertura for m in cat.JANELAS} == {
        "correr",
        "basculante",
        "maxim_ar",
        "abrir",
        "fixa",
    }
    assert len({m.id for m in cat.PORTAS}) == len(cat.PORTAS)
    assert len({m.id for m in cat.JANELAS}) == len(cat.JANELAS)
    b = cat.modelo_janela("basculante-60x60")
    assert b is not None and b.peitoril >= 1400 and "banheiro" in b.uso
    p80 = cat.modelo_porta("giro-80")
    assert p80 is not None and (p80.largura, p80.altura) == (800, 2100)
    assert cat.modelo_porta("nao-existe") is None
