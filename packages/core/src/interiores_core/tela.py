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

from interiores_core import bancada, cotas, escadas, geometria, planejado
from interiores_core.medidas import medidas_estimadas
from interiores_core.modelo import (
    DadosComodo,
    Escada,
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
    estimada: bool = False
    """Alguma medida da parede (espessura, altura) é chute: a tela desenha tracejado."""


class AberturaTela(_Tela):
    id: str
    tipo: str
    parede: str
    vao: list[Pt]
    """Retângulo do vão dentro da parede (para "abrir" o desenho da parede)."""
    giro: list[Pt] | None = None
    """Área varrida pela folha (porta de giro)."""
    largura: int
    estimada: bool = False
    """Alguma medida do vão (largura, altura, posição, peitoril) é chute."""


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
    bancada: bool = False
    """Bancada/mesa planejada (tampo, pernas e módulos)."""
    detalhes: list[list[Pt]] = []
    """Contornos de dentro, para a planta (bancada: pernas, painéis e módulos)."""


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
    espaco: int | None = None
    """Índice do espaço no vão (de baixo para cima); na prateleira, o espaço logo abaixo."""


class ChapaTela(_Tela):
    material: str
    espessura: int
    area_m2: float
    chapas: int
    fita_metros: float


class PecaTela(_Tela):
    """Uma linha da lista de corte."""

    nome: str
    material: str
    espessura: int
    comprimento: float
    largura: float
    quantidade: int
    fita: str = ""
    """Bordas com fita: "1C" = um lado comprido, "2C2L" = os quatro lados..."""
    obs: str = ""


class PlanejadoTela(_Tela):
    """Vista de frente de um móvel planejado, já calculada, para o editor desenhar."""

    lista: list[PecaTela] = []
    """Lista de corte: cada peça com medidas, quantidade e fita de borda."""
    vistas: dict[str, list[RetanguloTela]] = {}
    """Bancada: vista de frente de cada trecho (``costas`` e, no L, ``braco``)."""
    modulos: dict[str, PlanejadoTela] = {}
    """Bancada: a vista de cada módulo (como um planejado comum), para montar por dentro."""

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


class EscadaTela(_Tela):
    """A conta da escada e o desenho dos degraus."""

    inicio: Pt
    """Pé da escada (no caracol, o centro): o ponto que anda ao arrastar."""
    degraus: list[list[Pt]]
    """Contorno de cada degrau (o patamar incluído), do primeiro ao último."""
    patamares: list[int] = []
    """Índices (em ``degraus``) dos patamares."""
    caminho: list[Pt]
    """Linha de subida, do pé à chegada (seta "sobe")."""
    desnivel: int
    espelhos: int
    espelho: float
    piso: float
    blondel: float
    lances: list[int]
    giro: float | None = None


class EstruturaTela(_Tela):
    """Pilar, viga ou laje projetados na planta."""

    id: str
    tipo: str
    """pilar, viga, laje, escada ou ``escada_abaixo`` (a escada do andar de baixo chegando:
    ``contorno`` é o vão dela na laje)."""
    contorno: list[Pt]
    """Projeção na planta (a laje, por fora; os furos vêm à parte)."""
    furos: list[list[Pt]] = []
    estimada: bool = False
    """Alguma medida (tamanho, espessura, altura) é chute."""
    escada: EscadaTela | None = None


class CotaTela(_Tela):
    """Cota pronta para desenhar (ver :mod:`interiores_core.cotas`)."""

    de: Pt
    ate: Pt
    lado: Pt
    """Para onde a cota sai da linha medida (unitário)."""
    fileira: int
    """0 = a mais perto da linha medida."""
    tipo: str
    """``comodo`` (face interna, por dentro), ``trecho`` (cadeia com as aberturas),
    ``eixo`` (eixos das paredes, por fora) ou ``geral`` (total externo)."""
    valor: int
    """mm."""
    comodo: str | None = None
    origem: str = "projeto"
    """De onde vêm as medidas que ela usa: ``trena``, ``projeto`` ou ``estimada`` (chute)."""


class PavimentoTela(_Tela):
    id: str
    paredes: list[ParedeTela]
    aberturas: list[AberturaTela]
    comodos: list[ComodoTela]
    moveis: list[MovelTela]
    instalacoes: list[InstalacaoTela]
    estrutura: list[EstruturaTela] = []
    cotas: list[CotaTela] = []
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
    pav: Pavimento,
    dados_comodos: Mapping[str, DadosComodo] | None = None,
    abaixo: Pavimento | None = None,
) -> PavimentoTela:
    """Tudo do pavimento (e o mobiliário dos cômodos dele) em polígonos prontos.

    ``abaixo``: o andar de baixo; as escadas dele aparecem aqui chegando (o vão e "desce").
    """
    dados_comodos = dados_comodos or {}
    paredes = [
        ParedeTela(
            id=p.id,
            eixo=(p.inicio, p.fim),
            corpo=_pts(geometria.corpo(p).exterior.coords[:-1]),
            espessura=p.espessura.valor,
            lado_a=p.lado_a,
            lado_b=p.lado_b,
            estimada=bool(medidas_estimadas(p)),
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
                estimada=bool(medidas_estimadas(a)),
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
            bancada=m.bancada is not None,
            detalhes=_detalhes_bancada(m),
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
    estrutura = []
    for e in pav.estrutura:
        g = geometria.poligono_estrutura(pav, e)
        if g is None:
            continue
        estrutura.append(
            EstruturaTela(
                id=e.id,
                tipo=e.tipo,
                contorno=_pts(g.exterior.coords[:-1]),
                furos=[_pts(f.coords[:-1]) for f in g.interiors],
                estimada=bool(medidas_estimadas(e)),
                escada=_escada_tela(pav, e) if isinstance(e, Escada) else None,
            )
        )
    if abaixo is not None:
        for e in abaixo.estrutura:
            if not isinstance(e, Escada) or (buraco := escadas.furo(abaixo, e)) is None:
                continue
            estrutura.append(
                EstruturaTela(
                    id=e.id,
                    tipo="escada_abaixo",
                    contorno=_pts(buraco.exterior.coords[:-1]),
                    escada=_escada_tela(abaixo, e),
                )
            )
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
        estrutura=estrutura,
        cotas=[
            CotaTela(
                de=_pts([k.de])[0],
                ate=_pts([k.ate])[0],
                lado=k.lado,
                fileira=k.fileira,
                tipo=k.tipo,
                valor=k.valor,
                comodo=k.comodo,
                origem=k.origem,
            )
            for k in cotas.cotas_do_pavimento(pav)
        ],
        limites=limites,
    )


def _escada_tela(pav: Pavimento, e: Escada) -> EscadaTela:
    c = escadas.calcular(pav, e)
    return EscadaTela(
        inicio=(float(e.inicio[0]), float(e.inicio[1])),
        degraus=[_pts(d.poligono.exterior.coords[:-1]) for d in c.degraus],
        patamares=[i for i, d in enumerate(c.degraus) if d.patamar],
        caminho=_pts(c.caminho),
        desnivel=round(c.desnivel),
        espelhos=c.espelhos,
        espelho=round(c.espelho, 1),
        piso=c.piso,
        blondel=round(c.blondel, 1),
        lances=list(c.lances),
        giro=round(c.giro) if c.giro is not None else None,
    )


def _detalhes_bancada(m: Movel) -> list[list[Pt]]:
    """Pernas, painéis e módulos da bancada, em coordenadas do pavimento (vazio se não for
    bancada ou se ela não fechar: aí a checagem aponta o erro)."""
    if m.bancada is None:
        return []
    try:
        calc = bancada.calcular(m)
    except planejado.ConstrucaoInvalidaError:
        return []
    saida = [_pts(geometria.cantos_movel(mod.movel)) for mod in calc.modulos]
    for p in calc.pernas:
        t = next(t for t in calc.trechos if t.nome == p.trecho)
        u, v = t.uv(p.x, p.y)
        if p.painel:
            e = m.bancada.tampo.espessura.valor
            cantos = [(u - e / 2, v - p.comprimento / 2), (u + e / 2, v + p.comprimento / 2)]
        else:
            meia = bancada.PERNA / 2
            cantos = [(u - meia, v - meia), (u + meia, v + meia)]
        (u0, v0), (u1, v1) = cantos
        locais = [t.ponto(a, b) for a, b in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
        saida.append(_pts([geometria.girar_movel(m, x, y) for x, y in locais]))
    return saida


def _retangulos(layout: list[planejado.Retangulo]) -> list[RetanguloTela]:
    return [
        RetanguloTela(
            tipo=x.tipo,
            x=round(x.x, 1),
            y=round(x.y, 1),
            largura=round(x.largura, 1),
            altura=round(x.altura, 1),
            rotulo=x.rotulo,
            vao=x.vao,
            espaco=x.espaco,
        )
        for x in layout
    ]


def planejado_para_tela(m: Movel) -> PlanejadoTela:
    """Vista de frente do móvel planejado ou da bancada (levanta ``ConstrucaoInvalidaError``/
    ``ValueError`` se a construção não fecha ou o móvel não é planejado)."""
    if m.bancada is not None:
        b = bancada.calcular(m)
        costas = b.trechos[0]
        return PlanejadoTela(
            largura=round(costas.comprimento),
            altura=m.altura.valor,
            retangulos=_retangulos(b.layout),
            larguras_vaos=[],
            alturas=[],
            pecas=sum(p.quantidade for p in b.pecas),
            chapas=_chapas(b),
            ferragens=[f"{f.quantidade}× {f.nome}" for f in b.ferragens],
            lista=_lista(b),
            vistas={nome: _retangulos(v) for nome, v in b.vistas.items()},
            modulos={m.modulo.id: planejado_para_tela(m.movel) for m in b.modulos},
        )
    if m.construcao is None:
        raise ValueError(f"o móvel '{m.id}' não é planejado (sem construção)")
    r = planejado.calcular(m)
    return PlanejadoTela(
        largura=m.largura.valor,
        altura=m.altura.valor,
        retangulos=_retangulos(r.layout),
        larguras_vaos=[round(v, 1) for v in r.larguras_vaos],
        alturas=[[round(a, 1) for a in col] for col in r.alturas],
        pecas=sum(p.quantidade for p in r.pecas),
        chapas=_chapas(r),
        ferragens=[f"{f.quantidade}× {f.nome}" for f in r.ferragens],
        lista=_lista(r),
    )


def _lista(r: planejado.Planejado) -> list[PecaTela]:
    return [
        PecaTela(
            nome=p.nome,
            material=p.material,
            espessura=p.espessura,
            comprimento=round(p.comprimento, 1),
            largura=round(p.largura, 1),
            quantidade=p.quantidade,
            fita=p.fita,
            obs=p.obs,
        )
        for p in r.pecas
    ]


def _chapas(r: planejado.Planejado) -> list[ChapaTela]:
    return [
        ChapaTela(
            material=c.material,
            espessura=c.espessura,
            area_m2=c.area_m2,
            chapas=c.chapas,
            fita_metros=c.fita_metros,
        )
        for c in r.chapas
    ]
