"""Exportação do JSON Schema oficial (usado pelo frontend e por editores)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from interiores_core import catalogo
from interiores_core.modelo import DadosComodo, Projeto

SCHEMAS: dict[str, type[BaseModel]] = {
    "projeto.schema.json": Projeto,
    "comodo.schema.json": DadosComodo,
}


def exportar(pasta: Path | str) -> list[Path]:
    """Grava os schemas e o catálogo de móveis em ``pasta``; devolve os caminhos gravados."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    gravados = []
    for nome, modelo in SCHEMAS.items():
        caminho = pasta / nome
        schema = modelo.model_json_schema()
        caminho.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        gravados.append(caminho)
    caminho = pasta / "catalogo.json"
    caminho.write_text(
        json.dumps(catalogo.exportar(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    gravados.append(caminho)
    return gravados
