"""Portas e janelas prontas: tipos e tamanhos comerciais para escolher ao criar.

Escolher um modelo só preenche largura, altura, peitoril e o tipo de abertura; tudo continua
editável depois (e a origem das medidas é perguntada, como em qualquer medida).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ModeloPorta(_Base):
    id: str
    nome: str
    folha: Literal["giro", "correr", "camarao"]
    estilo: Literal["lisa", "almofadada", "vidro", "veneziana"] = "lisa"
    largura: int
    altura: int = 2100


class ModeloJanela(_Base):
    id: str
    nome: str
    abertura: Literal["correr", "basculante", "maxim_ar", "abrir", "fixa"]
    folhas: int = 2
    largura: int
    altura: int
    peitoril: int
    uso: str = ""
    """Onde costuma ir (ajuda a escolher)."""


ESTILOS_PORTA: dict[str, str] = {
    "lisa": "Lisa",
    "almofadada": "Almofadada",
    "vidro": "Com vidro",
    "veneziana": "Veneziana",
}
FOLHAS_PORTA: dict[str, str] = {
    "giro": "De abrir (giro)",
    "correr": "De correr",
    "camarao": "Camarão",
}
ABERTURAS_JANELA: dict[str, str] = {
    "correr": "De correr",
    "basculante": "Basculante",
    "maxim_ar": "Maxim-ar",
    "abrir": "De abrir",
    "fixa": "Fixa",
}

PORTAS: tuple[ModeloPorta, ...] = (
    ModeloPorta(id="giro-60", nome="De abrir 60 × 210 (banheiro)", folha="giro", largura=600),
    ModeloPorta(id="giro-70", nome="De abrir 70 × 210", folha="giro", largura=700),
    ModeloPorta(id="giro-80", nome="De abrir 80 × 210", folha="giro", largura=800),
    ModeloPorta(id="giro-90", nome="De abrir 90 × 210 (entrada)", folha="giro", largura=900),
    ModeloPorta(id="correr-80", nome="De correr 80 × 210", folha="correr", largura=800),
    ModeloPorta(id="correr-120", nome="De correr 120 × 210", folha="correr", largura=1200),
    ModeloPorta(id="camarao-70", nome="Camarão 70 × 210", folha="camarao", largura=700),
    ModeloPorta(id="camarao-80", nome="Camarão 80 × 210", folha="camarao", largura=800),
    ModeloPorta(
        id="vidro-80", nome="De abrir com vidro 80 × 210", folha="giro", estilo="vidro", largura=800
    ),
)

JANELAS: tuple[ModeloJanela, ...] = (
    ModeloJanela(id="correr-100x100", nome="De correr 100 × 100", abertura="correr",
                 largura=1000, altura=1000, peitoril=1100, uso="quarto, cozinha"),
    ModeloJanela(id="correr-120x100", nome="De correr 120 × 100", abertura="correr",
                 largura=1200, altura=1000, peitoril=1100, uso="quarto"),
    ModeloJanela(id="correr-150x120", nome="De correr 150 × 120", abertura="correr",
                 largura=1500, altura=1200, peitoril=1000, uso="quarto, sala"),
    ModeloJanela(id="correr-200x120", nome="De correr 200 × 120 (4 folhas)", abertura="correr",
                 folhas=4, largura=2000, altura=1200, peitoril=1000, uso="sala"),
    ModeloJanela(id="basculante-60x60", nome="Basculante 60 × 60", abertura="basculante",
                 folhas=1, largura=600, altura=600, peitoril=1500, uso="banheiro"),
    ModeloJanela(id="maxim-ar-80x60", nome="Maxim-ar 80 × 60", abertura="maxim_ar",
                 folhas=1, largura=800, altura=600, peitoril=1400, uso="banheiro, cozinha"),
    ModeloJanela(id="abrir-100x120", nome="De abrir 100 × 120", abertura="abrir",
                 largura=1000, altura=1200, peitoril=1000, uso="quarto"),
    ModeloJanela(id="fixa-60x100", nome="Fixa 60 × 100", abertura="fixa",
                 folhas=1, largura=600, altura=1000, peitoril=1100, uso="iluminação"),
)  # fmt: skip


class CatalogoAberturas(_Base):
    """O que a tela recebe: modelos prontos e os nomes de cada opção."""

    portas: tuple[ModeloPorta, ...]
    janelas: tuple[ModeloJanela, ...]
    folhas_porta: dict[str, str]
    estilos_porta: dict[str, str]
    aberturas_janela: dict[str, str]


def exportar() -> CatalogoAberturas:
    return CatalogoAberturas(
        portas=PORTAS,
        janelas=JANELAS,
        folhas_porta=FOLHAS_PORTA,
        estilos_porta=ESTILOS_PORTA,
        aberturas_janela=ABERTURAS_JANELA,
    )


def modelo_porta(id_: str) -> ModeloPorta | None:
    return next((m for m in PORTAS if m.id == id_), None)


def modelo_janela(id_: str) -> ModeloJanela | None:
    return next((m for m in JANELAS if m.id == id_), None)
