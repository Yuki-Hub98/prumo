"""Geometria derivada do modelo: polígonos dos cômodos, corpos de parede, lados.

Coordenadas em mm (float nos resultados derivados; as medidas de entrada são int).
"""

from __future__ import annotations

import math

from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from interiores_core.modelo import (
    Comodo,
    Movel,
    Parede,
    Pavimento,
    Pilar,
    PontoInstalacao,
    Porta,
)

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
    """Área livre do cômodo (polígono de eixo menos as paredes), ou ``None`` se não fechar.

    Vértices colineares que sobram do recorte (encontro de paredes de espessuras
    diferentes) são removidos: cada face de parede vira um único lado.
    """
    poligono = poligono_eixo(pavimento, comodo)
    if poligono is None:
        return None
    return poligono.difference(corpos_paredes(pavimento)).simplify(0)


def area_util_m2(pavimento: Pavimento, comodo: Comodo) -> float | None:
    """Área útil em m², arredondada a 2 casas."""
    util = poligono_util(pavimento, comodo)
    return None if util is None else round(util.area / 1_000_000, 2)


def direcao(parede: Parede) -> tuple[tuple[float, float], tuple[float, float]]:
    """Unitário ao longo da parede (início → fim) e normal à esquerda (lado ``a``)."""
    (x0, y0), (x1, y1) = parede.inicio, parede.fim
    tam = comprimento(parede)
    u = ((x1 - x0) / tam, (y1 - y0) / tam)
    return u, (-u[1], u[0])


def giro_porta(pavimento: Pavimento, porta: Porta, passos: int = 12) -> Polygon | None:
    """Quarto de círculo varrido pela folha de uma porta de giro (``None`` se for de correr).

    A dobradiça fica na face da parede do lado para onde a porta abre.
    """
    parede = pavimento.parede(porta.parede)
    if porta.folha != "giro" or parede is None or comprimento(parede) == 0:
        return None
    u, n = direcao(parede)
    s = 1 if porta.abre_para == parede.lado_a else -1
    meia = parede.espessura.valor / 2
    larg = porta.largura.valor
    d0 = porta.distancia_inicio.valor
    ini = (parede.inicio[0] + u[0] * d0, parede.inicio[1] + u[1] * d0)
    fim = (ini[0] + u[0] * larg, ini[1] + u[1] * larg)
    dobradica, outro = (ini, fim) if porta.dobradica != "fim" else (fim, ini)
    centro = (dobradica[0] + n[0] * s * meia, dobradica[1] + n[1] * s * meia)
    ang_folha = math.atan2(n[1] * s, n[0] * s)
    ang_fecha = math.atan2(outro[1] - dobradica[1], outro[0] - dobradica[0])
    varredura = (ang_folha - ang_fecha) % (2 * math.pi)
    sentido = 1 if abs(varredura - math.pi / 2) < 1e-6 else -1
    arco = [
        (
            centro[0] + larg * math.cos(ang_fecha + sentido * (math.pi / 2) * k / passos),
            centro[1] + larg * math.sin(ang_fecha + sentido * (math.pi / 2) * k / passos),
        )
        for k in range(passos + 1)
    ]
    return Polygon([centro, *arco])


_ROTACAO_PARA_FRENTE = {(0, 1): 0, (-1, 0): 90, (0, -1): 180, (1, 0): 270}


def na_parede(
    pavimento: Pavimento,
    comodo_id: str,
    parede_id: str,
    distancia: int,
    largura: int,
    profundidade: int,
) -> tuple[tuple[int, int], int]:
    """Centro e rotação de um móvel com as costas na face da parede, virado para o cômodo.

    ``distancia``: do início da parede até a borda do móvel, ao longo do eixo (a
    mesma referência de ``distancia_inicio`` das portas e janelas). A largura do
    móvel corre ao longo da parede.

    Levanta ``KeyError`` se a parede não existir e ``ValueError`` se ela não
    delimitar o cômodo ou não for horizontal/vertical (rotação só em 90°).
    """
    parede = pavimento.parede(parede_id)
    if parede is None:
        raise KeyError(f"parede '{parede_id}' não existe no pavimento '{pavimento.id}'")
    if comodo_id not in (parede.lado_a, parede.lado_b):
        raise ValueError(
            f"a parede '{parede_id}' não delimita o cômodo '{comodo_id}' "
            f"(lados: {parede.lado_a} | {parede.lado_b})"
        )
    u, n = direcao(parede)
    lado = 1 if parede.lado_a == comodo_id else -1
    frente = (round(n[0] * lado), round(n[1] * lado))
    if frente not in _ROTACAO_PARA_FRENTE or abs(n[0] * lado - frente[0]) > 1e-9:
        raise ValueError(f"a parede '{parede_id}' não é horizontal nem vertical")
    ao_longo = distancia + largura / 2
    afastado = parede.espessura.valor / 2 + profundidade / 2
    x = parede.inicio[0] + u[0] * ao_longo + frente[0] * afastado
    y = parede.inicio[1] + u[1] * ao_longo + frente[1] * afastado
    return (round(x), round(y)), _ROTACAO_PARA_FRENTE[frente]


_GIROS = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
"""cos e sen de cada rotação permitida (inteiros, sem erro de ponto flutuante)."""


def girar_movel(movel: Movel, x: float, y: float) -> tuple[float, float]:
    """Ponto no referencial do móvel (centro na origem, rotação 0) → coordenada global."""
    cos, sen = _GIROS[movel.rotacao]
    return (movel.centro[0] + x * cos - y * sen, movel.centro[1] + x * sen + y * cos)


def frente_movel(movel: Movel) -> tuple[int, int]:
    """Vetor unitário para onde o móvel está virado (lado de uso).

    Convenção (ver :class:`Movel`): em rotação 0 a frente é +y.
    """
    cos, sen = _GIROS[movel.rotacao]
    return (-sen, cos)


def cantos_movel(movel: Movel) -> list[tuple[float, float]]:
    """Cantos em ordem anti-horária, começando pelas costas.

    Ordem: costas-esq., costas-dir., frente-dir., frente-esq. ("esquerda/direita"
    no referencial do móvel em rotação 0, com x para a direita).
    """
    w, d = movel.largura.valor / 2, movel.profundidade.valor / 2
    return [girar_movel(movel, x, y) for x, y in ((-w, -d), (w, -d), (w, d), (-w, d))]


RAIO_PADRAO = 100
"""mm: raio dos cantos quando a forma é arredondada e o raio ainda não foi dado."""


def braco_l(movel: Movel) -> float:
    """Largura dos braços do L (dada, ou 40 % do lado menor)."""
    menor = min(movel.largura.valor, movel.profundidade.valor)
    return float(movel.braco.valor) if movel.braco else round(menor * 0.4)


def contorno_local(movel: Movel) -> Polygon:
    """Forma vista de cima no referencial do móvel (centro na origem, costas em -y, frente
    em +y). Retângulo, cantos arredondados, redondo/oval ou L (braço do lado ``lado_l`` de
    quem olha de frente: a esquerda dele é +x)."""
    w, d = movel.largura.valor / 2, movel.profundidade.valor / 2
    if movel.forma == "arredondado":
        r = min(float(movel.raio.valor) if movel.raio else RAIO_PADRAO, w, d)
        if r <= 0:
            return Polygon([(-w, -d), (w, -d), (w, d), (-w, d)])
        miolo = Polygon([(-w + r, -d + r), (w - r, -d + r), (w - r, d - r), (-w + r, d - r)])
        return miolo.buffer(r, quad_segs=8) if w > r and d > r else Point(0, 0).buffer(r, 8)
    if movel.forma == "redondo":
        pts = [(w * math.cos(a), d * math.sin(a)) for a in (i * math.pi / 32 for i in range(64))]
        return Polygon(pts)
    if movel.forma == "L":
        b = braco_l(movel)
        s = 1 if (movel.lado_l or "esquerda") == "esquerda" else -1
        # costas inteiras + braço que vem para a frente no lado escolhido
        pts = [(-w, -d), (w, -d), (w, d), (w - b, d), (w - b, -d + b), (-w, -d + b)]
        return Polygon([(x * s, y) for x, y in pts])
    return Polygon([(-w, -d), (w, -d), (w, d), (-w, d)])


def poligono_movel(movel: Movel) -> Polygon:
    """Projeção do móvel no piso (na forma dele: retângulo, arredondado, redondo, L)."""
    if movel.forma is None:
        return Polygon(cantos_movel(movel))
    return Polygon(
        [girar_movel(movel, x, y) for x, y in contorno_local(movel).exterior.coords[:-1]]
    )


def formas_possiveis(movel: Movel) -> tuple[str, ...]:
    """Formas que este móvel aceita: corpo simples (sob medida, banco, berço) e mesas; os
    outros (cama, sofá, guarda-roupa) e os planejados ficam retangulares."""
    from interiores_core.catalogo import Simbolo, item_do_tipo

    item = item_do_tipo(movel.tipo)
    simbolo = item.simbolo if item else Simbolo.GENERICO
    if movel.construcao is not None or simbolo not in (Simbolo.GENERICO, Simbolo.MESA):
        return ("retangular",)
    return ("retangular", "arredondado", "redondo", "L")


def paredes_da_face(
    pavimento: Pavimento, comodo: Comodo, p: tuple[float, float], q: tuple[float, float]
) -> list[Parede]:
    """Paredes do cômodo cuja face coincide com o lado p→q da área útil."""
    meio = Point((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    tam = math.dist(p, q)
    u = ((q[0] - p[0]) / tam, (q[1] - p[1]) / tam)
    achadas = []
    for pid in comodo.paredes:
        parede = pavimento.parede(pid)
        if parede is None or comprimento(parede) == 0:
            continue
        pu, _ = direcao(parede)
        paralela = abs(pu[0] * u[1] - pu[1] * u[0]) < 1e-6
        if paralela and abs(eixo(parede).distance(meio) - parede.espessura.valor / 2) < 2:
            achadas.append(parede)
    return achadas


def recorte_do_comodo(pavimento: Pavimento, comodo_id: str) -> Pavimento:
    """Cópia do pavimento só com o que pertence ao cômodo (para carimbo e desenho).

    Mantém: as paredes do cômodo, aberturas nessas paredes, instalações e estrutura
    dentro ou na borda do polígono de eixo. Ponto com ``comodo`` de outro cômodo
    fica de fora (ex.: ponto da pia do banheiro na parede que divide com o quarto).
    Se o cômodo não fechar, fica com as paredes e aberturas apenas.
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
        if (
            isinstance(i, PontoInstalacao)
            and i.comodo in (None, comodo_id)
            and (i.parede in ids or toca(Point(i.posicao)))
        )
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
