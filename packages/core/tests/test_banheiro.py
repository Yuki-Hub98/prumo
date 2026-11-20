"""Regras do banheiro (tipos/banheiro.py) num banheiro de 2,4 × 2,4 m montado no teste."""

from typing import Any

import pytest

from interiores_core import catalogo
from interiores_core.modelo import DadosComodo, Movel, Projeto
from interiores_core.partes import partes_do_movel
from interiores_core.regras import checar
from interiores_core.tipos import modulo_do_tipo
from interiores_core.validacao import Problema, Severidade


def _m(v: int) -> dict[str, Any]:
    return {"valor": v, "origem": "projeto"}


def _parede(id_: str, a: list[int], b: list[int]) -> dict[str, Any]:
    return {
        "id": id_,
        "inicio": a,
        "fim": b,
        "espessura": _m(150),
        "lado_a": "banheiro",
        "lado_b": "externo",
    }


def _movel(
    id_: str, tipo: str, centro: list[int], larg: int, prof: int, alt: int, **extra: Any
) -> dict[str, Any]:
    return {
        "id": id_,
        "tipo": tipo,
        "centro": centro,
        "largura": _m(larg),
        "profundidade": _m(prof),
        "altura": _m(alt),
        **extra,
    }


def _ponto(id_: str, tipo: str, pos: list[int], parede: str | None = None) -> dict[str, Any]:
    p = {"id": id_, "forma": "ponto", "tipo": tipo, "posicao": pos, "altura": _m(300)}
    return {**p, "parede": parede} if parede else p


@pytest.fixture
def projeto() -> dict[str, Any]:
    """Vaso e lavatório na parede de baixo, box no canto de cima à direita, porta à esquerda."""
    return {
        "schema_version": 1,
        "projeto": "teste",
        "imovel": {"tipo": "casa"},
        "pavimentos": [
            {
                "id": "terreo",
                "pe_direito": _m(2700),
                "cota_piso": _m(0),
                "paredes": [
                    _parede("p1", [0, 0], [2400, 0]),
                    _parede("p2", [2400, 0], [2400, 2400]),
                    _parede("p3", [2400, 2400], [0, 2400]),
                    _parede("p4", [0, 2400], [0, 0]),
                ],
                "aberturas": [
                    {
                        "id": "po1",
                        "tipo": "porta",
                        "parede": "p4",
                        "distancia_inicio": _m(400),
                        "largura": _m(700),
                        "altura": _m(2100),
                        "de": "externo",
                        "para": "banheiro",
                        "abre_para": "banheiro",
                        "dobradica": "inicio",
                    },
                ],
                "instalacoes": [
                    _ponto("es-vaso", "esgoto", [500, 100]),
                    _ponto("af-lav", "agua_fria", [1200, 0], "p1"),
                    _ponto("es-lav", "esgoto", [1300, 100]),
                    _ponto("ralo", "ralo", [1725, 1925]),
                    _ponto("tomada", "tomada", [900, 0], "p1"),
                ],
                "comodos": [
                    {
                        "id": "banheiro",
                        "nome": "Banheiro",
                        "tipo": "banheiro",
                        "paredes": ["p1", "p2", "p3", "p4"],
                    },
                ],
            }
        ],
    }


@pytest.fixture
def moveis() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "comodo": "banheiro",
        "moveis": [
            _movel("vaso", "vaso", [500, 400], 370, 650, 780, modelo="acoplada"),
            _movel("lav", "lavatorio", [1200, 300], 600, 450, 850, modelo="60"),
            _movel("box", "box", [1725, 1925], 1200, 800, 1900, modelo="80x120", rotacao=180),
        ],
    }


def rodar(projeto: dict[str, Any], moveis: dict[str, Any], regras: Any = None) -> list[Problema]:
    return checar(
        Projeto.model_validate(projeto),
        {"banheiro": DadosComodo.model_validate(moveis)},
        regras,
    )


def _inst(projeto: dict[str, Any]) -> list[dict[str, Any]]:
    return projeto["pavimentos"][0]["instalacoes"]  # type: ignore[no-any-return]


def _mov(moveis: dict[str, Any], id_: str) -> dict[str, Any]:
    return next(m for m in moveis["moveis"] if m["id"] == id_)


def do_banheiro(ps: list[Problema]) -> set[str]:
    modulo = modulo_do_tipo("banheiro")
    assert modulo is not None
    nossos = {
        "frente_vaso",
        "frente_lavatorio",
        "tomada_box",
        "box_sem_ralo",
        "vaso_sem_esgoto",
        "lavatorio_sem_agua",
        "lavatorio_sem_esgoto",
    }
    return {p.codigo for p in ps if p.codigo in nossos}


def test_banheiro_bem_montado_passa(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    ps = rodar(projeto, moveis)
    assert do_banheiro(ps) == set()
    assert not [p for p in ps if p.severidade is Severidade.ERRO]


def test_frente_do_vaso_apertada(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    # lavatório na frente do vaso, a 300 mm
    _mov(moveis, "lav")["centro"] = [500, 1180]
    _mov(moveis, "lav")["rotacao"] = 180
    ps = [p for p in rodar(projeto, moveis) if p.codigo == "frente_vaso"]
    assert len(ps) == 1 and ps[0].elemento == "vaso" and ps[0].severidade is Severidade.AVISO


def test_limite_da_frente_no_regras_toml(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    # do lavatório até o box: ~1,1 m livres
    assert "frente_lavatorio" in do_banheiro(
        rodar(projeto, moveis, {"banheiro": {"frente_lavatorio": 1500}})
    )


def test_tomada_perto_do_box(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    for i in _inst(projeto):
        if i["id"] == "tomada":
            i["posicao"], i["parede"] = [2400, 1300], "p2"  # 225 mm abaixo do box
    ps = [p for p in rodar(projeto, moveis) if p.codigo == "tomada_box"]
    assert len(ps) == 1 and ps[0].severidade is Severidade.ERRO and ps[0].elemento == "tomada"


def test_tomada_do_outro_lado_da_parede_nao_conta(
    projeto: dict[str, Any], moveis: dict[str, Any]
) -> None:
    for i in _inst(projeto):
        if i["id"] == "tomada":
            i["posicao"], i["parede"], i["comodo"] = [2400, 1300], "p2", "externo"
    assert "tomada_box" not in do_banheiro(rodar(projeto, moveis))


def test_box_sem_ralo(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    projeto["pavimentos"][0]["instalacoes"] = [i for i in _inst(projeto) if i["id"] != "ralo"]
    ps = [p for p in rodar(projeto, moveis) if p.codigo == "box_sem_ralo"]
    assert len(ps) == 1 and ps[0].severidade is Severidade.ERRO


def test_vaso_e_lavatorio_sem_pontos(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    projeto["pavimentos"][0]["instalacoes"] = [i for i in _inst(projeto) if i["id"] == "ralo"]
    assert do_banheiro(rodar(projeto, moveis)) == {
        "vaso_sem_esgoto",
        "lavatorio_sem_agua",
        "lavatorio_sem_esgoto",
    }


def test_catalogo_e_partes_do_banheiro() -> None:
    for tipo in ("vaso", "lavatorio", "box"):
        item = catalogo.item_do_tipo(tipo)
        assert item is not None and item.categoria is catalogo.Categoria.BANHEIRO
        assert item.modelo() is not None
    vaso = Movel.model_validate(_movel("v", "vaso", [0, 0], 370, 650, 780))
    box = Movel.model_validate(_movel("b", "box", [0, 0], 1200, 800, 1900))
    lav = Movel.model_validate(_movel("l", "lavatorio", [0, 0], 600, 450, 850))
    assert partes_do_movel(vaso) == ("assento", "caixa")
    assert partes_do_movel(box) == ("vidros", "perfis")
    assert "cuba" in partes_do_movel(lav)
