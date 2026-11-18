"""Helpers dos testes do core."""

from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[3]
CASA = Path(__file__).resolve().parent / "dados" / "casa"
"""Cópia congelada do projeto de exemplo: editar ``projetos/casa`` (móveis, medidas)
não pode quebrar os testes. Atualize a cópia só quando o teste precisar."""


def pav(d: dict[str, Any]) -> dict[str, Any]:
    """Primeiro pavimento do dict do projeto."""
    return d["pavimentos"][0]  # type: ignore[no-any-return]


def item(lista: list[dict[str, Any]], id_: str) -> dict[str, Any]:
    """Item de uma lista pelo id."""
    return next(x for x in lista if x["id"] == id_)
