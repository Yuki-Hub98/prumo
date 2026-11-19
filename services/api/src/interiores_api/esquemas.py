"""Formatos de pedido e resposta da API (o que não vem pronto dos modelos do core).

Medidas são sempre em **mm inteiros** e sempre com ``origem`` (a tela pergunta
"medi / quero assim / chute"): o modelo ``Medida`` do core recusa sem origem.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from interiores_core.medidas import Medida, Origem
from interiores_core.modelo import (
    Comodo,
    DadosComodo,
    Id,
    Janela,
    Parede,
    Porta,
    Projeto,
    Variacao,
)
from interiores_core.validacao import Problema


class _Esquema(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- projetos


class ResumoProjeto(_Esquema):
    codigo: str
    versao: int
    imovel: str
    apelido: str | None = None


class NovoPavimento(_Esquema):
    id: Id = "terreo"
    nome: str | None = "Térreo"
    pe_direito: Medida
    cota_piso: Medida = Medida(valor=0, origem=Origem.PROJETO, obs="referência do pavimento")


class NovoProjeto(_Esquema):
    """Projeto vazio (um pavimento, sem paredes), para desenhar do zero."""

    codigo: Id
    imovel: Literal["casa", "apartamento"]
    apelido: str | None = None
    pavimento: NovoPavimento


class ProjetoCompleto(_Esquema):
    versao: int
    projeto: Projeto
    comodos: dict[str, DadosComodo]
    variacoes: dict[str, dict[str, Variacao]]


class Mudanca(_Esquema):
    caminho: str
    antes: Any = None
    depois: Any = None


class ItemHistorico(Mudanca):
    versao: int
    quando: str
    fonte: str
    operacao: str | None = None


class MedidaEstimada(_Esquema):
    caminho: str
    pavimento: str | None
    comodo: str | None
    entidade: str
    entidade_codigo: str | None
    campo: str
    valor: int
    obs: str | None


# ---------------------------------------------------------------- edição


class ResultadoEdicao(_Esquema):
    versao: int
    """Versão nova; mande-a na próxima edição (``?versao=``)."""
    alteracoes: list[Mudanca]
    novos: list[Problema] = Field(description="Problemas que esta edição introduziu.")
    problemas: list[Problema] = Field(description="Todos os problemas estruturais agora.")


Campos = dict[str, Any]
"""Campos a mudar (PATCH). ``null`` apaga o campo; medidas como ``{valor, origem}``."""


class AlterarParede(_Esquema):
    campos: Campos
    arrastar_vizinhas: bool = True


class DividirParede(_Esquema):
    distancia: int = Field(gt=0, description="mm do início da parede até o corte")
    novo_id: Id | None = None


class MoverVertice(_Esquema):
    de: tuple[int, int]
    para: tuple[int, int]


class NovaInstalacao(_Esquema):
    instalacao: dict[str, Any] = Field(
        description=(
            "Ponto (``forma: ponto``, como PontoInstalacao) ou trecho (``forma: trecho``). "
            "Ponto em parede pode vir sem ``posicao`` se ``distancia`` for informada."
        ),
        json_schema_extra={"anyOf": [{"$ref": "#/components/schemas/PontoInstalacao"},
                                     {"$ref": "#/components/schemas/TrechoInstalacao"}]},
    )  # fmt: skip
    distancia: int | None = Field(None, ge=0, description="mm do início da parede (ponto)")


class AlterarInstalacao(_Esquema):
    campos: Campos
    distancia: int | None = Field(None, ge=0)


class AlterarComodo(_Esquema):
    campos: Campos
    ajustar_lados: bool = True


class NovoComodo(_Esquema):
    comodo: Comodo
    ajustar_lados: bool = True


NovaAbertura = Porta | Janela

__all__ = [
    "AlterarComodo",
    "AlterarInstalacao",
    "AlterarParede",
    "Campos",
    "DividirParede",
    "ItemHistorico",
    "MedidaEstimada",
    "MoverVertice",
    "Mudanca",
    "NovaAbertura",
    "NovaInstalacao",
    "NovoComodo",
    "NovoPavimento",
    "NovoProjeto",
    "Parede",
    "ProjetoCompleto",
    "ResultadoEdicao",
    "ResumoProjeto",
]
