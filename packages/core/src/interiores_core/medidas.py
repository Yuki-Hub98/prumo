"""Objeto de medida: toda dimensão do projeto carrega valor, origem e observação."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class Origem(StrEnum):
    """De onde veio a medida."""

    TRENA = "trena"
    """Medido no local."""
    ESTIMADA = "estimada"
    """Chute ou leitura de foto — torna o desenho PRELIMINAR."""
    PROJETO = "projeto"
    """Valor desejado ou decidido."""


Milimetros = Annotated[StrictInt, Field(ge=0, description="Valor inteiro em milímetros.")]


class Medida(BaseModel):
    """Medida em milímetros inteiros, sempre com origem.

    Exemplo: ``{"valor": 3150, "origem": "trena", "obs": "rodapé a rodapé"}``.
    Valores com casa decimal são recusados (unidade interna é mm inteiro).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    valor: Milimetros
    origem: Origem
    obs: str | None = None
    data: date | None = None

    @property
    def estimada(self) -> bool:
        """Se a medida torna o desenho preliminar."""
        return self.origem is Origem.ESTIMADA


def medidas_em(objeto: object, caminho: str = "") -> Iterator[tuple[str, Medida]]:
    """Percorre um modelo e devolve ``(caminho, medida)`` de toda Medida encontrada.

    O caminho usa ids quando o item tem ``id`` (ex.: ``paredes[p1].espessura``),
    para ser legível no carimbo dos desenhos.
    """
    if isinstance(objeto, Medida):
        yield caminho, objeto
    elif isinstance(objeto, BaseModel):
        for nome in type(objeto).model_fields:
            sub = f"{caminho}.{nome}" if caminho else nome
            yield from medidas_em(getattr(objeto, nome), sub)
    elif isinstance(objeto, list | tuple):
        for i, item in enumerate(objeto):
            chave = getattr(item, "id", i)
            yield from medidas_em(item, f"{caminho}[{chave}]")


def medidas_estimadas(objeto: object, caminho: str = "") -> list[tuple[str, Medida]]:
    """Só as medidas com ``origem == "estimada"``."""
    return [(c, m) for c, m in medidas_em(objeto, caminho) if m.estimada]
