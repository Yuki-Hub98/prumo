"""Cotas da planta para a tela (as mesmas medidas do DXF, já prontas para desenhar).

- **Cômodo** (``comodo``): cada face interna, medida de canto a canto da área útil; na tela
  ficam por dentro do cômodo. Com porta ou janela na face, sai também a cadeia (``trecho``):
  do canto à abertura, a abertura e dela ao outro canto.
- **Gerais** (``eixo`` e ``geral``): eixos das paredes retas em cadeia, embaixo e à esquerda,
  e o total externo.

``lado`` é o unitário para onde a cota é afastada da linha medida e ``fileira`` diz qual
fileira ela ocupa (0 = a mais perto); quem desenha escolhe o afastamento de cada fileira.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Literal

from shapely import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from interiores_core import geometria
from interiores_core.medidas import medidas_em
from interiores_core.modelo import Comodo, Parede, Pavimento

Pt = tuple[float, float]
TipoCota = Literal["comodo", "trecho", "eixo", "geral"]
Origem = Literal["trena", "projeto", "estimada"]


def origem_de(*objetos: object) -> Origem:
    """Origem que a cota herda das medidas envolvidas: qualquer chute faz dela um chute;
    tudo medido, medida; senão, "quero assim"."""
    origens = {m.origem for o in objetos for _, m in medidas_em(o)}
    if "estimada" in origens:
        return "estimada"
    if origens and origens <= {"trena"}:
        return "trena"
    return "projeto"


@dataclass(frozen=True)
class Cota:
    de: Pt
    ate: Pt
    lado: Pt
    """Unitário para onde a cota sai da linha medida."""
    fileira: int
    tipo: TipoCota
    comodo: str | None = None
    origem: Origem = "projeto"

    @property
    def valor(self) -> int:
        return round(math.dist(self.de, self.ate))


def _maior(g: BaseGeometry | None) -> Polygon | None:
    if g is None or g.is_empty:
        return None
    if isinstance(g, Polygon):
        return g
    partes = [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
    return max(partes, key=lambda p: p.area, default=None)


def _cortes(pav: Pavimento, paredes: list[Parede], p: Pt, u: Pt, tam: float) -> list[float]:
    """Onde as aberturas das ``paredes`` começam e terminam ao longo da face p + t·u."""
    ids = {pa.id for pa in paredes}
    cortes: list[float] = []
    for ab in pav.aberturas:
        parede = pav.parede(ab.parede)
        if parede is None or parede.id not in ids:
            continue
        pu, _ = geometria.direcao(parede)
        for d in (ab.distancia_inicio.valor, ab.distancia_inicio.valor + ab.largura.valor):
            x, y = parede.inicio[0] + pu[0] * d, parede.inicio[1] + pu[1] * d
            t = (x - p[0]) * u[0] + (y - p[1]) * u[1]
            if 0 < t < tam:
                cortes.append(round(t, 3))
    return cortes


def cotas_do_comodo(pav: Pavimento, c: Comodo) -> list[Cota]:
    """Faces internas do cômodo (por dentro) e, com aberturas, a cadeia de cada face."""
    util = _maior(geometria.poligono_util(pav, c))
    if util is None:
        return []
    pts = [(float(x), float(y)) for x, y in orient(util, sign=1.0).exterior.coords]
    cotas: list[Cota] = []
    for p, q in itertools.pairwise(pts):
        dx, dy = q[0] - p[0], q[1] - p[1]
        tam = math.hypot(dx, dy)
        if tam < 1:
            continue
        u = (dx / tam, dy / tam)
        dentro = (-u[1], u[0])  # anel anti-horário: o interior fica à esquerda
        paredes = geometria.paredes_da_face(pav, c, p, q)
        ids = {pa.id for pa in paredes}
        aberturas = [a for a in pav.aberturas if a.parede in ids]
        origem = origem_de(*paredes, *aberturas)
        cortes = sorted({0.0, tam, *_cortes(pav, paredes, p, u, tam)})
        fileira = 0
        if len(cortes) > 2:
            for t0, t1 in itertools.pairwise(cortes):
                if t1 - t0 >= 1:
                    de = (p[0] + u[0] * t0, p[1] + u[1] * t0)
                    ate = (p[0] + u[0] * t1, p[1] + u[1] * t1)
                    cotas.append(Cota(de, ate, dentro, 0, "trecho", c.id, origem))
            fileira = 1
        cotas.append(Cota(p, q, dentro, fileira, "comodo", c.id, origem))
    return cotas


def cotas_gerais(pav: Pavimento) -> list[Cota]:
    """Eixos das paredes retas em cadeia e o total externo, embaixo e à esquerda."""
    corpos = [geometria.corpo(p) for p in pav.paredes if geometria.comprimento(p) > 0]
    if not corpos:
        return []
    xmin, ymin, xmax, ymax = unary_union(corpos).bounds
    xs = sorted({float(p.inicio[0]) for p in pav.paredes if p.inicio[0] == p.fim[0]})
    ys = sorted({float(p.inicio[1]) for p in pav.paredes if p.inicio[1] == p.fim[1]})
    baixo, esquerda = (0.0, -1.0), (-1.0, 0.0)

    def nos_eixos(*vs: float, em_x: bool) -> Origem:
        retas = [p for p in pav.paredes if (p.inicio[0] == p.fim[0]) == em_x]
        return origem_de(*(p for p in retas if float(p.inicio[0 if em_x else 1]) in vs))

    cotas = [
        Cota((a, ymin), (b, ymin), baixo, 0, "eixo", origem=nos_eixos(a, b, em_x=True))
        for a, b in itertools.pairwise(xs)
    ]
    cotas += [
        Cota((xmin, a), (xmin, b), esquerda, 0, "eixo", origem=nos_eixos(a, b, em_x=False))
        for a, b in itertools.pairwise(ys)
    ]
    tudo = origem_de(*pav.paredes)
    cotas.append(Cota((xmin, ymin), (xmax, ymin), baixo, 1, "geral", origem=tudo))
    cotas.append(Cota((xmin, ymin), (xmin, ymax), esquerda, 1, "geral", origem=tudo))
    return cotas


def cotas_do_pavimento(pav: Pavimento) -> list[Cota]:
    return cotas_gerais(pav) + [k for c in pav.comodos for k in cotas_do_comodo(pav, c)]
