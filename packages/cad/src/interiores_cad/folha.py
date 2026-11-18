"""Folha (formato, escala, enquadramento) e carimbo.

A folha é desenhada no próprio espaço de modelo, em escala: 1 mm de papel vale
``escala`` mm do imóvel. Assim o DXF já sai com moldura e carimbo e o PDF é só
o enquadramento exato da folha.
"""

from __future__ import annotations

import re
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass

from ezdxf.enums import TextEntityAlignment
from ezdxf.layouts.layout import Modelspace

from interiores_cad.estilo import AVISO_OBRA, ESTILO_TEXTO, Texto
from interiores_core.medidas import Medida

ESCALAS = (20, 25, 50)
"""Escalas permitidas (CLAUDE.md §5.3)."""

MARGEM = 10.0
LARGURA_PAINEL = 115.0
"""Coluna da direita: aviso, medidas estimadas e carimbo (mm de papel)."""
LARGURA_LETRA = 0.75
"""Largura média de um caractere em relação à altura do texto (para quebrar linhas)."""
FOLGA_DESENHO = 32.0
"""Espaço reservado em volta das paredes para cotas e etiquetas (mm de papel)."""


@dataclass(frozen=True)
class Formato:
    nome: str
    largura: float
    altura: float


FORMATOS = (
    Formato("A3", 420, 297),
    Formato("A2", 594, 420),
    Formato("A1", 841, 594),
    Formato("A0", 1189, 841),
)


@dataclass(frozen=True)
class Folha:
    """Folha escolhida e onde ela cai no espaço de modelo."""

    formato: Formato
    escala: int
    origem: tuple[float, float]
    """Canto inferior esquerdo da folha, em coordenadas de modelo (mm)."""

    @property
    def area_desenho(self) -> tuple[float, float]:
        """Largura e altura (mm de papel) da área à esquerda do painel."""
        return (
            self.formato.largura - 2 * MARGEM - LARGURA_PAINEL - MARGEM,
            self.formato.altura - 2 * MARGEM,
        )

    def modelo(self, x: float, y: float) -> tuple[float, float]:
        """Ponto em mm de papel → coordenada de modelo."""
        return (self.origem[0] + x * self.escala, self.origem[1] + y * self.escala)

    def mm(self, papel: float) -> float:
        """Comprimento em mm de papel → unidades de modelo."""
        return papel * self.escala

    @property
    def limites(self) -> tuple[float, float, float, float]:
        """(xmin, ymin, xmax, ymax) da folha em coordenadas de modelo."""
        x0, y0 = self.origem
        return (
            x0,
            y0,
            x0 + self.formato.largura * self.escala,
            y0 + self.formato.altura * self.escala,
        )


def escolher_folha(caixa: tuple[float, float, float, float]) -> Folha:
    """Menor formato e maior escala em que a caixa (mm do imóvel) cabe com as cotas.

    Tenta A3 em 1:20, 1:25, 1:50; depois formatos maiores em 1:50.
    """
    xmin, ymin, xmax, ymax = caixa
    largura, altura = xmax - xmin, ymax - ymin
    candidatos = [(FORMATOS[0], e) for e in ESCALAS] + [(f, ESCALAS[-1]) for f in FORMATOS[1:]]
    for formato, escala in candidatos:
        folha = Folha(formato, escala, (0.0, 0.0))
        area_l, area_a = folha.area_desenho
        if (
            largura / escala + 2 * FOLGA_DESENHO <= area_l
            and altura / escala + 2 * FOLGA_DESENHO <= area_a
        ):
            # centraliza a caixa na área de desenho
            cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
            origem = (cx - (MARGEM + area_l / 2) * escala, cy - (MARGEM + area_a / 2) * escala)
            return Folha(formato, escala, origem)
    raise ValueError(
        f"desenho de {largura:.0f} × {altura:.0f} mm não cabe nem em A0 a 1:{ESCALAS[-1]}"
    )


# ---------------------------------------------------------------- estimadas

_ITEM = re.compile(r"\[([^\]]+)\]\.?([^\[]*)$")


def agrupar_estimadas(estimadas: Sequence[tuple[str, Medida]]) -> list[str]:
    """Agrupa caminhos por elemento: ``"janela-quarto: largura, altura"``.

    O elemento é o último ``[id]`` do caminho; sem ``[id]``, o prefixo (pavimento).
    Mantém a ordem da primeira aparição.
    """
    grupos: dict[str, list[str]] = {}
    for caminho, _ in estimadas:
        achado = _ITEM.search(caminho)
        if achado:
            elemento, campo = achado.group(1), achado.group(2) or "valor"
        else:
            elemento, _, campo = caminho.rpartition(".")
            elemento = _ITEM.sub(r"\1", elemento) if "[" in elemento else elemento
        grupos.setdefault(elemento, []).append(campo)
    return [f"{elemento}: {', '.join(campos)}" for elemento, campos in grupos.items()]


# ---------------------------------------------------------------- carimbo


@dataclass(frozen=True)
class DadosCarimbo:
    projeto: str
    apelido: str | None
    desenho: str
    """Ex.: "Planta baixa — Quarto (suíte)"."""
    pavimento: str
    escopo: str
    """Ex.: "cômodo quarto", "pavimento terreo"."""
    data: str
    hash_curto: str
    gerador: str
    estimadas: Sequence[tuple[str, Medida]]
    legenda: Sequence[str] = ()
    """Linhas da legenda de símbolos, logo acima do carimbo."""
    checagens: Sequence[str] = ()
    """Problemas das checagens de uso, já numerados como no desenho."""


def _texto(
    msp: Modelspace,
    folha: Folha,
    texto: str,
    x: float,
    y: float,
    altura: float,
    camada: str = "TEXTO",
    alinhamento: TextEntityAlignment = TextEntityAlignment.BOTTOM_LEFT,
) -> None:
    msp.add_text(
        texto,
        height=folha.mm(altura),
        dxfattribs={"layer": camada, "style": ESTILO_TEXTO},
    ).set_placement(folha.modelo(x, y), align=alinhamento)


def _retangulo(
    msp: Modelspace, folha: Folha, x0: float, y0: float, x1: float, y1: float, camada: str
) -> None:
    pontos = [folha.modelo(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    msp.add_lwpolyline(pontos, close=True, dxfattribs={"layer": camada})


def _caixa_checagens(
    msp: Modelspace, folha: Folha, checagens: Sequence[str], px0: float, px1: float, y: float
) -> float:
    """Caixa "CHECAGENS" a partir de ``y`` (de baixo para cima); devolve o novo topo."""
    x = px0 + 3
    largura_chars = int((px1 - px0 - 6) / (Texto.CARIMBO_PEQUENO * LARGURA_LETRA))
    linhas: list[str] = []
    for item in checagens or ["Nenhum problema nas checagens de uso."]:
        linhas += textwrap.wrap(item, largura_chars, subsequent_indent="    ")
    linhas = linhas[:24]
    passo = Texto.CARIMBO_PEQUENO * 1.55
    altura = passo * (len(linhas) + 1) + 3
    _retangulo(msp, folha, px0, y, px1, y + altura, "TEXTO")
    yl = y + altura - 2 - Texto.CARIMBO_PEQUENO
    _texto(
        msp, folha, "CHECAGENS (números = marcas no desenho)", x, yl, Texto.CARIMBO_PEQUENO * 0.8
    )
    for linha in linhas:
        yl -= passo
        camada = "RESTRICAO" if checagens else "TEXTO"
        _texto(msp, folha, linha, x, yl, Texto.CARIMBO_PEQUENO, camada)
    return y + altura


def desenhar_folha(msp: Modelspace, folha: Folha, dados: DadosCarimbo) -> None:
    """Moldura, carimbo, lista de estimadas e aviso de obra (se houver estimada)."""
    larg, alt = folha.formato.largura, folha.formato.altura
    _retangulo(msp, folha, MARGEM, MARGEM, larg - MARGEM, alt - MARGEM, "TEXTO")
    px0 = larg - MARGEM - LARGURA_PAINEL
    px1 = larg - MARGEM
    msp.add_line(
        folha.modelo(px0, MARGEM), folha.modelo(px0, alt - MARGEM), dxfattribs={"layer": "TEXTO"}
    )
    x = px0 + 3

    # carimbo (de baixo para cima)
    linhas = [
        ("GERADOR", dados.gerador),
        ("HASH DO JSON", dados.hash_curto),
        ("DATA", dados.data),
        ("ESCALA · FOLHA", f"1:{folha.escala} · {folha.formato.nome} · cotas em mm"),
        ("ESCOPO", dados.escopo),
        ("PAVIMENTO", dados.pavimento),
        ("PROJETO", dados.projeto + (f" ({dados.apelido})" if dados.apelido else "")),
    ]
    passo = 8.0
    y = MARGEM
    for rotulo, valor in linhas:
        _retangulo(msp, folha, px0, y, px1, y + passo, "TEXTO")
        _texto(msp, folha, rotulo, x, y + passo - 2.6, Texto.CARIMBO_PEQUENO * 0.8)
        _texto(msp, folha, valor, x, y + 1.3, Texto.CARIMBO)
        y += passo
    _retangulo(msp, folha, px0, y, px1, y + 12, "TEXTO")
    _texto(msp, folha, dados.desenho, x, y + 4, Texto.CARIMBO_TITULO)
    y += 12
    if dados.legenda:
        passo_leg = Texto.CARIMBO_PEQUENO * 1.6
        altura_leg = passo_leg * (len(dados.legenda) + 1) + 3
        _retangulo(msp, folha, px0, y, px1, y + altura_leg, "TEXTO")
        yl = y + altura_leg - 2 - Texto.CARIMBO_PEQUENO
        _texto(msp, folha, "LEGENDA", x, yl, Texto.CARIMBO_PEQUENO * 0.8)
        for linha in dados.legenda:
            yl -= passo_leg
            _texto(msp, folha, linha, x, yl, Texto.CARIMBO_PEQUENO)
        y += altura_leg
    y = _caixa_checagens(msp, folha, dados.checagens, px0, px1, y)
    y_topo_carimbo = y

    # aviso + estimadas (de cima para baixo)
    y = alt - MARGEM - 3
    if dados.estimadas:
        y -= Texto.AVISO
        _texto(msp, folha, "PRELIMINAR", x, y, Texto.AVISO, "AVISO")
        y -= Texto.AVISO + 2
        _texto(msp, folha, "NÃO USAR PARA OBRA", x, y, Texto.AVISO, "AVISO")
        y -= 6
        _texto(msp, folha, AVISO_OBRA, x, y, Texto.CARIMBO_PEQUENO, "AVISO")
        y -= 4
        _texto(
            msp,
            folha,
            f"{len(dados.estimadas)} medida(s) estimada(s) usada(s) neste desenho:",
            x,
            y,
            Texto.CARIMBO_PEQUENO,
        )
        y -= 4
        largura_chars = int((LARGURA_PAINEL - 6) / (Texto.CARIMBO_PEQUENO * LARGURA_LETRA))
        linhas_est: list[str] = []
        for grupo in agrupar_estimadas(dados.estimadas):
            linhas_est += textwrap.wrap(grupo, largura_chars, subsequent_indent="   ")
        passo_est = Texto.CARIMBO_PEQUENO * 1.55
        cabem = int((y - y_topo_carimbo - 4) / passo_est)
        if len(linhas_est) > cabem:
            resto = len(linhas_est) - (cabem - 1)
            linhas_est = [
                *linhas_est[: cabem - 1],
                f"... e mais {resto} linha(s): ver `interiores validar --estimadas`",
            ]
        for linha in linhas_est:
            _texto(msp, folha, linha, x, y, Texto.CARIMBO_PEQUENO)
            y -= passo_est
    else:
        y -= Texto.CARIMBO
        _texto(msp, folha, "Nenhuma medida estimada.", x, y, Texto.CARIMBO)
