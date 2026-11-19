"""Geometria pronta para desenhar o pavimento numa tela (frontend).

O frontend não recalcula nada: recebe polígonos em mm, no sistema do pavimento
(y para cima), e só desenha. Assim a regra de "onde fica o vão", "para onde a
porta gira" ou "quais são os cantos do móvel girado" mora num lugar só (o core),
igual para CAD, render e tela.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict
from shapely import Polygon
from shapely.geometry.base import BaseGeometry

from interiores_core import geometria
from interiores_core.modelo import (
    DadosComodo,
    Janela,
    Pavimento,
    PontoInstalacao,
    Porta,
)

Pt = tuple[float, float]


class _Tela(BaseModel):
    model_config = ConfigDict(frozen=True)


class ParedeTela(_Tela):
    id: str
    eixo: tuple[Pt, Pt]
    corpo: list[Pt]
    """Retângulo da parede (eixo ± meia espessura)."""
    espessura: int
    lado_a: str
    lado_b: str


class AberturaTela(_Tela):
    id: str
    tipo: str
    parede: str
    vao: list[Pt]
    """Retângulo do vão dentro da parede (para "abrir" o desenho da parede)."""
    giro: list[Pt] | None = None
    """Área varrida pela folha (porta de giro)."""
    largura: int


class ComodoTela(_Tela):
    id: str
    nome: str
    tipo: str
    poligono: list[Pt] | None
    """Área útil (sem as paredes); ``None`` se o cômodo ainda não fecha."""
    area_m2: float | None
    centro: Pt | None
    """Ponto para o rótulo (sempre dentro do polígono)."""


class MovelTela(_Tela):
    id: str
    comodo: str
    tipo: str
    nome: str | None
    centro: tuple[int, int]
    rotacao: int
    cantos: list[Pt]
    """Anti-horário, começando pelas costas (costas-esq., costas-dir., frente-dir., frente-esq.)."""
    frente: tuple[int, int]
    elevado: bool
    """Não ocupa o piso (TV na parede, armário aéreo)."""


class InstalacaoTela(_Tela):
    id: str
    tipo: str
    forma: str
    posicao: Pt | None = None
    caminho: list[Pt] | None = None
    parede: str | None = None


class PavimentoTela(_Tela):
    id: str
    paredes: list[ParedeTela]
    aberturas: list[AberturaTela]
    comodos: list[ComodoTela]
    moveis: list[MovelTela]
    instalacoes: list[InstalacaoTela]
    limites: tuple[Pt, Pt] | None
    """Canto inferior-esquerdo e superior-direito de tudo (para enquadrar)."""


def _pts(coords: object) -> list[Pt]:
    return [(round(x, 1), round(y, 1)) for x, y in coords]  # type: ignore[attr-defined]


def _maior(g: BaseGeometry) -> Polygon | None:
    if isinstance(g, Polygon):
        return g
    poligonos = [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
    return max(poligonos, key=lambda p: p.area) if poligonos else None


def _vao(pav: Pavimento, a: Porta | Janela) -> list[Pt] | None:
    parede = pav.parede(a.parede)
    if parede is None or geometria.comprimento(parede) == 0:
        return None
    u, n = geometria.direcao(parede)
    meia = parede.espessura.valor / 2
    d0, d1 = a.distancia_inicio.valor, a.distancia_inicio.valor + a.largura.valor
    x0, y0 = parede.inicio
    p0 = (x0 + u[0] * d0, y0 + u[1] * d0)
    p1 = (x0 + u[0] * d1, y0 + u[1] * d1)
    return _pts(
        [
            (p0[0] + n[0] * meia, p0[1] + n[1] * meia),
            (p1[0] + n[0] * meia, p1[1] + n[1] * meia),
            (p1[0] - n[0] * meia, p1[1] - n[1] * meia),
            (p0[0] - n[0] * meia, p0[1] - n[1] * meia),
        ]
    )


def pavimento_para_tela(
    pav: Pavimento, dados_comodos: Mapping[str, DadosComodo] | None = None
) -> PavimentoTela:
    """Tudo do pavimento (e o mobiliário dos cômodos dele) em polígonos prontos."""
    dados_comodos = dados_comodos or {}
    paredes = [
        ParedeTela(
            id=p.id,
            eixo=(p.inicio, p.fim),
            corpo=_pts(geometria.corpo(p).exterior.coords[:-1]),
            espessura=p.espessura.valor,
            lado_a=p.lado_a,
            lado_b=p.lado_b,
        )
        for p in pav.paredes
        if geometria.comprimento(p) > 0
    ]
    aberturas = []
    for a in pav.aberturas:
        vao = _vao(pav, a)
        if vao is None:
            continue
        giro = geometria.giro_porta(pav, a) if isinstance(a, Porta) else None
        aberturas.append(
            AberturaTela(
                id=a.id,
                tipo=a.tipo,
                parede=a.parede,
                vao=vao,
                giro=_pts(giro.exterior.coords[:-1]) if giro is not None else None,
                largura=a.largura.valor,
            )
        )
    comodos = []
    for c in pav.comodos:
        util = geometria.poligono_util(pav, c)
        alvo = _maior(util) if util is not None else None
        rotulo = alvo.representative_point() if alvo is not None else None
        comodos.append(
            ComodoTela(
                id=c.id,
                nome=c.nome,
                tipo=c.tipo,
                poligono=_pts(alvo.exterior.coords[:-1]) if alvo is not None else None,
                area_m2=geometria.area_util_m2(pav, c),
                centro=(round(rotulo.x, 1), round(rotulo.y, 1)) if rotulo is not None else None,
            )
        )
    moveis = [
        MovelTela(
            id=m.id,
            comodo=c.id,
            tipo=m.tipo,
            nome=m.nome,
            centro=m.centro,
            rotacao=m.rotacao,
            cantos=_pts(geometria.cantos_movel(m)),
            frente=geometria.frente_movel(m),
            elevado=not m.ocupa_piso,
        )
        for c in pav.comodos
        for m in (dados_comodos[c.id].moveis if c.id in dados_comodos else [])
    ]
    instalacoes = [
        InstalacaoTela(
            id=i.id,
            tipo=i.tipo,
            forma=i.forma,
            posicao=i.posicao if isinstance(i, PontoInstalacao) else None,
            caminho=None if isinstance(i, PontoInstalacao) else _pts(i.caminho),
            parede=i.parede if isinstance(i, PontoInstalacao) else None,
        )
        for i in pav.instalacoes
    ]
    xs = [x for p in paredes for x, _ in p.corpo] + [x for m in moveis for x, _ in m.cantos]
    ys = [y for p in paredes for _, y in p.corpo] + [y for m in moveis for _, y in m.cantos]
    limites = ((min(xs), min(ys)), (max(xs), max(ys))) if xs else None
    return PavimentoTela(
        id=pav.id,
        paredes=paredes,
        aberturas=aberturas,
        comodos=comodos,
        moveis=moveis,
        instalacoes=instalacoes,
        limites=limites,
    )
