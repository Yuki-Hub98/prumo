"""Modelo do projeto: Projeto → Imóvel → Pavimento → (paredes, aberturas, estrutura,
instalações, cômodos).

Coordenadas são globais por pavimento, em mm inteiros, com o eixo y para cima
(origem num canto de referência do croqui). Cômodos não têm origem própria.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from interiores_core.medidas import Medida

SCHEMA_VERSION = 1
EXTERNO = "externo"
"""Valor de lado de parede / destino de porta que não é um cômodo modelado."""

Id = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]*$", max_length=64)]
Ponto = tuple[StrictInt, StrictInt]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- paredes


class Parede(_Modelo):
    """Parede como entidade própria, compartilhada entre cômodos.

    ``lado_a`` é o cômodo à **esquerda** de quem anda de ``inicio`` para ``fim``;
    ``lado_b``, o da direita. Use ``"externo"`` quando não houver cômodo modelado.
    """

    id: Id
    inicio: Ponto
    fim: Ponto
    espessura: Medida
    lado_a: str
    lado_b: str
    altura: Medida | None = Field(None, description="Se omitida, vale o pé-direito.")


# ---------------------------------------------------------------- aberturas


class _AberturaBase(_Modelo):
    id: Id
    parede: str
    distancia_inicio: Medida = Field(description="Do início da parede até o vão.")
    largura: Medida
    altura: Medida


class Porta(_AberturaBase):
    """Porta: liga dois cômodos e tem sentido de abertura."""

    tipo: Literal["porta"]
    de: str
    para: str
    folha: Literal["giro", "correr"] = "giro"
    abre_para: str | None = Field(
        None, description="Cômodo (de/para) para onde a folha gira. Obrigatório se giro."
    )
    dobradica: Literal["inicio", "fim"] | None = Field(
        None, description="Lado do vão com a dobradiça, no sentido da parede."
    )


class Janela(_AberturaBase):
    """Janela com peitoril (altura do piso até o vão)."""

    tipo: Literal["janela"]
    peitoril: Medida


Abertura = Annotated[Porta | Janela, Field(discriminator="tipo")]


# ---------------------------------------------------------------- estrutura


class Pilar(_Modelo):
    id: Id
    tipo: Literal["pilar"]
    centro: Ponto
    largura: Medida = Field(description="Dimensão em x.")
    profundidade: Medida = Field(description="Dimensão em y.")


class Viga(_Modelo):
    id: Id
    tipo: Literal["viga"]
    inicio: Ponto
    fim: Ponto
    largura: Medida
    altura: Medida = Field(description="Quanto a viga desce abaixo da laje.")


ElementoEstrutural = Annotated[Pilar | Viga, Field(discriminator="tipo")]


# ---------------------------------------------------------------- instalações


class TipoInstalacao(StrEnum):
    TOMADA = "tomada"
    INTERRUPTOR = "interruptor"
    PONTO_LUZ = "ponto_luz"
    AGUA_FRIA = "agua_fria"
    AGUA_QUENTE = "agua_quente"
    ESGOTO = "esgoto"
    RALO = "ralo"
    GAS = "gas"


class PontoInstalacao(_Modelo):
    """Ponto (tomada, interruptor, saída de água...) com altura do piso."""

    id: Id
    forma: Literal["ponto"]
    tipo: TipoInstalacao
    posicao: Ponto
    altura: Medida
    parede: str | None = None
    comodo: str | None = Field(
        None,
        description=(
            "Cômodo atendido pelo ponto. Obrigatório em parede entre dois cômodos: "
            "diz de que lado da parede ele fica."
        ),
    )
    obs: str | None = None


class TrechoInstalacao(_Modelo):
    """Trecho de tubulação/eletroduto. Se embutido, gera faixa de "não furar"."""

    id: Id
    forma: Literal["trecho"]
    tipo: TipoInstalacao
    caminho: list[Ponto] = Field(min_length=2)
    altura: Medida
    embutido: bool = True
    obs: str | None = None


Instalacao = Annotated[PontoInstalacao | TrechoInstalacao, Field(discriminator="forma")]


# ---------------------------------------------------------------- cômodos


class TipoComodo(StrEnum):
    QUARTO = "quarto"
    SALA = "sala"
    COZINHA = "cozinha"
    BANHEIRO = "banheiro"
    LAVABO = "lavabo"
    AREA_SERVICO = "area_servico"
    ESCRITORIO = "escritorio"
    CORREDOR = "corredor"
    VARANDA = "varanda"
    GARAGEM = "garagem"
    OUTRO = "outro"


class Comodo(_Modelo):
    """Cômodo: polígono derivado das paredes que o delimitam (não digitado à parte)."""

    id: Id
    nome: str
    tipo: TipoComodo
    paredes: list[str] = Field(min_length=3)
    piso: str | None = Field(None, description="Acabamento do piso.")
    teto: str | None = Field(None, description="Acabamento do teto.")
    pe_direito: Medida | None = Field(None, description="Se omitido, vale o do pavimento.")


# ---------------------------------------------------------------- pavimento / imóvel


class Pavimento(_Modelo):
    id: Id
    nome: str | None = None
    cota_piso: Medida
    pe_direito: Medida
    rodape: Medida | None = Field(None, description="Altura do rodapé.")
    paredes: list[Parede] = Field(default_factory=list)
    aberturas: list[Abertura] = Field(default_factory=list)
    estrutura: list[ElementoEstrutural] = Field(default_factory=list)
    instalacoes: list[Instalacao] = Field(default_factory=list)
    comodos: list[Comodo] = Field(default_factory=list)

    def parede(self, id_: str) -> Parede | None:
        return next((p for p in self.paredes if p.id == id_), None)

    def comodo(self, id_: str) -> Comodo | None:
        return next((c for c in self.comodos if c.id == id_), None)


class Imovel(_Modelo):
    tipo: Literal["casa", "apartamento"]
    endereco_apelido: str | None = None


class Projeto(_Modelo):
    """Raiz do ``projeto.json``."""

    schema_version: Literal[1]
    projeto: Id
    imovel: Imovel
    pavimentos: list[Pavimento] = Field(min_length=1)

    def pavimento_do_comodo(self, comodo_id: str) -> Pavimento | None:
        return next((p for p in self.pavimentos if p.comodo(comodo_id)), None)


# ---------------------------------------------------------------- comodos/<id>.json


class Movel(_Modelo):
    """Móvel posicionado pelo centro, com rotação em graus (sentido anti-horário).

    Convenção de orientação: com ``rotacao: 0`` o móvel tem as **costas para -y**
    (para baixo na planta) e a **frente para +y**. A largura corre em x e a
    profundidade em y. A rotação gira o móvel em torno do centro, então a frente
    aponta para: 0 → +y, 90 → -x, 180 → -y, 270 → +x.

    "Costas" é o lado que encosta na parede: cabeceira da cama, fundo do
    guarda-roupa. "Frente" é o lado de uso: pés da cama, portas do guarda-roupa.
    """

    id: Id
    tipo: str = Field(description="cama, guarda_roupa, criado_mudo, ...")
    nome: str | None = None
    centro: Ponto
    rotacao: Literal[0, 90, 180, 270] = Field(
        0,
        description=(
            "Graus, anti-horário. Em 0 as costas ficam para -y e a frente para +y; "
            "a frente aponta para 0: +y, 90: -x, 180: -y, 270: +x."
        ),
    )
    largura: Medida = Field(description="Dimensão ao longo do eixo x antes da rotação.")
    profundidade: Medida = Field(
        description="Dimensão de costas a frente (eixo y antes da rotação)."
    )
    altura: Medida


class DadosComodo(_Modelo):
    """Raiz de ``comodos/<comodo>.json``: mobiliário e dados específicos."""

    schema_version: Literal[1]
    comodo: Id
    moveis: list[Movel] = Field(default_factory=list)
