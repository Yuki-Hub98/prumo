"""O que uma regra recebe: o cômodo já resolvido em geometria, móveis e limites."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cached_property

from shapely import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from interiores_core import geometria
from interiores_core.modelo import Comodo, Movel, Pavimento, Porta
from interiores_core.validacao import Problema, Severidade

Ponto = tuple[float, float]
Lado = tuple[Ponto, Ponto]

ALCANCE = 20_000.0
"""Até onde (mm) uma folga é procurada; maior que qualquer cômodo."""
FOLGA_NUMERICA = 1.0


@dataclass
class Contexto:
    pavimento: Pavimento
    comodo: Comodo
    util: Polygon
    """Área livre do cômodo (sem paredes)."""
    moveis: list[Movel]
    limites: Mapping[str, int]
    problemas: list[Problema] = field(default_factory=list)

    # ---------------------------------------------------------------- geometria

    @cached_property
    def poligonos(self) -> dict[str, Polygon]:
        return {m.id: geometria.poligono_movel(m) for m in self.moveis}

    @cached_property
    def fora(self) -> BaseGeometry:
        """Tudo que não é piso livre do cômodo (paredes, outros cômodos, rua)."""
        x0, y0, x1, y1 = self.util.bounds
        return box(x0 - ALCANCE, y0 - ALCANCE, x1 + ALCANCE, y1 + ALCANCE).difference(self.util)

    @cached_property
    def livre(self) -> BaseGeometry:
        """Piso livre: área útil menos a projeção dos móveis."""
        return self.util.difference(unary_union(list(self.poligonos.values())))

    @cached_property
    def portas(self) -> list[Porta]:
        """Portas nas paredes do cômodo que ligam a ele."""
        ids = set(self.comodo.paredes)
        return [
            a
            for a in self.pavimento.aberturas
            if isinstance(a, Porta) and a.parede in ids and self.comodo.id in (a.de, a.para)
        ]

    def obstaculos(self, exceto: str | None = None) -> BaseGeometry:
        """Paredes/exterior e todos os móveis, menos o indicado."""
        outros = [p for mid, p in self.poligonos.items() if mid != exceto]
        return unary_union([self.fora, *outros])

    def folga(self, lado: Lado, direcao: Ponto, exceto: str | None = None) -> float:
        """Distância livre (mm) à frente de ``lado`` na ``direcao``, em toda a largura do lado.

        Mede numa faixa perpendicular ao lado: é a menor distância até a primeira
        parede ou móvel que entra nessa faixa.
        """
        (ax, ay), (bx, by) = lado
        dx, dy = direcao
        tam = math.hypot(bx - ax, by - ay)
        if tam <= 2 * FOLGA_NUMERICA:
            return ALCANCE
        # encolhe 1 mm nas pontas e afasta 1 mm do lado: contato só de borda
        # (o próprio lado, a parede onde ele encosta) não conta como obstáculo
        ux, uy = (bx - ax) / tam * FOLGA_NUMERICA, (by - ay) / tam * FOLGA_NUMERICA
        ox, oy = dx * FOLGA_NUMERICA, dy * FOLGA_NUMERICA
        faixa = self.faixa(
            ((ax + ux + ox, ay + uy + oy), (bx - ux + ox, by - uy + oy)), direcao, ALCANCE
        )
        bate = faixa.intersection(self.obstaculos(exceto))
        if bate.is_empty or bate.area == 0:
            return ALCANCE
        return float(LineString(lado).distance(bate))

    @staticmethod
    def faixa(lado: Lado, direcao: Ponto, profundidade: float) -> Polygon:
        (ax, ay), (bx, by) = lado
        dx, dy = direcao
        return Polygon(
            [
                (ax, ay),
                (bx, by),
                (bx + dx * profundidade, by + dy * profundidade),
                (ax + dx * profundidade, ay + dy * profundidade),
            ]
        )

    # ---------------------------------------------------------------- problemas

    def add(
        self,
        severidade: Severidade,
        codigo: str,
        mensagem: str,
        elemento: str | None = None,
        regiao: BaseGeometry | None = None,
    ) -> None:
        contorno: list[tuple[int, int]] | None = None
        posicao: tuple[int, int] | None = None
        if regiao is not None and not regiao.is_empty:
            alvo = regiao if isinstance(regiao, Polygon) else regiao.convex_hull
            if isinstance(alvo, Polygon):
                contorno = [(round(x), round(y)) for x, y in alvo.exterior.coords]
            c = regiao.centroid
            posicao = (round(c.x), round(c.y))
        self.problemas.append(
            Problema(
                severidade=severidade,
                codigo=codigo,
                mensagem=mensagem,
                pavimento=self.pavimento.id,
                comodo=self.comodo.id,
                elemento=elemento,
                posicao=posicao,
                regiao=contorno,
            )
        )


Regra = Callable[[Contexto], None]
"""Uma checagem: lê o contexto e registra problemas com ``ctx.add``."""


# ---------------------------------------------------------------- lados dos móveis


def lado_local(movel: Movel, qual: str) -> tuple[Lado, Ponto]:
    """Segmento e direção para fora de um lado do móvel no referencial global.

    ``qual``: ``"frente"``, ``"costas"``, ``"esquerda"`` ou ``"direita"`` (esquerda
    e direita de quem olha o móvel de frente estando atrás dele, isto é, -x e +x
    locais).
    """
    w, d = movel.largura.valor / 2, movel.profundidade.valor / 2
    locais: dict[str, tuple[Ponto, Ponto, Ponto]] = {
        "frente": ((w, d), (-w, d), (0, 1)),
        "costas": ((-w, -d), (w, -d), (0, -1)),
        "esquerda": ((-w, d), (-w, -d), (-1, 0)),
        "direita": ((w, -d), (w, d), (1, 0)),
    }
    a, b, (vx, vy) = locais[qual]
    ga, gb = geometria.girar_movel(movel, *a), geometria.girar_movel(movel, *b)
    cx, cy = geometria.girar_movel(movel, 0, 0)
    ox, oy = geometria.girar_movel(movel, vx, vy)
    return (ga, gb), (ox - cx, oy - cy)


def onde_na_planta(direcao: Ponto) -> str:
    """Descrição do lado pela direção na planta (y para cima)."""
    dx, dy = direcao
    if abs(dx) >= abs(dy):
        return "à direita na planta" if dx > 0 else "à esquerda na planta"
    return "acima na planta" if dy > 0 else "abaixo na planta"


def de_tipo(moveis: Iterable[Movel], *tipos: str) -> list[Movel]:
    return [m for m in moveis if m.tipo in tipos]
