"""Modelos próprios: o móvel vira modelo sem a posição e volta igual em outro lugar."""

import json
from typing import Any

import pytest
from apoio import CASA

from interiores_core import edicao_moveis as em
from interiores_core.carregar import carregar
from interiores_core.edicao import EdicaoInvalidaError
from interiores_core.modelo import Movel
from interiores_core.modelos_proprios import DO_LUGAR, modelo_do_movel, movel_do_modelo


def _cama() -> Movel:
    dados = json.loads((CASA / "comodos" / "quarto.json").read_text(encoding="utf-8"))
    return Movel.model_validate(next(m for m in dados["moveis"] if m["id"] == "cama"))


def test_modelo_sem_lugar_e_com_as_origens() -> None:
    cama = _cama()
    modelo = modelo_do_movel(cama)
    assert not DO_LUGAR & set(modelo)
    assert modelo["tipo"] == "cama"
    assert modelo["largura"] == cama.largura.model_dump(mode="json", exclude_none=True)
    novo = movel_do_modelo(modelo, "cama-2", (500, 600), 90, "Cama do hóspede")
    assert (novo["id"], novo["centro"], novo["rotacao"], novo["nome"]) == (
        "cama-2", [500, 600], 90, "Cama do hóspede"
    )  # fmt: skip
    assert novo["largura"]["origem"] == cama.largura.origem  # chute continua chute


def test_planejado_vai_junto() -> None:
    m: dict[str, Any] = {
        "id": "gab", "tipo": "sob_medida", "nome": "Gabinete", "centro": [0, 0],
        "largura": {"valor": 800, "origem": "projeto"},
        "profundidade": {"valor": 500, "origem": "projeto"},
        "altura": {"valor": 850, "origem": "projeto"},
        "forma": "arredondado", "raio": {"valor": 60, "origem": "projeto"},
    }  # fmt: skip
    modelo = modelo_do_movel(Movel.model_validate(m))
    assert modelo["forma"] == "arredondado" and modelo["raio"]["valor"] == 60
    assert Movel.model_validate(movel_do_modelo(modelo, "gab-2", (0, 0))).forma == "arredondado"


def test_adicionar_movel_a_partir_do_modelo() -> None:
    c = carregar(CASA)
    modelo = modelo_do_movel(_cama())
    ed = em.adicionar_movel(
        c.projeto, "quarto", c.dados_comodos.get("quarto"), "ignorado", centro=(1500, 1500),
        base=modelo,
    )  # fmt: skip
    novo = next(
        m for m in ed.dados.moveis if m.id not in {x.id for x in c.dados_comodos["quarto"].moveis}
    )
    assert novo.tipo == "cama" and novo.largura == _cama().largura and novo.id.startswith("cama")
    with pytest.raises(EdicaoInvalidaError, match="modelo inválido"):
        em.adicionar_movel(
            c.projeto, "quarto", c.dados_comodos.get("quarto"), "x", centro=(0, 0),
            base={"tipo": "cama"},
        )  # fmt: skip
