"""Formatos de pedido e resposta da API (o que não vem pronto dos modelos do core).

Medidas são sempre em **mm inteiros** e sempre com ``origem`` (a tela pergunta
"medi / quero assim / chute"): o modelo ``Medida`` do core recusa sem origem.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from interiores_core.medidas import Medida, Origem
from interiores_core.modelo import (
    Bancada,
    Comodo,
    Construcao,
    CoresVariacao,
    DadosComodo,
    Id,
    Janela,
    Laje,
    Parede,
    Pilar,
    Porta,
    Projeto,
    Variacao,
    Viga,
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


class Prisma3D(_Esquema):
    """Contorno na planta (mm) extrudado de ``z0`` a ``z1`` (paredes, piso, teto...)."""

    nome: str
    contorno: list[tuple[float, float]]
    z0: float
    z1: float
    material: str
    oculto_em: list[str] = Field(default_factory=list)
    extras: dict[str, str] = Field(default_factory=dict, description="movel e parte (pintura).")


class Caixa3D(_Esquema):
    """Paralelepípedo (peças de móvel, folhas de porta): centro e tamanho em mm, giro em z."""

    nome: str
    centro: tuple[float, float, float]
    tamanho: tuple[float, float, float]
    rotacao: float
    material: str
    chanfro: float = 0.0
    oculto_em: list[str] = Field(default_factory=list)
    extras: dict[str, str] = Field(default_factory=dict, description="movel e parte (pintura).")


class Material3D(_Esquema):
    cor: str
    rugosidade: float = 0.6
    textura: str | None = None
    metal: bool = False
    vidro: bool = False
    emissao: float | None = None


class Cena3D(_Esquema):
    """Cena calculada pelo core (a mesma que vai para o Blender, sem câmeras e luzes), para o
    visor montar o 3D ao vivo: muda junto com a planta, a cada versão (rascunho incluído)."""

    versao: int = Field(description="Versão do projeto desta cena.")
    prismas: list[Prisma3D]
    caixas: list[Caixa3D]
    materiais: dict[str, Material3D]
    aviso: str | None = None


class SuperficieTinta(_Esquema):
    comodo: str
    nome: str
    tinta: Literal["latex", "esmalte"]
    cor: str | None = Field(description="Hex da variação; null = cor padrão.")
    area_m2: float
    litros: float


class Lata(_Esquema):
    litros: float
    quantidade: int


class GrupoTinta(_Esquema):
    """Uma tinta numa cor: o que comprar."""

    tinta: Literal["latex", "esmalte"]
    cor: str | None
    area_m2: float
    litros: float
    latas: list[Lata]


class Tinta(_Esquema):
    """Cálculo de tinta do pavimento com as variações escolhidas em cada cômodo."""

    versao: int
    preliminar: bool = Field(
        description="Há medida estimada no pavimento: confira antes de comprar."
    )
    grupos: list[GrupoTinta]
    superficies: list[SuperficieTinta]
    parametros: dict[str, Any] = Field(description="Rendimento, demãos, perda e latas usados.")


class PedidoRenderPavimento(_Esquema):
    qualidade: Literal["rascunho", "final"] = Field(
        "rascunho", description="rascunho: segundos, para conferir; final: alguns minutos."
    )
    vistas: list[str] = Field(
        default_factory=lambda: ["perspectiva", "superior"],
        min_length=1,
        description="Câmeras: perspectiva (aérea) e superior (de cima), as duas sem teto.",
    )


class Vista(_Esquema):
    nome: str
    titulo: str


class InfoRender(_Esquema):
    id: int
    escopo: Literal["comodo", "pavimento"] = Field(
        "comodo", description="pavimento: a casa inteira do pavimento (id em ``comodo``)."
    )
    comodo: str = Field(description="Id do cômodo (ou do pavimento, no escopo pavimento).")
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
    modelo_url: str | None = Field(
        None, description="Modelo 3D do cômodo ou do pavimento (.glb), se pronto."
    )


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


class InfoRascunho(_Esquema):
    desde: int = Field(description="Versão salva onde o rascunho começou.")
    passos: int = Field(description="Mudanças ainda não salvas.")
    refazer: bool = Field(description="Há passo desfeito para refazer.")


class Versoes(_Esquema):
    atual: int
    desfazer: int | None = Field(description="Versão que o desfazer restaura (None: nada).")
    refazer: int | None = Field(description="Versão que o refazer restaura (None: nada).")
    versoes: list[ResumoVersao] = Field(description="Da mais nova para a mais velha.")
    rascunho: InfoRascunho | None = Field(
        None, description="Rascunho aberto (mudanças não salvas), se houver."
    )


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
    modelo_proprio: str | None = Field(
        None,
        description="Código de um modelo próprio: o móvel sai igual a ele (``tipo`` é ignorado).",
    )


class NovoModeloProprio(_Esquema):
    """Guardar um móvel de um projeto como modelo próprio."""

    projeto: str
    comodo: str
    movel: str
    nome: str = Field(min_length=1, max_length=120)


class ModeloProprioResumo(_Esquema):
    codigo: str
    nome: str
    tipo: str
    largura: int
    profundidade: int
    altura: int
    planejado: bool
    """Tem montagem por dentro (gavetas, prateleiras...)."""
    estimadas: int
    """Quantas medidas do modelo são chute (vão assim para o móvel novo)."""


class DefinirConstrucao(_Esquema):
    """Como o móvel é montado por dentro (planejado); ``null`` tira a construção."""

    construcao: Construcao | None


class DefinirBancada(_Esquema):
    """Tampo, pernas e módulos da bancada/mesa planejada; ``null`` tira (fica só a forma)."""

    bancada: Bancada | None


class RedimensionarMovel(_Esquema):
    """Arrastar um lado do móvel: o lado oposto fica parado; a medida vira "Quero assim"."""

    lado: Literal["esquerda", "direita", "frente", "costas"]
    tamanho: int = Field(gt=0, description="mm: largura (esquerda/direita) ou profundidade")


class MoverMovel(_Esquema):
    """Arrastar (``centro``), girar (``rotacao``) ou prender numa ``parede``."""

    centro: tuple[int, int] | None = None
    rotacao: Literal[0, 90, 180, 270] | None = None
    parede: str | None = None
    distancia: int = Field(0, ge=0)


NovaAbertura = Porta | Janela
NovaEstrutura = Annotated[Pilar | Viga | Laje, Field(discriminator="tipo")]

__all__ = [
    "AdicionarPavimento",
    "AlterarComodo",
    "AlterarInstalacao",
    "AlterarParede",
    "Apagado",
    "Campos",
    "DefinirConstrucao",
    "DividirParede",
    "InfoRender",
    "ItemHistorico",
    "MedidaEstimada",
    "ModeloProprioResumo",
    "MoverMovel",
    "MoverVertice",
    "Mudanca",
    "NovaAbertura",
    "NovaEstrutura",
    "NovaInstalacao",
    "NovaVariacao",
    "NovoComodo",
    "NovoModeloProprio",
    "NovoMovel",
    "NovoPavimento",
    "NovoProjeto",
    "Parede",
    "PedidoRender",
    "Preferencias",
    "ProjetoCompleto",
    "RedimensionarMovel",
    "Renomear",
    "ResultadoEdicao",
    "ResumoProjeto",
    "ResumoVersao",
    "Versoes",
    "Vista",
]
