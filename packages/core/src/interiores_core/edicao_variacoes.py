"""Variações de cor de um cômodo (``variacoes/<comodo>/<nome>.json``), em funções puras.

Variação nunca altera o projeto base (CLAUDE.md §7): é uma paleta à parte, uma por
nome, para comparar opções. Aqui só se valida; quem grava é o chamador.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from interiores_core.edicao import EdicaoInvalidaError
from interiores_core.modelo import Projeto, Variacao

NOME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
"""Nome da variação = nome do arquivo (``base`` é reservado: as cores padrão)."""


def validar_variacao(
    projeto: Projeto, comodo: str, nome: str, variacao: Variacao | Mapping[str, Any]
) -> Variacao:
    """Confere a variação de ``comodo`` e devolve o modelo.

    Recusa nome inválido ou ``base``, cômodo inexistente ou diferente do da variação
    e cor para parede que não delimita o cômodo (a cor por parede vale para a face
    voltada para ele).
    """
    pav = projeto.pavimento_do_comodo(comodo)
    if pav is None:
        raise KeyError(f"cômodo '{comodo}' não existe no projeto")
    if not NOME.match(nome) or nome == "base" or len(nome) > 64:
        raise EdicaoInvalidaError(
            f"nome de variação inválido: '{nome}' (minúsculas, números, - e _; 'base' é reservado)"
        )
    try:
        var = (
            variacao
            if isinstance(variacao, Variacao)
            else Variacao.model_validate({"schema_version": 1, "comodo": comodo, **variacao})
        )
    except ValidationError as e:
        raise EdicaoInvalidaError(f"dados inválidos: {e}") from e
    if var.comodo != comodo:
        raise EdicaoInvalidaError(f"a variação é do cômodo '{var.comodo}', não de '{comodo}'")
    c = pav.comodo(comodo)
    assert c is not None
    fora = sorted(set(var.cores.paredes) - set(c.paredes))
    if fora:
        raise EdicaoInvalidaError(
            f"parede(s) {', '.join(fora)} não delimitam '{comodo}' "
            f"(paredes dele: {', '.join(c.paredes)})"
        )
    return var
