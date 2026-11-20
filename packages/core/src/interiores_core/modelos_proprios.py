"""Modelos próprios: um móvel editado guardado para reaproveitar em outros cômodos/projetos.

O modelo é o móvel sem o que é do lugar onde ele estava (id, centro, giro). Medidas, forma,
portas e a montagem por dentro (planejado) vão junto, **com a origem que tinham** — um chute
continua chute no móvel novo (nada é inventado). Onde os modelos ficam guardados (banco) é
assunto da API; aqui é só a conversão.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from interiores_core.modelo import Movel

DO_LUGAR = frozenset({"id", "centro", "rotacao"})
"""Campos do móvel que dizem onde ele está, não o que ele é."""


def modelo_do_movel(movel: Movel) -> dict[str, Any]:
    """O móvel como modelo (sem posição); pronto para guardar como JSON."""
    dados = movel.model_dump(mode="json", exclude_none=True)
    return {k: v for k, v in dados.items() if k not in DO_LUGAR}


def movel_do_modelo(
    modelo: Mapping[str, Any],
    id_: str,
    centro: tuple[int, int],
    rotacao: int = 0,
    nome: str | None = None,
) -> dict[str, Any]:
    """Um móvel novo a partir do modelo, no lugar pedido (dict do JSON, já validado)."""
    dados = {k: copy.deepcopy(v) for k, v in modelo.items() if k not in DO_LUGAR}
    dados.update(id=id_, centro=list(centro), rotacao=rotacao)
    if nome:
        dados["nome"] = nome
    return Movel.model_validate(dados).model_dump(mode="json", exclude_none=True)
