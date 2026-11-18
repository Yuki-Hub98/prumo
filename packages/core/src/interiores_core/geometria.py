"""Geometria derivada do modelo: polígonos dos cômodos, corpos de parede, lados.

Coordenadas em mm (float nos resultados derivados; as medidas de entrada são int).
"""

from __future__ import annotations

import math

from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from interiores_core.modelo import Comodo, Parede, Pavimento, Pilar, PontoInstalacao

FOLGA_LADO = 10.0
"""Distância extra além da face da parede ao testar de que lado está um cômodo."""


def comprimento(parede: Parede) -> float:
    """Comprimento do eixo da parede, em mm."""
    (x0, y0), (x1, y1) = parede.inicio, parede.fim
    return math.hypot(x1 - x0, y1 - y0)


def eixo(parede: Parede) -> LineString:
    return LineString([parede.inicio, parede.fim])


def corpo(parede: Parede) -> Polygon:
    """Retângulo ocupado pela parede (eixo ± meia espessura, pontas em esquadro)."""
    meia = parede.espessura.valor / 2
    geom = eixo(parede).buffer(meia, cap_style="square", join_style="mitre")
    assert isinstance(geom, Polygon)
    return geom


def ponto_ao_lado(parede: Parede, lado: str, distancia: float | None = None) -> Point:
    """Ponto a partir do meio da parede, do lado ``"a"`` (esquerda) ou ``"b"`` (direita)."""
    (x0, y0), (x1, y1) = parede.inicio, parede.fim
    tam = comprimento(parede)
    if distancia is None:
        distancia = parede.espessura.valor / 2 + FOLGA_LADO
    nx, ny = -(y1 - y0) / tam, (x1 - x0) / tam  # normal à esquerda
    sinal = 1 if lado == "a" else -1
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    return Point(mx + sinal * nx * distancia, my + sinal * ny * distancia)


def poligono_eixo(pavimento: Pavimento, comodo: Comodo) -> Polygon | None:
    """Polígono pelos eixos das paredes do cômodo, ou ``None`` se não fechar.

    Fecha quando os eixos formam exatamente um anel que usa todas as paredes.
    """
    paredes = [pavimento.parede(pid) for pid in comodo.paredes]
    if any(p is None or comprimento(p) == 0 for p in paredes):
        return None
    linhas = [eixo(p) for p in paredes if p is not None]
    poligonos = list(polygonize(unary_union(linhas)))
    if len(poligonos) != 1:
        return None
    poligono = poligonos[0]
    contorno = poligono.exterior
    if not all(contorno.covers(linha) for linha in linhas):
        return None
    return poligono


def corpos_paredes(pavimento: Pavimento) -> BaseGeometry:
    """União de todos os corpos de parede do pavimento."""
    return unary_union([corpo(p) for p in pavimento.paredes if comprimento(p) > 0])


def poligono_util(pavimento: Pavimento, comodo: Comodo) -> BaseGeometry | None:
    """Área livre do cômodo (polígono de eixo menos as paredes), ou ``None`` se não fechar."""
    poligono = poligono_eixo(pavimento, comodo)
    if poligono is None:
        return None
    return poligono.difference(corpos_paredes(pavimento))


def area_util_m2(pavimento: Pavimento, comodo: Comodo) -> float | None:
    """Área útil em m², arredondada a 2 casas."""
    util = poligono_util(pavimento, comodo)
    return None if util is None else round(util.area / 1_000_000, 2)


def recorte_do_comodo(pavimento: Pavimento, comodo_id: str) -> Pavimento:
    """Cópia do pavimento só com o que pertence ao cômodo (para carimbo e desenho).

    Mantém: as paredes do cômodo, aberturas nessas paredes, instalações e estrutura
    dentro ou na borda do polígono de eixo. Se o cômodo não fechar, fica com as
    paredes e aberturas apenas.
    """
    comodo = pavimento.comodo(comodo_id)
    if comodo is None:
        raise KeyError(f"cômodo '{comodo_id}' não está no pavimento '{pavimento.id}'")
    ids = set(comodo.paredes)
    poligono = poligono_eixo(pavimento, comodo)

    def toca(geom: BaseGeometry) -> bool:
        return poligono is not None and poligono.intersects(geom)

    instalacoes = [
        i
        for i in pavimento.instalacoes
        if (isinstance(i, PontoInstalacao) and (i.parede in ids or toca(Point(i.posicao))))
        or (not isinstance(i, PontoInstalacao) and toca(LineString(i.caminho)))
    ]
    estrutura = [
        e
        for e in pavimento.estrutura
        if toca(Point(e.centro) if isinstance(e, Pilar) else LineString([e.inicio, e.fim]))
    ]
    return pavimento.model_copy(
        update={
            "paredes": [p for p in pavimento.paredes if p.id in ids],
            "aberturas": [a for a in pavimento.aberturas if a.parede in ids],
            "instalacoes": instalacoes,
            "estrutura": estrutura,
            "comodos": [comodo],
        }
    )
