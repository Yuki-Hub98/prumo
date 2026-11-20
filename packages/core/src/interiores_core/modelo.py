"""Modelo do projeto: Projeto → Imóvel → Pavimento → (paredes, aberturas, estrutura,
instalações, cômodos).

Coordenadas são globais por pavimento, em mm inteiros, com o eixo y para cima
(origem num canto de referência do croqui). Cômodos não têm origem própria.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

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
    folha: Literal["giro", "correr", "camarao"] = "giro"
    """``camarao``: duas folhas que dobram para um lado (varre metade da largura)."""
    abre_para: str | None = Field(
        None,
        description="Cômodo (de/para) para onde a folha gira. Obrigatório se giro ou camarão.",
    )
    dobradica: Literal["inicio", "fim"] | None = Field(
        None, description="Lado do vão com a dobradiça, no sentido da parede."
    )
    estilo: Literal["lisa", "almofadada", "vidro", "veneziana"] | None = Field(
        None, description="Acabamento da folha (só visual); sem valor = lisa."
    )
    modelo: str | None = Field(
        None, description="Modelo do catálogo de portas de onde vieram as medidas."
    )


class Janela(_AberturaBase):
    """Janela com peitoril (altura do piso até o vão)."""

    tipo: Literal["janela"]
    peitoril: Medida
    abertura: Literal["correr", "basculante", "maxim_ar", "abrir", "fixa"] | None = Field(
        None, description="Como a janela abre; sem valor = de correr."
    )
    folhas: int | None = Field(
        None, ge=1, le=6, description="Número de folhas (correr/abrir); sem valor = 2."
    )
    modelo: str | None = Field(
        None, description="Modelo do catálogo de janelas de onde vieram as medidas."
    )


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


class Chapa(_Modelo):
    """Material de chapa (MDF, MDP, HDF...) e sua espessura."""

    material: str = Field(description='Ex.: "MDF branco", "MDP carvalho", "HDF branco".')
    espessura: Medida


class Espaco(_Modelo):
    """Espaço dentro de um vão, de baixo para cima.

    Entre dois espaços seguidos entra uma prateleira, exceto entre duas gavetas
    (que ficam empilhadas). ``altura`` é a altura livre do espaço (na gaveta, a
    altura da frente); se faltar, divide igualmente o que sobra no vão.
    """

    tipo: Literal["gaveta", "nicho", "cabideiro"]
    altura: Medida | None = None


class Vao(_Modelo):
    """Coluna do móvel entre duas divisórias (ou entre a lateral e uma divisória)."""

    largura: Medida | None = Field(
        None, description="Largura livre; se faltar, divide igualmente o que sobra."
    )
    espacos: list[Espaco] = Field(min_length=1, description="De baixo para cima.")
    porta: bool = Field(
        True, description="Com portas de abrir: se este vão tem porta (False = nicho aberto)."
    )


class Construcao(_Modelo):
    """Como o móvel planejado é construído por dentro (marcenaria em chapa).

    Caixa com laterais inteiras, base e tampo entre as laterais, divisórias entre a
    base e o tampo, fundo sobreposto, portas sobrepostas (de abrir, por vão) ou de
    correr (no móvel todo, conforme ``Movel.portas``) e gavetas com corrediça
    telescópica.
    """

    chapa: Chapa
    fundo: Chapa
    rodape: Medida | None = Field(None, description="Altura do rodapé (base recuada).")
    vaos: list[Vao] = Field(min_length=1, description="Da esquerda para a direita (de frente).")


AcabamentoMovel = Literal[
    "madeira_clara", "madeira_escura", "amadeirado", "branco_fosco", "laca_brilho", "preto_fosco"
]


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
    tipo: str = Field(
        description="Tipo do catálogo (cama, guarda_roupa, sofa, tv...); fora dele vira caixa."
    )
    modelo: str | None = Field(None, description="Modelo do catálogo de onde vieram as medidas.")
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
    portas: Literal["abrir", "correr"] | None = Field(
        None,
        description=(
            "Portas na frente do móvel (guarda-roupa, armário). Define o espaço livre "
            "exigido à frente: de abrir precisa de mais."
        ),
    )
    largura_porta: Medida | None = Field(
        None, description="Largura de cada folha de porta de abrir (para o espaço de giro)."
    )
    acabamento: AcabamentoMovel | None = Field(
        None, description="Material da caixa (só visual); sem valor = o padrão do tipo."
    )
    puxador: Literal["barra", "botao", "perfil", "cava"] | None = Field(
        None, description="Tipo de puxador das portas e gavetas (só visual); sem valor = barra."
    )
    pes: Literal["quadrado", "palito", "metalico", "rodape"] | None = Field(
        None, description="Tipo de pé (só visual); sem valor = o padrão do tipo."
    )
    elevacao: Medida | None = Field(
        None,
        description=(
            "Do piso até a base do móvel (TV na parede, armário aéreo). Móvel elevado "
            "não ocupa o piso: não conta para passagem nem para o giro de portas."
        ),
    )
    polegadas: int | None = Field(None, ge=10, le=150, description="Diagonal da tela (TV).")
    construcao: Construcao | None = Field(
        None, description="Móvel planejado: estrutura interna para desenho e lista de corte."
    )
    forma: Literal["arredondado", "redondo", "L"] | None = Field(
        None,
        description=(
            "Forma vista de cima (vazio = retangular): cantos arredondados (``raio``), redondo "
            "ou oval (círculo se largura = profundidade) ou em L (``braco``, ``lado_l``). "
            "Largura e profundidade continuam sendo a caixa em volta."
        ),
    )
    raio: Medida | None = Field(None, description="Raio dos cantos (forma arredondado).")
    braco: Medida | None = Field(
        None, description="Largura dos braços do L (forma L): a faixa das costas e a do lado."
    )
    lado_l: Literal["esquerda", "direita"] | None = Field(
        None,
        description="Lado do braço que vem para a frente, olhando de frente (padrão: esquerda).",
    )

    @model_validator(mode="after")
    def _forma_cabe(self) -> Movel:
        menor = min(self.largura.valor, self.profundidade.valor)
        if self.forma is not None and self.construcao is not None:
            raise ValueError("móvel planejado (com construção) só pode ser retangular")
        if self.forma == "arredondado" and self.raio and self.raio.valor * 2 > menor:
            raise ValueError(f"raio de {self.raio.valor} mm não cabe: no máximo {menor // 2} mm")
        if self.forma == "L" and self.braco and not 0 < self.braco.valor < menor:
            raise ValueError(
                f"braço do L de {self.braco.valor} mm: precisa ser menor que {menor} mm"
            )
        return self

    @property
    def ocupa_piso(self) -> bool:
        return self.elevacao is None or self.elevacao.valor == 0


class DadosComodo(_Modelo):
    """Raiz de ``comodos/<comodo>.json``: mobiliário e dados específicos."""

    schema_version: Literal[1]
    comodo: Id
    moveis: list[Movel] = Field(default_factory=list)


# ---------------------------------------------------------------- variacoes/<comodo>/*.json

Cor = Annotated[
    str, Field(pattern=r"^#[0-9a-fA-F]{6}$", description="Cor em hexadecimal: #RRGGBB.")
]


class CoresVariacao(_Modelo):
    """Paleta de uma variação. Tudo opcional: o que faltar usa a cor padrão."""

    parede: Cor | None = None
    """Cor geral das paredes do cômodo."""
    paredes: dict[str, Cor] = Field(
        default_factory=dict,
        description=(
            "Cor por parede (id), que substitui a geral: parede de destaque. Vale para a "
            "face voltada para este cômodo (a outra face é de outro cômodo)."
        ),
    )
    piso: Cor | None = None
    teto: Cor | None = None
    rodape: Cor | None = None
    moveis: dict[str, Cor] = Field(
        default_factory=dict,
        description="Cor por id de móvel ou por tipo (o id tem prioridade).",
    )
    pecas: dict[str, dict[str, Cor]] = Field(
        default_factory=dict,
        description=(
            'Cor por parte do móvel, por id ou tipo: {"guarda-roupa": {"portas": '
            '"#ffffff", "puxadores": "#222222"}} (o id tem prioridade). Partes: '
            "ver ``interiores_core.partes``; o que não tiver cor usa a do móvel."
        ),
    )


class Variacao(_Modelo):
    """Raiz de ``variacoes/<comodo>/<nome>.json``: uma alternativa de acabamento.

    Variações nunca alteram o ``projeto.json`` base (CLAUDE.md §7).
    """

    schema_version: Literal[1]
    comodo: Id
    nome: str | None = Field(None, description="Nome para exibir; o id é o nome do arquivo.")
    descricao: str | None = None
    cores: CoresVariacao = Field(default_factory=CoresVariacao)
