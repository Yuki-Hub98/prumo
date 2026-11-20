"""Geometria pronta para desenhar o pavimento numa tela (frontend).

O frontend não recalcula nada: recebe polígonos em mm, no sistema do pavimento
(y para cima), e só desenha. Assim a regra de "onde fica o vão", "para onde a
porta gira" ou "quais são os cantos do móvel girado" mora num lugar só (o core),
igual para CAD, render e tela.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import pairwise

from pydantic import BaseModel, ConfigDict
from shapely import Polygon
from shapely.geometry.base import BaseGeometry

from interiores_core import geometria, planejado
from interiores_core.modelo import (
    DadosComodo,
    Janela,
    Movel,
    Pavimento,
    PontoInstalacao,
    Porta,
)
from interiores_core.partes import PARTES, partes_do_movel

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


class FaceTela(_Tela):
    parede: str
    de: Pt
    ate: Pt
    """Lado da área útil do cômodo que é a face desta parede (para pintar)."""


class ComodoTela(_Tela):
    id: str
    nome: str
    tipo: str
    poligono: list[Pt] | None
    """Área útil (sem as paredes); ``None`` se o cômodo ainda não fecha."""
    area_m2: float | None
    centro: Pt | None
    """Ponto para o rótulo (sempre dentro do polígono)."""
    faces: list[FaceTela] = []
    """Faces das paredes voltadas para o cômodo (cor por parede)."""


class ParteTela(_Tela):
    id: str
    nome: str


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
    partes: list[ParteTela] = []
    """Partes com cor própria (portas, gavetas...), além do corpo."""
    planejavel: bool = False
    """Dá para montar por dentro (vãos, gavetas, portas, prateleiras)."""
    contorno: list[Pt] = []
    """Forma vista de cima (retângulo, arredondado, redondo, L), para desenhar na planta."""
    forma: str = "retangular"
    formas: list[str] = []
    """Formas que este móvel aceita (só "retangular": não muda de forma)."""
    planejado: bool = False
    """Já tem construção (é planejado)."""


class RetanguloTela(_Tela):
    tipo: str
    """lateral, base, tampo, divisoria, rodape, prateleira, gaveta, nicho, cabideiro, porta."""
    x: float
    y: float
    """mm a partir do canto de baixo à esquerda (olhando de frente)."""
    largura: float
    altura: float
    rotulo: str = ""
    vao: int | None = None


class ChapaTela(_Tela):
    material: str
    espessura: int
    area_m2: float
    chapas: int
    fita_metros: float


class PlanejadoTela(_Tela):
    """Vista de frente de um móvel planejado, já calculada, para o editor desenhar."""

    largura: int
    altura: int
    retangulos: list[RetanguloTela]
    larguras_vaos: list[float]
    alturas: list[list[float]]
    """Altura de cada espaço, por vão (de baixo para cima)."""
    pecas: int
    """Peças de chapa (somando as quantidades)."""
    chapas: list[ChapaTela]
    ferragens: list[str]


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
        faces = []
        if alvo is not None:
            anel: list[Pt] = [(x, y) for x, y in alvo.exterior.coords]
            for p0, p1 in pairwise(anel):
                for w in geometria.paredes_da_face(pav, c, p0, p1):
                    faces.append(FaceTela(parede=w.id, de=_pts([p0])[0], ate=_pts([p1])[0]))
        comodos.append(
            ComodoTela(
                id=c.id,
                nome=c.nome,
                tipo=c.tipo,
                poligono=_pts(alvo.exterior.coords[:-1]) if alvo is not None else None,
                area_m2=geometria.area_util_m2(pav, c),
                centro=(round(rotulo.x, 1), round(rotulo.y, 1)) if rotulo is not None else None,
                faces=faces,
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
            partes=[ParteTela(id=p, nome=PARTES[p]) for p in partes_do_movel(m)],
            planejavel=m.tipo in planejado.TIPOS_PLANEJAVEIS,
            contorno=_pts(list(geometria.poligono_movel(m).exterior.coords)[:-1]),
            forma=m.forma or "retangular",
            formas=list(geometria.formas_possiveis(m)),
            planejado=m.construcao is not None,
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


def planejado_para_tela(m: Movel) -> PlanejadoTela:
    """Vista de frente do móvel planejado (levanta ``ConstrucaoInvalidaError``/``ValueError``
    se a construção não fecha ou o móvel não tem construção)."""
    if m.construcao is None:
        raise ValueError(f"o móvel '{m.id}' não é planejado (sem construção)")
    r = planejado.calcular(m)
    return PlanejadoTela(
        largura=m.largura.valor,
        altura=m.altura.valor,
        retangulos=[
            RetanguloTela(
                tipo=x.tipo,
                x=round(x.x, 1),
                y=round(x.y, 1),
                largura=round(x.largura, 1),
                altura=round(x.altura, 1),
                rotulo=x.rotulo,
                vao=x.vao,
            )
            for x in r.layout
        ],
        larguras_vaos=[round(v, 1) for v in r.larguras_vaos],
        alturas=[[round(a, 1) for a in col] for col in r.alturas],
        pecas=sum(p.quantidade for p in r.pecas),
        chapas=[
            ChapaTela(
                material=c.material,
                espessura=c.espessura,
                area_m2=c.area_m2,
                chapas=c.chapas,
                fita_metros=c.fita_metros,
            )
            for c in r.chapas
        ],
        ferragens=[f"{f.quantidade}× {f.nome}" for f in r.ferragens],
    )
