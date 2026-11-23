"""Catálogo de móveis: tipos, modelos com medidas padrão, lados de uso e símbolo.

As medidas do catálogo são **padrões de mercado** (mm). Ao entrar num projeto,
viram ``Medida`` com ``origem: "estimada"`` e uma ``obs`` dizendo de qual modelo
vieram, para o usuário ajustar depois (CLAUDE.md §4).

O catálogo é exportado em JSON (``schema/catalogo.json``) para o frontend montar
o editor de móveis. Tipo fora do catálogo continua aceito no projeto: é
desenhado como caixa genérica e usa só a frente.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Lado = Literal["frente", "costas", "esquerda", "direita"]
"""Lados do móvel no referencial dele (rotação 0: costas em -y, frente em +y)."""


class Categoria(StrEnum):
    DORMIR = "dormir"
    GUARDAR = "guardar"
    SENTAR = "sentar"
    MESAS = "mesas"
    ELETRONICOS = "eletronicos"
    COZINHA = "cozinha"
    BANHEIRO = "banheiro"
    AREA_SERVICO = "area_servico"
    SOB_MEDIDA = "sob_medida"


class Simbolo(StrEnum):
    """Como o móvel é desenhado na planta."""

    CAMA = "cama"
    PORTAS = "portas"
    """Linha das portas na frente (guarda-roupa, armário)."""
    ASSENTO = "assento"
    """Encosto nas costas e braços nas laterais (sofá, poltrona)."""
    CADEIRA = "cadeira"
    TELA = "tela"
    GAVETAS = "gavetas"
    MESA = "mesa"
    PRATELEIRAS = "prateleiras"
    GENERICO = "generico"
    """Caixa com seta na frente."""
    PIA = "pia"
    """Gabinete com bancada, cuba e torneira."""
    FOGAO = "fogao"
    """Bocas em cima (e forno na frente, se for de piso)."""
    GELADEIRA = "geladeira"
    VASO = "vaso"
    """Bacia (arredondada na frente) e caixa acoplada atrás."""
    BOX = "box"
    """Área do chuveiro com o vidro na frente."""
    BELICHE = "beliche"
    """Duas camas empilhadas com escada."""
    CADEIRA_GIRATORIA = "cadeira_giratoria"
    """Cadeira de escritório: assento redondo e base em estrela."""
    MAQUINA = "maquina"
    """Máquina de lavar (abertura frontal redonda)."""


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModeloCatalogo(_Base):
    """Um modelo de um tipo de móvel, com as medidas padrão em mm."""

    id: str
    nome: str
    largura: int = Field(description="mm, ao longo do x local (de lado a lado).")
    profundidade: int = Field(description="mm, de costas a frente.")
    altura: int = Field(description="mm.")
    elevacao: int | None = Field(None, description="mm do piso até a base (TV na parede).")
    portas: Literal["abrir", "correr"] | None = None
    largura_porta: int | None = None
    polegadas: int | None = Field(None, description="Diagonal da tela (TV).")
    energia: Literal["gas", "eletrico"] | None = Field(
        None, description="Fogão: a gás pede ponto de gás e ventilação."
    )
    forma: Literal["arredondado", "redondo", "L"] | None = Field(
        None, description="Forma do móvel (mesa redonda...); sem valor = retângulo."
    )


class ItemCatalogo(_Base):
    """Um tipo de móvel."""

    tipo: str
    nome: str
    categoria: Categoria
    simbolo: Simbolo
    lados_uso: tuple[Lado, ...] = Field(
        description=(
            "Lados por onde o móvel é usado; a checagem de passagem exige que pelo menos "
            "um seja alcançável. Vazio: não precisa de acesso (ex.: TV na parede)."
        )
    )
    assento: bool = Field(False, description="Lugar de onde se assiste TV (sofá, cama...).")
    modelos: tuple[ModeloCatalogo, ...]
    modelo_padrao: str

    def modelo(self, id_: str | None = None) -> ModeloCatalogo | None:
        alvo = id_ or self.modelo_padrao
        return next((m for m in self.modelos if m.id == alvo), None)


def _m(id_: str, nome: str, larg: int, prof: int, alt: int, **extra: Any) -> ModeloCatalogo:
    return ModeloCatalogo(id=id_, nome=nome, largura=larg, profundidade=prof, altura=alt, **extra)


def _tv(pol: int, largura: int, altura: int) -> ModeloCatalogo:
    return _m(f"{pol}pol", f'{pol}"', largura, 80, altura, polegadas=pol, elevacao=1000)


_ITENS = (
    # ------------------------------------------------------------ dormir
    ItemCatalogo(
        tipo="cama",
        nome="Cama",
        categoria=Categoria.DORMIR,
        simbolo=Simbolo.CAMA,
        lados_uso=("esquerda", "direita", "frente"),
        assento=True,
        modelos=(
            _m("solteiro", "Solteiro (88 × 188)", 880, 1880, 550),
            _m("viuva", "Viúva (128 × 188)", 1280, 1880, 550),
            _m("casal", "Casal (138 × 188)", 1380, 1880, 550),
            _m("queen", "Queen (158 × 198)", 1580, 1980, 550),
            _m("king", "King (193 × 203)", 1930, 2030, 550),
        ),
        modelo_padrao="casal",
    ),
    ItemCatalogo(
        tipo="berco",
        nome="Berço",
        categoria=Categoria.DORMIR,
        simbolo=Simbolo.GENERICO,
        lados_uso=("frente",),
        modelos=(_m("padrao", "Padrão (70 × 130)", 700, 1300, 1000),),
        modelo_padrao="padrao",
    ),
    ItemCatalogo(
        tipo="criado_mudo",
        nome="Criado-mudo",
        categoria=Categoria.DORMIR,
        simbolo=Simbolo.GAVETAS,
        lados_uso=("frente",),
        modelos=(
            _m("padrao", "Padrão (45 × 40)", 450, 400, 550),
            _m("pequeno", "Pequeno (35 × 30)", 350, 300, 500),
        ),
        modelo_padrao="padrao",
    ),
    # ------------------------------------------------------------ guardar
    ItemCatalogo(
        tipo="guarda_roupa",
        nome="Guarda-roupa",
        categoria=Categoria.GUARDAR,
        simbolo=Simbolo.PORTAS,
        lados_uso=("frente",),
        modelos=(
            _m("2_portas", "2 portas de abrir", 900, 550, 2100, portas="abrir", largura_porta=450),
            _m("4_portas", "4 portas de abrir", 1600, 550, 2300, portas="abrir", largura_porta=400),
            _m("correr_2", "2 portas de correr", 1800, 600, 2300, portas="correr"),
            _m("correr_3", "3 portas de correr", 2400, 600, 2400, portas="correr"),
        ),
        modelo_padrao="correr_2",
    ),
    ItemCatalogo(
        tipo="armario",
        nome="Armário",
        categoria=Categoria.GUARDAR,
        simbolo=Simbolo.PORTAS,
        lados_uso=("frente",),
        modelos=(
            _m("baixo", "Baixo (80 × 40)", 800, 400, 850, portas="abrir", largura_porta=400),
            _m("alto", "Alto (80 × 40)", 800, 400, 1800, portas="abrir", largura_porta=400),
            _m(
                "aereo",
                "Aéreo (80 × 35)",
                800,
                350,
                700,
                portas="abrir",
                largura_porta=400,
                elevacao=1500,
            ),
        ),
        modelo_padrao="alto",
    ),
    ItemCatalogo(
        tipo="comoda",
        nome="Cômoda",
        categoria=Categoria.GUARDAR,
        simbolo=Simbolo.GAVETAS,
        lados_uso=("frente",),
        modelos=(_m("padrao", "Padrão (100 × 50)", 1000, 500, 900),),
        modelo_padrao="padrao",
    ),
    ItemCatalogo(
        tipo="estante",
        nome="Estante",
        categoria=Categoria.GUARDAR,
        simbolo=Simbolo.PRATELEIRAS,
        lados_uso=("frente",),
        modelos=(
            _m("padrao", "Padrão (90 × 35)", 900, 350, 1800),
            _m("baixa", "Baixa (90 × 35)", 900, 350, 900),
        ),
        modelo_padrao="padrao",
    ),
    ItemCatalogo(
        tipo="sapateira",
        nome="Sapateira",
        categoria=Categoria.GUARDAR,
        simbolo=Simbolo.PORTAS,
        lados_uso=("frente",),
        modelos=(
            _m("padrao", "Padrão (70 × 35)", 700, 350, 1000, portas="abrir", largura_porta=350),
        ),
        modelo_padrao="padrao",
    ),
    # ------------------------------------------------------------ sentar
    ItemCatalogo(
        tipo="sofa",
        nome="Sofá",
        categoria=Categoria.SENTAR,
        simbolo=Simbolo.ASSENTO,
        lados_uso=("frente",),
        assento=True,
        modelos=(
            _m("2_lugares", "2 lugares", 1600, 900, 850),
            _m("3_lugares", "3 lugares", 2100, 900, 850),
            _m("retratil", "Retrátil (fechado)", 2300, 1000, 950),
            _m("canto", "De canto em L (260 × 160)", 2600, 1600, 850, forma="L"),
        ),
        modelo_padrao="3_lugares",
    ),
    ItemCatalogo(
        tipo="poltrona",
        nome="Poltrona",
        categoria=Categoria.SENTAR,
        simbolo=Simbolo.ASSENTO,
        lados_uso=("frente",),
        assento=True,
        modelos=(_m("padrao", "Padrão (80 × 80)", 800, 800, 900),),
        modelo_padrao="padrao",
    ),
    ItemCatalogo(
        tipo="cadeira",
        nome="Cadeira",
        categoria=Categoria.SENTAR,
        simbolo=Simbolo.CADEIRA,
        lados_uso=("frente",),
        modelos=(
            _m("padrao", "Padrão (45 × 50)", 450, 500, 900),
            _m("escritorio", "Escritório (65 × 65)", 650, 650, 1100),
        ),
        modelo_padrao="padrao",
    ),
    ItemCatalogo(
        tipo="banco",
        nome="Banco / puff",
        categoria=Categoria.SENTAR,
        simbolo=Simbolo.GENERICO,
        lados_uso=("frente",),
        modelos=(
            _m("puff", "Puff (40 × 40)", 400, 400, 450),
            _m("peseira", "Peseira (120 × 40)", 1200, 400, 450),
        ),
        modelo_padrao="puff",
    ),
    # ------------------------------------------------------------ mesas
    ItemCatalogo(
        tipo="mesa",
        nome="Mesa",
        categoria=Categoria.MESAS,
        simbolo=Simbolo.MESA,
        lados_uso=("frente", "costas", "esquerda", "direita"),
        modelos=(
            _m("4_lugares", "Jantar 4 lugares", 1200, 800, 750),
            _m("6_lugares", "Jantar 6 lugares", 1600, 900, 750),
            _m("redonda_4", "Jantar redonda 4 lugares (Ø 100)", 1000, 1000, 750, forma="redondo"),
            _m("redonda_6", "Jantar redonda 6 lugares (Ø 120)", 1200, 1200, 750, forma="redondo"),
            _m("centro", "Centro", 1000, 600, 400),
            _m("lateral", "Lateral (Ø 45)", 450, 450, 550, forma="redondo"),
        ),
        modelo_padrao="4_lugares",
    ),
    ItemCatalogo(
        tipo="escrivaninha",
        nome="Escrivaninha",
        categoria=Categoria.MESAS,
        simbolo=Simbolo.MESA,
        lados_uso=("frente",),
        modelos=(
            _m("padrao", "Padrão (120 × 60)", 1200, 600, 750),
            _m("compacta", "Compacta (90 × 45)", 900, 450, 750),
        ),
        modelo_padrao="padrao",
    ),
    ItemCatalogo(
        tipo="penteadeira",
        nome="Penteadeira",
        categoria=Categoria.MESAS,
        simbolo=Simbolo.GAVETAS,
        lados_uso=("frente",),
        modelos=(_m("padrao", "Padrão (100 × 45)", 1000, 450, 780),),
        modelo_padrao="padrao",
    ),
    # ------------------------------------------------------------ eletrônicos
    ItemCatalogo(
        tipo="tv",
        nome="TV",
        categoria=Categoria.ELETRONICOS,
        simbolo=Simbolo.TELA,
        lados_uso=(),
        modelos=(
            _tv(32, 730, 430),
            _tv(43, 970, 570),
            _tv(50, 1120, 650),
            _tv(55, 1230, 710),
            _tv(65, 1450, 840),
        ),
        modelo_padrao="50pol",
    ),
    ItemCatalogo(
        tipo="rack",
        nome="Rack / painel",
        categoria=Categoria.ELETRONICOS,
        simbolo=Simbolo.GAVETAS,
        lados_uso=("frente",),
        modelos=(
            _m("padrao", "Padrão (180 × 40)", 1800, 400, 500),
            _m("pequeno", "Pequeno (120 × 35)", 1200, 350, 500),
        ),
        modelo_padrao="padrao",
    ),
    # ------------------------------------------------------------ mais móveis
    ItemCatalogo(
        tipo="beliche",
        nome="Beliche",
        categoria=Categoria.DORMIR,
        simbolo=Simbolo.BELICHE,
        lados_uso=("esquerda", "direita", "frente"),
        modelos=(
            _m("solteiro", "Solteiro (colchão 78 × 188)", 900, 1950, 1600),
            _m("solteiro_88", "Solteiro largo (colchão 88 × 188)", 1000, 1950, 1600),
        ),
        modelo_padrao="solteiro",
    ),
    ItemCatalogo(
        tipo="aparador",
        nome="Aparador",
        categoria=Categoria.GUARDAR,
        simbolo=Simbolo.PORTAS,
        lados_uso=("frente",),
        modelos=(
            _m("120", "Aparador 120 × 40", 1200, 400, 800, portas="abrir", largura_porta=400),
            _m("160", "Buffet 160 × 45", 1600, 450, 800, portas="abrir", largura_porta=400),
        ),
        modelo_padrao="120",
    ),
    ItemCatalogo(
        tipo="painel_tv",
        nome="Painel de TV",
        categoria=Categoria.ELETRONICOS,
        simbolo=Simbolo.GENERICO,
        lados_uso=(),
        modelos=(
            _m("180", "Painel 180 × 140", 1800, 30, 1400, elevacao=400),
            _m("220", "Painel 220 × 160", 2200, 30, 1600, elevacao=300),
        ),
        modelo_padrao="180",
    ),
    ItemCatalogo(
        tipo="cadeira_escritorio",
        nome="Cadeira de escritório",
        categoria=Categoria.SENTAR,
        simbolo=Simbolo.CADEIRA_GIRATORIA,
        lados_uso=("frente",),
        modelos=(_m("padrao", "Giratória com rodízios", 620, 620, 1050),),
        modelo_padrao="padrao",
    ),
    ItemCatalogo(
        tipo="puff",
        nome="Puff",
        categoria=Categoria.SENTAR,
        simbolo=Simbolo.GENERICO,
        lados_uso=(),
        modelos=(
            _m("quadrado", "Quadrado 45 × 45", 450, 450, 420),
            _m("redondo", "Redondo Ø 45", 450, 450, 420, forma="redondo"),
        ),
        modelo_padrao="quadrado",
    ),
    # ------------------------------------------------------------ área de serviço
    ItemCatalogo(
        tipo="maquina_lavar",
        nome="Máquina de lavar",
        categoria=Categoria.AREA_SERVICO,
        simbolo=Simbolo.MAQUINA,
        lados_uso=("frente",),
        modelos=(
            _m("frontal", "Frontal 11 kg (60 × 65)", 600, 650, 850),
            _m("superior", "Abertura em cima 12 kg (60 × 66)", 600, 660, 1000),
        ),
        modelo_padrao="frontal",
    ),
    ItemCatalogo(
        tipo="tanque",
        nome="Tanque",
        categoria=Categoria.AREA_SERVICO,
        simbolo=Simbolo.PIA,
        lados_uso=("frente",),
        modelos=(
            _m("louca", "Tanque de louça com coluna (55 × 45)", 550, 450, 850),
            _m("gabinete", "Tanque com gabinete (60 × 50)", 600, 500, 900),
        ),
        modelo_padrao="louca",
    ),
    # ------------------------------------------------------------ cozinha
    ItemCatalogo(
        tipo="pia",
        nome="Pia (gabinete com bancada e cuba)",
        categoria=Categoria.COZINHA,
        simbolo=Simbolo.PIA,
        lados_uso=("frente",),
        modelos=(
            _m("120", "Gabinete 120 × 55", 1200, 550, 900),
            _m("150", "Gabinete 150 × 55", 1500, 550, 900),
            _m("180", "Bancada 180 × 60", 1800, 600, 900),
        ),
        modelo_padrao="120",
    ),
    ItemCatalogo(
        tipo="fogao",
        nome="Fogão / cooktop",
        categoria=Categoria.COZINHA,
        simbolo=Simbolo.FOGAO,
        lados_uso=("frente",),
        modelos=(
            _m("4bocas", "Fogão 4 bocas a gás (55 × 60)", 550, 600, 850, energia="gas"),
            _m("5bocas", "Fogão 5 bocas a gás (75 × 60)", 750, 600, 850, energia="gas"),
            _m(
                "cooktop",
                "Cooktop de indução (60 × 52, na bancada)",
                600,
                520,
                60,
                elevacao=900,
                energia="eletrico",
            ),
        ),
        modelo_padrao="4bocas",
    ),
    ItemCatalogo(
        tipo="geladeira",
        nome="Geladeira",
        categoria=Categoria.COZINHA,
        simbolo=Simbolo.GELADEIRA,
        lados_uso=("frente",),
        modelos=(
            _m("duplex", "Duplex (70 × 72 × 180)", 700, 720, 1800),
            _m("frost", "Frost free (60 × 68 × 170)", 600, 680, 1700),
            _m("inverse", "Inverse (75 × 75 × 190)", 750, 750, 1900),
        ),
        modelo_padrao="duplex",
    ),
    # ------------------------------------------------------------ banheiro
    ItemCatalogo(
        tipo="vaso",
        nome="Vaso sanitário",
        categoria=Categoria.BANHEIRO,
        simbolo=Simbolo.VASO,
        lados_uso=("frente",),
        modelos=(
            _m("acoplada", "Com caixa acoplada (37 × 65)", 370, 650, 780),
            _m("compacto", "Compacto (36 × 60)", 360, 600, 750),
            _m("suspenso", "Suspenso, caixa embutida (36 × 54)", 360, 540, 400),
        ),
        modelo_padrao="acoplada",
    ),
    ItemCatalogo(
        tipo="lavatorio",
        nome="Lavatório (gabinete com cuba)",
        categoria=Categoria.BANHEIRO,
        simbolo=Simbolo.PIA,
        lados_uso=("frente",),
        modelos=(
            _m("60", "Gabinete 60 × 45", 600, 450, 850),
            _m("80", "Gabinete 80 × 45", 800, 450, 850),
            _m("100", "Bancada 100 × 50", 1000, 500, 850),
        ),
        modelo_padrao="60",
    ),
    ItemCatalogo(
        tipo="box",
        nome="Box do chuveiro",
        categoria=Categoria.BANHEIRO,
        simbolo=Simbolo.BOX,
        lados_uso=("frente",),
        modelos=(
            _m("90x90", "90 × 90", 900, 900, 1900),
            _m("80x120", "120 × 80 (frontal)", 1200, 800, 1900),
            _m("90x140", "140 × 90 (frontal)", 1400, 900, 1900),
        ),
        modelo_padrao="80x120",
    ),
    ItemCatalogo(
        tipo="sob_medida",
        nome="Móvel sob medida",
        categoria=Categoria.SOB_MEDIDA,
        simbolo=Simbolo.GENERICO,
        lados_uso=("frente",),
        modelos=(_m("padrao", "Caixa (80 × 50 × 80)", 800, 500, 800),),
        modelo_padrao="padrao",
    ),
)
"""O último, ``sob_medida``, é o móvel criado do zero: nome e medidas livres; dá para
montar por dentro (``construcao``) como planejado."""

CATALOGO: dict[str, ItemCatalogo] = {i.tipo: i for i in _ITENS}


def item_do_tipo(tipo: str) -> ItemCatalogo | None:
    return CATALOGO.get(tipo)


def lados_de_uso(tipo: str) -> tuple[Lado, ...]:
    """Lados de uso do tipo; fora do catálogo, só a frente."""
    item = CATALOGO.get(tipo)
    return item.lados_uso if item else ("frente",)


def _medida(valor: int, origem: str, obs: str) -> dict[str, Any]:
    return {"valor": valor, "origem": origem, "obs": obs}


def novo_movel(
    tipo: str,
    id_: str,
    centro: tuple[int, int],
    modelo: str | None = None,
    rotacao: int = 0,
    nome: str | None = None,
    medidas: dict[str, int] | None = None,
    origem_medidas: str = "estimada",
) -> dict[str, Any]:
    """Móvel pronto para ``comodos/<comodo>.json`` a partir do catálogo.

    As medidas vêm do modelo do catálogo como ``estimada``; as passadas em
    ``medidas`` (largura, profundidade, altura, elevacao, largura_porta)
    substituem as do modelo com ``origem_medidas``.

    Levanta ``KeyError`` se o tipo ou o modelo não existirem no catálogo.
    """
    item = CATALOGO.get(tipo)
    if item is None:
        raise KeyError(f"tipo '{tipo}' não está no catálogo ({', '.join(sorted(CATALOGO))})")
    mod = item.modelo(modelo)
    if mod is None:
        ids = ", ".join(m.id for m in item.modelos)
        raise KeyError(f"modelo '{modelo}' não existe para '{tipo}' ({ids})")
    medidas = medidas or {}
    desconhecidas = set(medidas) - {
        "largura",
        "profundidade",
        "altura",
        "elevacao",
        "largura_porta",
    }
    if desconhecidas:
        raise KeyError(f"medida(s) desconhecida(s): {', '.join(sorted(desconhecidas))}")
    origem_cat = f"estimada: padrão do catálogo ({item.nome.lower()} {mod.nome})"

    def med(campo: str, padrao: int | None) -> dict[str, Any] | None:
        if campo in medidas:
            return _medida(medidas[campo], origem_medidas, "informada ao adicionar o móvel")
        return None if padrao is None else _medida(padrao, "estimada", origem_cat)

    movel: dict[str, Any] = {
        "id": id_,
        "tipo": tipo,
        "modelo": mod.id,
        "nome": nome or item.nome,
        "centro": list(centro),
        "rotacao": rotacao,
        "largura": med("largura", mod.largura),
        "profundidade": med("profundidade", mod.profundidade),
        "altura": med("altura", mod.altura),
    }
    opcionais = {
        "elevacao": med("elevacao", mod.elevacao),
        "portas": mod.portas,
        "largura_porta": med("largura_porta", mod.largura_porta),
        "polegadas": mod.polegadas,
        "forma": mod.forma,
    }
    movel.update({k: v for k, v in opcionais.items() if v is not None})
    return movel


def exportar() -> dict[str, Any]:
    """Catálogo em formato JSON (para o frontend)."""
    from interiores_core.acabamentos import ACABAMENTOS, PES, PUXADORES  # evita ciclo

    return {
        "versao": 1,
        "itens": [i.model_dump(mode="json") for i in _ITENS],
        "acabamentos": {k: a.nome for k, a in ACABAMENTOS.items()},
        "puxadores": dict(PUXADORES),
        "pes": dict(PES),
    }
