"""Cortes e elevações do cômodo (vistas verticais), em DXF (1 unidade = 1 mm).

Uma vista é um plano vertical: uma linha na planta (``p0`` → ``p1``), a direção
para onde se olha (perpendicular à linha) e até que profundidade se enxerga. No
desenho, x é a posição ao longo da linha (cresce para a direita de quem olha) e
y é a altura a partir do piso.

- **Elevação** de uma parede: plano paralelo à face, a ``DIST_ELEVACAO`` dela,
  olhando para ela. Mostra a face, as aberturas, as instalações, o rodapé e os
  móveis encostados; as paredes vizinhas aparecem cortadas nas pontas.
- **Corte** AA/BB: plano atravessando o cômodo; as paredes cortadas saem
  hachuradas (com o vão, se o corte passar numa porta/janela) e o resto é o que
  se vê além.

Só entra o que é do cômodo: suas paredes, as aberturas nelas, as instalações do
lado dele e os seus móveis. Não há remoção de linhas ocultas.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from datetime import date

from ezdxf.enums import TextEntityAlignment
from ezdxf.layouts.layout import Modelspace
from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import polylabel

from interiores_cad import __version__
from interiores_cad.estilo import (
    COR_PREENCHIMENTO_PAREDE,
    ESTILO_COTA,
    ESTILO_TEXTO,
    TRACEJADO,
    Texto,
    novo_documento,
)
from interiores_cad.folha import DadosCarimbo, desenhar_folha, escolher_folha
from interiores_cad.planta import LEGENDA, SIGLAS, Desenho
from interiores_core import geometria
from interiores_core.carregar import ProjetoCarregado
from interiores_core.modelo import (
    Comodo,
    Janela,
    Movel,
    Parede,
    Pavimento,
    PontoInstalacao,
    Porta,
    TipoInstalacao,
)

VERSAO_VISTAS = f"interiores-cad {__version__} · vistas v1"
DIST_ELEVACAO = 700.0
"""Distância (mm) do plano da elevação até a face da parede: o que estiver nessa
faixa (móveis encostados) aparece."""
EXTENSAO = 200.0
"""Quanto a linha da vista passa das faces internas, para cortar as paredes."""
COR_CORTE_MOVEL = (200, 200, 200)
GAS = TipoInstalacao.GAS

Vetor = tuple[float, float]


@dataclass(frozen=True)
class Vista:
    nome: str
    """Para o arquivo: ``corte-aa``, ``elevacao-p1``."""
    titulo: str
    p0: Vetor
    p1: Vetor
    olhar: Vetor
    """Direção para onde se olha (unitário, perpendicular a p0 → p1)."""
    profundidade: float
    elevacao: bool = False

    @property
    def u(self) -> Vetor:
        dx, dy = self.p1[0] - self.p0[0], self.p1[1] - self.p0[1]
        tam = math.hypot(dx, dy)
        return dx / tam, dy / tam

    @property
    def comprimento(self) -> float:
        return math.dist(self.p0, self.p1)

    def s(self, x: float, y: float) -> float:
        """Posição ao longo da linha (0 em p0)."""
        ux, uy = self.u
        return (x - self.p0[0]) * ux + (y - self.p0[1]) * uy

    def t(self, x: float, y: float) -> float:
        """Profundidade a partir do plano, na direção do olhar."""
        return (x - self.p0[0]) * self.olhar[0] + (y - self.p0[1]) * self.olhar[1]

    @property
    def faixa(self) -> Polygon:
        """Região da planta enxergada pela vista."""
        (ax, ay), (bx, by) = self.p0, self.p1
        dx, dy = self.olhar[0] * self.profundidade, self.olhar[1] * self.profundidade
        return Polygon([(ax, ay), (bx, by), (bx + dx, by + dy), (ax + dx, ay + dy)])


# ---------------------------------------------------------------- quais vistas


def _maior(geom: BaseGeometry | None) -> Polygon | None:
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return geom
    partes = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    return max(partes, key=lambda g: g.area, default=None)


def vistas_do_comodo(pav: Pavimento, comodo: Comodo) -> list[Vista]:
    """Cortes AA e BB pelo meio do cômodo e uma elevação por face de parede."""
    util = _maior(geometria.poligono_util(pav, comodo))
    if util is None:
        return []
    vistas: list[Vista] = []
    c = polylabel(util, tolerance=10)

    for nome, olhar in (("AA", (0.0, 1.0)), ("BB", (-1.0, 0.0))):
        direita = (olhar[1], -olhar[0])
        longe = 100_000.0
        linha = LineString(
            [
                (c.x - direita[0] * longe, c.y - direita[1] * longe),
                (c.x + direita[0] * longe, c.y + direita[1] * longe),
            ]
        )
        dentro = linha.intersection(util)
        pedacos = list(getattr(dentro, "geoms", [dentro]))
        pedaco = min(pedacos, key=lambda g: g.distance(c))
        (ax, ay), (bx, by) = pedaco.coords[0], pedaco.coords[-1]
        if (bx - ax) * direita[0] + (by - ay) * direita[1] < 0:
            (ax, ay), (bx, by) = (bx, by), (ax, ay)
        p0 = (ax - direita[0] * EXTENSAO, ay - direita[1] * EXTENSAO)
        p1 = (bx + direita[0] * EXTENSAO, by + direita[1] * EXTENSAO)
        vistas.append(Vista(f"corte-{nome.lower()}", f"Corte {nome}", p0, p1, olhar, 100_000.0))

    pts = [(float(x), float(y)) for x, y in orient(util, sign=1.0).exterior.coords]
    for p, q in itertools.pairwise(pts):
        tam = math.dist(p, q)
        if tam < 1:
            continue
        u = ((q[0] - p[0]) / tam, (q[1] - p[1]) / tam)
        fora = (u[1], -u[0])  # anel anti-horário: exterior à direita
        paredes = geometria.paredes_da_face(pav, comodo, p, q)
        ids = "-".join(par.id for par in paredes) or f"face{len(vistas) - 1}"
        dist = min(DIST_ELEVACAO, tam)  # não atravessa o cômodo em faces curtas
        # de dentro, olhando a parede, a direita é o sentido q → p
        p0 = (q[0] - fora[0] * dist + u[0] * EXTENSAO, q[1] - fora[1] * dist + u[1] * EXTENSAO)
        p1 = (p[0] - fora[0] * dist - u[0] * EXTENSAO, p[1] - fora[1] * dist - u[1] * EXTENSAO)
        vistas.append(
            Vista(f"elevacao-{ids}", f"Elevação da parede {ids}", p0, p1, fora, dist + 1, True)
        )
    return vistas


# ---------------------------------------------------------------- desenho


class _Desenhista:
    def __init__(
        self, carregado: ProjetoCarregado, pav: Pavimento, comodo: Comodo, vista: Vista
    ) -> None:
        self.carregado = carregado
        self.pav = pav
        self.comodo = comodo
        self.vista = vista
        self.pe = (comodo.pe_direito or pav.pe_direito).valor
        util = _maior(geometria.poligono_util(pav, comodo))
        assert util is not None
        self.util: Polygon = util
        dados = carregado.dados_comodos.get(comodo.id)
        self.moveis: list[Movel] = list(dados.moveis) if dados else []
        self.folha = escolher_folha((0, -300, vista.comprimento, self.pe + 300))
        self.doc = novo_documento(self.folha.escala)
        self.msp: Modelspace = self.doc.modelspace()

    # -- utilitários

    def mm(self, papel: float) -> float:
        return self.folha.mm(papel)

    def texto(
        self,
        texto: str,
        ponto: Vetor,
        altura: float,
        camada: str = "TEXTO",
        alinhamento: TextEntityAlignment = TextEntityAlignment.MIDDLE_CENTER,
        rotacao: float = 0,
    ) -> None:
        self.msp.add_text(
            texto,
            height=self.mm(altura),
            rotation=rotacao,
            dxfattribs={"layer": camada, "style": ESTILO_TEXTO},
        ).set_placement(ponto, align=alinhamento)

    def ret(
        self, x0: float, y0: float, x1: float, y1: float, camada: str, **attrs: object
    ) -> list[Vetor]:
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        self.msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": camada, **attrs})
        return pts

    def hachura(self, pts: list[Vetor], camada: str, cor: tuple[int, int, int]) -> None:
        h = self.msp.add_hatch(dxfattribs={"layer": camada})
        h.rgb = cor
        h.paths.add_polyline_path(pts, is_closed=True)

    def cota(self, p1: Vetor, p2: Vetor, base: Vetor) -> None:
        angulo = 0 if abs(p2[1] - p1[1]) < 1e-6 else 90
        self.msp.add_linear_dim(
            base=base,
            p1=p1,
            p2=p2,
            angle=angulo,
            dimstyle=ESTILO_COTA,
            dxfattribs={"layer": "COTA"},
        ).render()

    def faixa_s(self, geom: BaseGeometry) -> tuple[float, float]:
        coords = _coords(geom)
        ss = [self.vista.s(x, y) for x, y in coords]
        return min(ss), max(ss)

    def altura_parede(self, parede: Parede) -> float:
        return float(parede.altura.valor) if parede.altura else float(self.pe)

    # -- piso, forro e paredes cortadas

    @property
    def vao(self) -> tuple[float, float]:
        """Trecho útil da vista em s: no corte, entre as paredes cortadas; na elevação,
        a largura das faces de parede vistas (no canto de um L o cômodo continua ao
        lado, mas a elevação é só da parede)."""
        v = self.vista
        if v.elevacao:
            faces = self.faces()
            if faces:
                return min(f[0] for f in faces), max(f[1] for f in faces)
        dentro = LineString([v.p0, v.p1]).intersection(self.util)
        return self.faixa_s(dentro)

    def piso_e_forro(self) -> None:
        a, b = self.vao
        self.msp.add_line((a, 0), (b, 0), dxfattribs={"layer": "PAREDE", "lineweight": 50})
        self.msp.add_line((a, self.pe), (b, self.pe), dxfattribs={"layer": "PAREDE"})
        self.texto(
            f"forro (pé-direito {self.pe})",
            ((a + b) / 2, self.pe + self.mm(2.5)),
            Texto.INFO_COMODO,
        )

    def paredes_cortadas(self) -> list[tuple[float, float]]:
        """Hachura as paredes do cômodo que a linha atravessa; devolve as faixas em s."""
        v = self.vista
        linha = LineString([v.p0, v.p1])
        faixas = []
        for pid in self.comodo.paredes:
            parede = self.pav.parede(pid)
            if parede is None or geometria.comprimento(parede) == 0:
                continue
            corte = geometria.corpo(parede).intersection(linha)
            if corte.is_empty or corte.length < 1:
                continue
            s0, s1 = self.faixa_s(corte)
            altura = self.altura_parede(parede)
            # onde a linha cruza o eixo da parede, há abertura?
            cruza = geometria.eixo(parede).intersection(linha)
            vao = self.abertura_em(parede, cruza) if not cruza.is_empty else None
            trechos: list[tuple[float, float]] = [(0.0, altura)]
            if isinstance(vao, Porta):
                trechos = [(float(vao.altura.valor), altura)]
                self.msp.add_line((s0, 0), (s1, 0), dxfattribs={"layer": "ABERTURA"})
            elif isinstance(vao, Janela):
                pe, topo = float(vao.peitoril.valor), float(vao.peitoril.valor + vao.altura.valor)
                trechos = [(0.0, pe), (topo, altura)]
                meio = (s0 + s1) / 2
                for x in (s0, meio, s1):
                    self.msp.add_line((x, pe), (x, topo), dxfattribs={"layer": "ABERTURA"})
            for z0, z1 in trechos:
                if z1 - z0 < 1:
                    continue
                pts = self.ret(s0, z0, s1, z1, "PAREDE")
                self.hachura(pts, "PAREDE", COR_PREENCHIMENTO_PAREDE)
            faixas.append((s0, s1))
        return faixas

    def abertura_em(self, parede: Parede, ponto: BaseGeometry) -> Porta | Janela | None:
        px, py = _coords(ponto)[0]
        u, _ = geometria.direcao(parede)
        a = (px - parede.inicio[0]) * u[0] + (py - parede.inicio[1]) * u[1]
        for ab in self.pav.aberturas:
            if ab.parede == parede.id:
                d0 = ab.distancia_inicio.valor
                if d0 <= a <= d0 + ab.largura.valor:
                    return ab
        return None

    # -- o que se vê além

    def faces(self) -> list[tuple[float, float, list[Parede]]]:
        """Faces de parede do cômodo voltadas para quem olha, dentro da vista."""
        v = self.vista
        pts = [(float(x), float(y)) for x, y in orient(self.util, sign=1.0).exterior.coords]
        achadas = []
        for p, q in itertools.pairwise(pts):
            tam = math.dist(p, q)
            if tam < 1:
                continue
            u = ((q[0] - p[0]) / tam, (q[1] - p[1]) / tam)
            dentro = (-u[1], u[0])
            de_frente = dentro[0] * v.olhar[0] + dentro[1] * v.olhar[1] < -0.99
            if not de_frente or not v.faixa.intersects(LineString([p, q])):
                continue
            s0, s1 = sorted((v.s(*p), v.s(*q)))
            achadas.append((s0, s1, geometria.paredes_da_face(self.pav, self.comodo, p, q)))
        return achadas

    def desenhar_faces(self) -> None:
        rodape = self.pav.rodape.valor if self.pav.rodape else 0
        for s0, s1, paredes in self.faces():
            self.ret(s0, 0, s1, self.pe, "PAREDE", lineweight=18)
            if rodape:
                self.msp.add_line((s0, rodape), (s1, rodape), dxfattribs={"layer": "PAREDE"})
            for parede in paredes:
                self.aberturas_na_face(parede)
                self.instalacoes_na_face(parede)

    def aberturas_na_face(self, parede: Parede) -> None:
        u, _ = geometria.direcao(parede)
        for ab in self.pav.aberturas:
            if ab.parede != parede.id:
                continue
            d0 = ab.distancia_inicio.valor
            a = (parede.inicio[0] + u[0] * d0, parede.inicio[1] + u[1] * d0)
            b = (a[0] + u[0] * ab.largura.valor, a[1] + u[1] * ab.largura.valor)
            s0, s1 = sorted((self.vista.s(*a), self.vista.s(*b)))
            if isinstance(ab, Janela):
                z0, z1 = float(ab.peitoril.valor), float(ab.peitoril.valor + ab.altura.valor)
                self.ret(s0, z0, s1, z1, "ABERTURA")
                self.ret(s0 + 40, z0 + 40, s1 - 40, z1 - 40, "ABERTURA")
                self.cota((s1, 0), (s1, z0), (s1 + self.mm(4), 0))
                self.cota((s1, z0), (s1, z1), (s1 + self.mm(4), z0))
            else:
                z0, z1 = 0.0, float(ab.altura.valor)
                self.ret(s0, z0, s1, z1, "ABERTURA")
                self.cota((s1, z0), (s1, z1), (s1 + self.mm(4), z0))
                # folha: diagonal indicando o lado da dobradiça (convenção de elevação)
                if ab.folha == "giro":
                    na_dobradica = (ab.dobradica != "fim") == (self.vista.s(*a) < self.vista.s(*b))
                    xd = s0 if na_dobradica else s1
                    xo = s1 if na_dobradica else s0
                    self.msp.add_line(
                        (xo, z0),
                        (xd, (z0 + z1) / 2),
                        dxfattribs={"layer": "ABERTURA", "linetype": TRACEJADO},
                    )
                    self.msp.add_line(
                        (xd, (z0 + z1) / 2),
                        (xo, z1),
                        dxfattribs={"layer": "ABERTURA", "linetype": TRACEJADO},
                    )
            self.texto(ab.id, ((s0 + s1) / 2, z1 + self.mm(2)), Texto.ABERTURA, "ABERTURA")
            self.cota((s0, z1), (s1, z1), (s0, z1 + self.mm(6)))

    def instalacoes_na_face(self, parede: Parede) -> None:
        r = self.mm(1.4)
        for inst in self.pav.instalacoes:
            if (
                not isinstance(inst, PontoInstalacao)
                or inst.parede != parede.id
                or inst.comodo not in (None, self.comodo.id)
                or inst.tipo is GAS
            ):
                continue
            self.ponto(inst, r)

    def ponto(self, inst: PontoInstalacao, r: float) -> None:
        s = self.vista.s(*inst.posicao)
        z = float(inst.altura.valor)
        camada = (
            "ELETRICA"
            if inst.tipo
            in (TipoInstalacao.TOMADA, TipoInstalacao.INTERRUPTOR, TipoInstalacao.PONTO_LUZ)
            else "HIDRAULICA"
        )
        if inst.tipo is TipoInstalacao.TOMADA:
            self.ret(s - r, z - r, s + r, z + r, camada)
            self.msp.add_circle((s - r / 2.5, z), r / 5, dxfattribs={"layer": camada})
            self.msp.add_circle((s + r / 2.5, z), r / 5, dxfattribs={"layer": camada})
        else:
            self.msp.add_circle((s, z), r, dxfattribs={"layer": camada})
        rotulo = f"{SIGLAS[inst.tipo]} h{inst.altura.valor}"
        self.texto(
            rotulo, (s + r * 1.4, z), Texto.INSTALACAO, camada, TextEntityAlignment.MIDDLE_LEFT
        )

    def luzes(self) -> None:
        """Pontos de luz no teto dentro da vista (projetados no forro)."""
        for inst in self.pav.instalacoes:
            if (
                isinstance(inst, PontoInstalacao)
                and inst.parede is None
                and inst.tipo is TipoInstalacao.PONTO_LUZ
                and self.vista.faixa.contains(Point(inst.posicao))
                and self.util.contains(Point(inst.posicao))
            ):
                self.ponto(inst, self.mm(1.4))

    def moveis_(self) -> None:
        v = self.vista
        linha = LineString([v.p0, v.p1])
        for m in self.moveis:
            pol = geometria.poligono_movel(m)
            if not v.faixa.intersects(pol):
                continue
            s0, s1 = self.faixa_s(pol)
            a, b = self.vao
            s0, s1 = max(s0, a), min(s1, b)  # recorta no trecho da vista
            if s1 - s0 < 1:
                continue
            base = float(m.elevacao.valor) if m.elevacao else 0.0
            topo = base + m.altura.valor
            cortado = (not v.elevacao) and pol.intersects(linha)
            pts = self.ret(s0, base, s1, topo, "MOVEL")
            if cortado:
                self.hachura(pts, "MOVEL", COR_CORTE_MOVEL)
            nome = m.nome or m.id
            self.texto(
                nome, ((s0 + s1) / 2, (base + topo) / 2 + self.mm(1.2)), Texto.MOVEL, "MOVEL"
            )
            self.texto(
                f"h{topo:.0f}" + (f" (elev. {base:.0f})" if base else ""),
                ((s0 + s1) / 2, (base + topo) / 2 - self.mm(1.2)),
                Texto.MOVEL * 0.85,
                "MOVEL",
            )

    def cotas_gerais(self) -> None:
        a, b = self.vao
        self.cota((a, 0), (b, 0), (a, -self.mm(10)))
        self.cota((a, 0), (a, self.pe), (a - self.mm(8), 0))

    def desenhar(self, data: str) -> Desenho:
        self.piso_e_forro()
        self.desenhar_faces()
        self.paredes_cortadas()
        self.moveis_()
        self.luzes()
        self.cotas_gerais()
        v = self.vista
        aviso = (
            "vista de dentro do cômodo, olhando para a parede"
            if v.elevacao
            else "paredes cortadas hachuradas; o resto é o que se vê além"
        )
        self.texto(
            f"{v.titulo.upper()} — {self.comodo.nome}",
            (v.comprimento / 2, -self.mm(18)),
            Texto.CARIMBO,
        )
        self.texto(aviso, (v.comprimento / 2, -self.mm(22)), Texto.CARIMBO_PEQUENO)
        estimadas = self.carregado.estimadas(self.comodo.id)
        proj = self.carregado.projeto
        titulo = f"{v.titulo} — {self.comodo.nome}"
        desenhar_folha(
            self.msp,
            self.folha,
            DadosCarimbo(
                projeto=proj.projeto,
                apelido=proj.imovel.endereco_apelido,
                desenho=titulo,
                pavimento=self.pav.nome or self.pav.id,
                escopo=f"cômodo {self.comodo.id} · {v.nome}",
                data=data,
                hash_curto=self.carregado.hash_curto,
                gerador=VERSAO_VISTAS,
                estimadas=estimadas,
                legenda=(*LEGENDA, "alturas a partir do piso acabado; cotas em mm"),
            ),
        )
        return Desenho(self.doc, self.folha, titulo, estimadas)


def _coords(geom: BaseGeometry) -> list[Vetor]:
    if hasattr(geom, "geoms"):
        return [c for g in geom.geoms for c in _coords(g)]
    if isinstance(geom, Polygon):
        return [(float(x), float(y)) for x, y in geom.exterior.coords]
    return [(float(x), float(y)) for x, y in geom.coords]


def desenhar_vistas(
    carregado: ProjetoCarregado, pavimento: str, comodo: str, data: date | None = None
) -> list[tuple[Vista, Desenho]]:
    """Todos os cortes e elevações do cômodo."""
    pav = next((p for p in carregado.projeto.pavimentos if p.id == pavimento), None)
    if pav is None:
        raise KeyError(f"pavimento '{pavimento}' não existe no projeto")
    c = pav.comodo(comodo)
    if c is None:
        raise KeyError(f"cômodo '{comodo}' não está no pavimento '{pavimento}'")
    data_txt = (data or date.today()).isoformat()
    return [
        (v, _Desenhista(carregado, pav, c, v).desenhar(data_txt)) for v in vistas_do_comodo(pav, c)
    ]
