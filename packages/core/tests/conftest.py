"""Fixtures do core: o projeto de exemplo `casa` (quarto + banheiro, tudo estimado)."""

import copy
import json
from collections.abc import Callable
from typing import Any

import pytest
from apoio import CASA

from interiores_core.modelo import Projeto


@pytest.fixture
def casa_dict() -> dict[str, Any]:
    """projeto.json da casa como dict — cópia, pode mutar à vontade."""
    return copy.deepcopy(json.loads((CASA / "projeto.json").read_text(encoding="utf-8")))


@pytest.fixture
def montar(casa_dict: dict[str, Any]) -> Callable[[], Projeto]:
    """Valida o dict (depois de mutado pelo teste) e devolve o Projeto."""
    return lambda: Projeto.model_validate(casa_dict)
