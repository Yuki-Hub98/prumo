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
    CoresVariacao,
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


class AdicionarPavimento(_Esquema):
    pavimento: NovoPavimento
    depois_de: str | None = Field(None, description="Id do pavimento anterior (padrão: no fim).")


class Renomear(_Esquema):
    codigo: Id


class Apagado(_Esquema):
    codigo: str
    pasta_movida_para: str | None = Field(
        description="A pasta não é apagada: vai para projetos/_apagados/ (fotos, croquis)."
    )


class Preferencias(_Esquema):
    """Preferências do usuário (por ora um só; com login, uma por pessoa)."""

    unidade: Literal["mm", "cm", "m"] = Field(
        "cm", description="Unidade em que a tela mostra e recebe medidas (a API é sempre mm)."
    )


class NovaVariacao(_Esquema):
    """Paleta de um cômodo: ``cores.parede`` (geral), ``cores.paredes`` (por parede, a
    face voltada para o cômodo), ``piso``, ``teto``, ``rodape`` e ``moveis`` (por id ou
    tipo). O que faltar usa a cor padrão."""

    nome: str | None = Field(None, description="Nome para exibir (ex.: Escura).")
    descricao: str | None = None
    cores: CoresVariacao = Field(default_factory=CoresVariacao)


class PedidoRender(_Esquema):
    variacao: str = Field("base", description="'base' (cores padrão) ou o nome da variação.")
    qualidade: Literal["rascunho", "final"] = Field(
        "rascunho", description="rascunho: segundos, para conferir; final: ~2 min."
    )
    vistas: list[str] = Field(
        default_factory=lambda: ["perspectiva", "superior"],
        min_length=1,
        description="Câmeras (ver GET .../vistas): perspectiva, porta, cama, canto-N, superior.",
    )


class Vista(_Esquema):
    nome: str
    titulo: str


class InfoRender(_Esquema):
    id: int
    comodo: str
    variacao: str
    qualidade: str
    vistas: list[str]
    status: Literal["na_fila", "rodando", "pronto", "erro"]
    progresso: float = Field(description="0 a 1")
    imagem_atual: int | None
    imagens: int
    estimativa_s: float | None = Field(description="Estimativa feita ao pedir (histórico).")
    restante_s: float | None = Field(description="Quanto falta, pelo ritmo real ou estimativa.")
    decorrido_s: float | None
    duracao_s: float | None = Field(description="Tempo real do Blender (pronto).")
    em_cache: bool
    versao_projeto: int
    criado_em: str
    erro: str | None
    imagens_url: list[str] = Field(description="Caminhos das imagens (pronto).")


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


class ResumoVersao(_Esquema):
    versao: int
    quando: str
    operacao: str | None = None
    tipo: str | None = Field(None, description="desfazer | refazer | reverter, se for uma volta.")
    para: int | None = Field(None, description="Versão cujo conteúdo foi restaurado.")
    alteracoes: int = Field(description="Quantas alterações a versão gravou.")
    caminhos: list[str] = Field(description="Até 5 caminhos alterados (resumo).")


class Versoes(_Esquema):
    atual: int
    desfazer: int | None = Field(description="Versão que o desfazer restaura (None: nada).")
    refazer: int | None = Field(description="Versão que o refazer restaura (None: nada).")
    versoes: list[ResumoVersao] = Field(description="Da mais nova para a mais velha.")


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


class NovoMovel(_Esquema):
    """Móvel do catálogo. Posição: ``centro`` (+ ``rotacao``) **ou** ``parede`` (+ ``distancia``).

    Medidas do catálogo entram como ``estimada``; as de ``medidas`` substituem com
    a origem que a pessoa escolheu.
    """

    tipo: str
    modelo: str | None = None
    id: Id | None = None
    nome: str | None = None
    centro: tuple[int, int] | None = None
    rotacao: Literal[0, 90, 180, 270] | None = None
    parede: str | None = None
    distancia: int = Field(0, ge=0, description="mm do início da parede até a borda do móvel")
    medidas: dict[str, Medida] = Field(
        default_factory=dict, description="largura, profundidade, altura, elevacao, largura_porta"
    )


class MoverMovel(_Esquema):
    """Arrastar (``centro``), girar (``rotacao``) ou prender numa ``parede``."""

    centro: tuple[int, int] | None = None
    rotacao: Literal[0, 90, 180, 270] | None = None
    parede: str | None = None
    distancia: int = Field(0, ge=0)


NovaAbertura = Porta | Janela

__all__ = [
    "AdicionarPavimento",
    "AlterarComodo",
    "AlterarInstalacao",
    "AlterarParede",
    "Apagado",
    "Campos",
    "DividirParede",
    "InfoRender",
    "ItemHistorico",
    "MedidaEstimada",
    "MoverMovel",
    "MoverVertice",
    "Mudanca",
    "NovaAbertura",
    "NovaInstalacao",
    "NovaVariacao",
    "NovoComodo",
    "NovoMovel",
    "NovoPavimento",
    "NovoProjeto",
    "Parede",
    "PedidoRender",
    "Preferencias",
    "ProjetoCompleto",
    "Renomear",
    "ResultadoEdicao",
    "ResumoProjeto",
    "ResumoVersao",
    "Versoes",
    "Vista",
]
