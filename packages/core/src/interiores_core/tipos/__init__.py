"""Módulos por tipo de cômodo (quarto, cozinha, ...), registrados por ``tipo``.

Cada tipo é um módulo ``tipos/<tipo>.py`` com:

- ``LIMITES``: padrões em mm, sobrescrevíveis na seção ``[<tipo>]`` do ``regras.toml``;
- ``REGRAS``: lista de funções ``(Contexto) -> None``.

O módulo é achado pelo nome do tipo: adicionar um tipo não exige mudar nada
fora do arquivo dele. Tipo sem módulo só passa pelas regras gerais.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from interiores_core.regras.contexto import Regra


class ModuloTipo(Protocol):
    LIMITES: Mapping[str, int]
    REGRAS: Sequence[Regra]


def modulo_do_tipo(tipo: str) -> ModuloTipo | None:
    """Módulo de regras do tipo, ou ``None`` se o tipo ainda não tiver um."""
    nome = f"{__name__}.{tipo}"
    try:
        return cast(ModuloTipo, importlib.import_module(nome))
    except ModuleNotFoundError as e:
        if e.name == nome:
            return None
        raise
