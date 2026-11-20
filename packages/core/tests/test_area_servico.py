"""Regras da área de serviço numa lavanderia de 2,0 × 1,6 m montada no teste."""

from typing import Any

from interiores_core import catalogo
from interiores_core.modelo import DadosComodo, Projeto
from interiores_core.regras import checar
from interiores_core.validacao import Problema, Severidade


def _m(v: int) -> dict[str, Any]:
    return {"valor": v, "origem": "projeto"}


def _projeto(pontos: list[dict[str, Any]]) -> Projeto:
    paredes = [
        ("p1", [0, 0], [2000, 0]), ("p2", [2000, 0], [2000, 1600]),
        ("p3", [2000, 1600], [0, 1600]), ("p4", [0, 1600], [0, 0]),
    ]  # fmt: skip
    return Projeto.model_validate({
        "schema_version": 1, "projeto": "t", "imovel": {"tipo": "casa"},
        "pavimentos": [{
            "id": "terreo", "pe_direito": _m(2700), "cota_piso": _m(0),
            "paredes": [{"id": i, "inicio": a, "fim": b, "espessura": _m(150),
                         "lado_a": "servico", "lado_b": "externo"} for i, a, b in paredes],
            "aberturas": [{"id": "po", "tipo": "porta", "parede": "p4",
                           "distancia_inicio": _m(400), "largura": _m(700), "altura": _m(2100),
                           "de": "externo", "para": "servico", "folha": "correr"}],
            "instalacoes": pontos,
            "comodos": [{"id": "servico", "nome": "Lavanderia", "tipo": "area_servico",
                         "paredes": ["p1", "p2", "p3", "p4"]}],
        }],
    })  # fmt: skip


def _ponto(id_: str, tipo: str, pos: list[int]) -> dict[str, Any]:
    return {"id": id_, "forma": "ponto", "tipo": tipo, "posicao": pos, "altura": _m(900)}


def _rodar(pontos: list[dict[str, Any]], moveis: list[dict[str, Any]]) -> list[Problema]:
    dados = DadosComodo.model_validate({"schema_version": 1, "comodo": "servico", "moveis": moveis})
    return checar(_projeto(pontos), {"servico": dados})


MAQUINA = catalogo.novo_movel("maquina_lavar", "maquina", (400, 400))
TANQUE = catalogo.novo_movel("tanque", "tanque", (1200, 300))


def test_maquina_e_tanque_com_pontos_passam() -> None:
    pontos = [
        _ponto("af", "agua_fria", [400, 75]),
        _ponto("es", "esgoto", [600, 75]),
        _ponto("af2", "agua_fria", [1200, 75]),
        _ponto("es2", "esgoto", [1300, 75]),
    ]
    codigos = {p.codigo for p in _rodar(pontos, [MAQUINA, TANQUE])}
    assert not {c for c in codigos if "sem_" in c or c == "area_servico_incompleta"}


def test_sem_pontos_e_erro() -> None:
    ps = [p for p in _rodar([], [MAQUINA, TANQUE]) if p.severidade is Severidade.ERRO]
    assert {p.codigo for p in ps} >= {
        "maquina_lavar_sem_agua_fria", "maquina_lavar_sem_esgoto",
        "tanque_sem_agua_fria", "tanque_sem_esgoto",
    }  # fmt: skip


def test_lavanderia_vazia_lembra_do_espaco() -> None:
    ps = [p for p in _rodar([], []) if p.codigo == "area_servico_incompleta"]
    assert len(ps) == 1 and ps[0].severidade is Severidade.INFO
    assert "máquina de lavar" in ps[0].mensagem and "tanque" in ps[0].mensagem
