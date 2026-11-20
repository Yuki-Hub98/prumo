"""Regras da cozinha (tipos/cozinha.py) numa cozinha de 3,6 × 3,0 m montada no teste."""

from typing import Any

import pytest

from interiores_core import catalogo
from interiores_core.modelo import DadosComodo, Movel, Projeto
from interiores_core.partes import partes_do_movel
from interiores_core.regras import checar
from interiores_core.validacao import Problema, Severidade

M = {"origem": "projeto"}


def _m(v: int) -> dict[str, Any]:
    return {**M, "valor": v}


def _parede(id_: str, a: list[int], b: list[int], fora: str = "externo") -> dict[str, Any]:
    return {
        "id": id_,
        "inicio": a,
        "fim": b,
        "espessura": _m(150),
        "lado_a": "cozinha",
        "lado_b": fora,
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


def _ponto(id_: str, tipo: str, pos: list[int]) -> dict[str, Any]:
    return {"id": id_, "forma": "ponto", "tipo": tipo, "posicao": pos, "altura": _m(600)}


@pytest.fixture
def projeto() -> dict[str, Any]:
    """Cozinha 3600 × 3000 (eixos), janela na parede de cima, porta para fora na esquerda."""
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
                    _parede("p1", [0, 0], [3600, 0]),
                    _parede("p2", [3600, 0], [3600, 3000]),
                    _parede("p3", [3600, 3000], [0, 3000]),
                    _parede("p4", [0, 3000], [0, 0]),
                ],
                "aberturas": [
                    {
                        "id": "j1",
                        "tipo": "janela",
                        "parede": "p3",
                        "distancia_inicio": _m(1200),
                        "largura": _m(1200),
                        "altura": _m(1000),
                        "peitoril": _m(1100),
                    },
                    {
                        "id": "po1",
                        "tipo": "porta",
                        "parede": "p4",
                        "distancia_inicio": _m(1000),
                        "largura": _m(800),
                        "altura": _m(2100),
                        "de": "externo",
                        "para": "cozinha",
                        "abre_para": "cozinha",
                        "dobradica": "inicio",
                    },
                ],
                "instalacoes": [
                    _ponto("af", "agua_fria", [600, 75]),
                    _ponto("es", "esgoto", [700, 75]),
                    _ponto("gas", "gas", [2000, 75]),
                ],
                "comodos": [
                    {
                        "id": "cozinha",
                        "nome": "Cozinha",
                        "tipo": "cozinha",
                        "paredes": ["p1", "p2", "p3", "p4"],
                    },
                ],
            }
        ],
    }


@pytest.fixture
def moveis() -> dict[str, Any]:
    """Linha na parede de baixo (frentes para +y) e geladeira na direita: triângulo ok."""
    return {
        "schema_version": 1,
        "comodo": "cozinha",
        "moveis": [
            _movel("pia", "pia", [700, 350], 1200, 550, 900, modelo="120"),
            _movel("fogao", "fogao", [2000, 375], 550, 600, 850, modelo="4bocas"),
            _movel("geladeira", "geladeira", [3165, 1600], 700, 720, 1800, rotacao=90),
        ],
    }


def rodar(projeto: dict[str, Any], moveis: dict[str, Any], regras: Any = None) -> list[Problema]:
    return checar(
        Projeto.model_validate(projeto),
        {"cozinha": DadosComodo.model_validate(moveis)},
        regras,
    )


def codigos(ps: list[Problema]) -> set[str]:
    return {p.codigo for p in ps}


def _mov(moveis: dict[str, Any], id_: str) -> dict[str, Any]:
    return next(m for m in moveis["moveis"] if m["id"] == id_)


def _inst(projeto: dict[str, Any]) -> list[dict[str, Any]]:
    return projeto["pavimentos"][0]["instalacoes"]  # type: ignore[no-any-return]


DA_COZINHA = {
    "triangulo_trabalho",
    "triangulo_incompleto",
    "pia_sem_agua",
    "pia_sem_esgoto",
    "fogao_sem_gas",
    "fogao_sem_ventilacao",
    "fogao_sob_janela",
    "altura_bancada",
}


def test_cozinha_bem_montada_passa(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    assert codigos(rodar(projeto, moveis)) & DA_COZINHA == set()


def test_triangulo_longe_demais(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    _mov(moveis, "pia")["centro"] = [700, 350]
    _mov(moveis, "fogao")["centro"] = [700, 2625]
    _mov(moveis, "fogao")["rotacao"] = 180
    _mov(moveis, "geladeira")["centro"] = [3165, 2500]
    ps = [p for p in rodar(projeto, moveis) if p.codigo == "triangulo_trabalho"]
    assert len(ps) == 1 and "longe demais" in ps[0].mensagem
    assert ps[0].severidade is Severidade.AVISO and ps[0].regiao


def test_triangulo_respeita_regras_toml(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    ps = rodar(projeto, moveis, {"cozinha": {"triangulo_min": 9000, "triangulo_max": 12000}})
    assert any(p.codigo == "triangulo_trabalho" and "apertado" in p.mensagem for p in ps)


def test_triangulo_incompleto_e_info(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    moveis["moveis"] = [m for m in moveis["moveis"] if m["id"] != "geladeira"]
    ps = [p for p in rodar(projeto, moveis) if p.codigo == "triangulo_incompleto"]
    assert len(ps) == 1 and ps[0].severidade is Severidade.INFO and "geladeira" in ps[0].mensagem


def test_pia_sem_agua_e_esgoto(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    projeto["pavimentos"][0]["instalacoes"] = [i for i in _inst(projeto) if i["id"] == "gas"]
    ps = rodar(projeto, moveis)
    erros = {p.codigo for p in ps if p.severidade is Severidade.ERRO and p.elemento == "pia"}
    assert erros == {"pia_sem_agua", "pia_sem_esgoto"}


def test_ponto_longe_da_pia_nao_vale(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    for i in _inst(projeto):
        if i["id"] == "es":
            i["posicao"] = [3000, 75]  # 1,7 m da pia
    assert "pia_sem_esgoto" in codigos(rodar(projeto, moveis))


def test_fogao_a_gas_sem_ponto(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    projeto["pavimentos"][0]["instalacoes"] = [i for i in _inst(projeto) if i["id"] != "gas"]
    assert "fogao_sem_gas" in codigos(rodar(projeto, moveis))
    # cooktop de indução não precisa de gás
    _mov(moveis, "fogao")["modelo"] = "cooktop"
    assert "fogao_sem_gas" not in codigos(rodar(projeto, moveis))


def test_fogao_a_gas_sem_ventilacao(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    pav = projeto["pavimentos"][0]
    pav["aberturas"] = []
    assert "fogao_sem_ventilacao" in codigos(rodar(projeto, moveis))


def test_fogao_sob_janela(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    f = _mov(moveis, "fogao")
    f["centro"], f["rotacao"] = [1800, 2625], 180  # encostado na parede da janela
    ps = [p for p in rodar(projeto, moveis) if p.codigo == "fogao_sob_janela"]
    assert len(ps) == 1 and ps[0].elemento == "fogao" and "j1" in ps[0].mensagem


def test_altura_da_bancada(projeto: dict[str, Any], moveis: dict[str, Any]) -> None:
    _mov(moveis, "pia")["altura"] = _m(800)
    ps = [p for p in rodar(projeto, moveis) if p.codigo == "altura_bancada"]
    assert len(ps) == 1 and "800 mm" in ps[0].mensagem


def test_catalogo_e_partes_da_cozinha() -> None:
    for tipo in ("pia", "fogao", "geladeira"):
        item = catalogo.item_do_tipo(tipo)
        assert item is not None and item.categoria is catalogo.Categoria.COZINHA
        assert item.modelo() is not None
    fogao = catalogo.item_do_tipo("fogao")
    assert fogao is not None
    assert {m.id: m.energia for m in fogao.modelos}["cooktop"] == "eletrico"
    pia = Movel.model_validate(_movel("pia", "pia", [0, 0], 1200, 550, 900))
    assert {"bancada", "cuba", "torneira"} <= set(partes_do_movel(pia))
