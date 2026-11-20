"""Planta baixa em DXF (1 unidade = 1 mm), por escopo: cômodo ou pavimento.

Só desenha: medidas, posições e consistência vêm prontas do ``core``.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from datetime import date

from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment
from ezdxf.layouts.layout import Modelspace
from shapely import LineString, MultiPolygon, Point, Polygon
from shapely.affinity import translate
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import polylabel, unary_union

from interiores_cad import __version__
from interiores_cad.estilo import (
    COR_PREENCHIMENTO_PAREDE,
    ESTILO_COTA,
    ESTILO_TEXTO,
    TRACEJADO,
    Texto,
    novo_documento,
)
from interiores_cad.folha import (
    LARGURA_LETRA,
    DadosCarimbo,
    Folha,
    desenhar_folha,
    escolher_folha,
)
from interiores_core import catalogo, geometria
from interiores_core.carregar import ProjetoCarregado
from interiores_core.catalogo import Simbolo
from interiores_core.medidas import Medida
from interiores_core.modelo import (
    EXTERNO,
    Comodo,
    Janela,
    Movel,
    Parede,
    Pavimento,
    PontoInstalacao,
    Porta,
    TipoInstalacao,
)
from interiores_core.regras import VERSAO_REGRAS, checar

VERSAO_GERADOR = f"interiores-cad {__version__} · planta v7 · {VERSAO_REGRAS}"
"""Entra na chave de cache das saídas: mudou o desenho, suba o ``planta vN``.

Inclui a versão das regras porque as checagens são desenhadas na planta.
"""

ELETRICOS = {TipoInstalacao.TOMADA, TipoInstalacao.INTERRUPTOR, TipoInstalacao.PONTO_LUZ}
HIDRAULICOS = {
    TipoInstalacao.AGUA_FRIA,
    TipoInstalacao.AGUA_QUENTE,
    TipoInstalacao.ESGOTO,
    TipoInstalacao.RALO,
}
SIGLAS = {
    TipoInstalacao.TOMADA: "T",
    TipoInstalacao.INTERRUPTOR: "S",
    TipoInstalacao.PONTO_LUZ: "luz",
    TipoInstalacao.AGUA_FRIA: "AF",
    TipoInstalacao.AGUA_QUENTE: "AQ",
    TipoInstalacao.ESGOTO: "ES",
    TipoInstalacao.RALO: "ralo",
    TipoInstalacao.GAS: "gás",
}
LEGENDA = (
    "T tomada · S interruptor · luz ponto de luz",
    "AF água fria · AQ água quente · ES esgoto · ralo",
    "h = altura do piso (mm)",
)


def _camada_instalacao(tipo: TipoInstalacao) -> str | None:
    if tipo in ELETRICOS:
        return "ELETRICA"
    if tipo in HIDRAULICOS:
        return "HIDRAULICA"
    return None  # gás não é desenhado


Vetor = tuple[float, float]


NOME_JANELA = {
    "correr": "correr",
    "basculante": "basculante",
    "maxim_ar": "maxim-ar",
    "abrir": "de abrir",
    "fixa": "fixa",
}


@dataclass
class Desenho:
    """DXF pronto e o que o PDF e o carimbo precisam saber dele."""

    doc: Drawing
    folha: Folha
    titulo: str
    estimadas: list[tuple[str, Medida]] = field(default_factory=list)

    @property
    def preliminar(self) -> bool:
        return bool(self.estimadas)


# ---------------------------------------------------------------- vetores


def _som(a: Vetor, b: Vetor, k: float = 1.0) -> Vetor:
    return (a[0] + b[0] * k, a[1] + b[1] * k)


def _direcao(parede: Parede) -> tuple[Vetor, Vetor]:
    """Unitário ao longo da parede e normal à esquerda (lado ``a``)."""
    (x0, y0), (x1, y1) = parede.inicio, parede.fim
    tam = geometria.comprimento(parede)
    u = ((x1 - x0) / tam, (y1 - y0) / tam)
    return u, (-u[1], u[0])


def _angulo(v: Vetor) -> float:
    return math.degrees(math.atan2(v[1], v[0])) % 360


def _angulo_legivel(v: Vetor) -> float:
    """Ângulo de texto ao longo de ``v`` sem ficar de cabeça para baixo."""
    a = _angulo(v)
    return a - 180 if 90 < a <= 270 else a


# ---------------------------------------------------------------- planta


class _Planta:
    def __init__(
        self,
        carregado: ProjetoCarregado,
        pavimento: Pavimento,
        comodos: list[Comodo],
        recorte: Pavimento,
        por_comodo: bool,
    ) -> None:
        self.carregado = carregado
        self.pavimento = pavimento
        self.comodos = comodos
        self.recorte = recorte
        self.por_comodo = por_comodo
        self.moveis: list[Movel] = [
            m
            for c in comodos
            if c.id in carregado.dados_comodos
            for m in carregado.dados_comodos[c.id].moveis
        ]
        self.ids_comodos = {c.id for c in comodos}
        self.giros: list[Polygon] = []
        """Área varrida pelas folhas de porta (rótulos não podem cair nela)."""
        self.corpos = unary_union(
            [geometria.corpo(p) for p in recorte.paredes if geometria.comprimento(p) > 0]
        )
        self.folha = escolher_folha(self.corpos.bounds)
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
        camada: str,
        rotacao: float = 0.0,
        alinhamento: TextEntityAlignment = TextEntityAlignment.MIDDLE_CENTER,
    ) -> None:
        self.msp.add_text(
            texto,
            height=self.mm(altura),
            rotation=rotacao,
            dxfattribs={"layer": camada, "style": ESTILO_TEXTO},
        ).set_placement(ponto, align=alinhamento)

    def lado_do_comodo(self, parede: Parede) -> int:
        """+1 se o cômodo desenhado fica à esquerda da parede (lado ``a``), senão -1."""
        if parede.lado_a in self.ids_comodos:
            return 1
        if parede.lado_b in self.ids_comodos:
            return -1
        return 1 if parede.lado_a != EXTERNO else -1

    # -- paredes

    def vao(self, parede: Parede, inicio: float, largura: float) -> Polygon:
        u, n = _direcao(parede)
        meia = parede.espessura.valor / 2 + 1
        a0 = _som(parede.inicio, u, inicio)
        a1 = _som(a0, u, largura)
        return Polygon(
            [_som(a0, n, meia), _som(a1, n, meia), _som(a1, n, -meia), _som(a0, n, -meia)]
        )

    def paredes(self) -> None:
        vaos = [
            self.vao(p, a.distancia_inicio.valor, a.largura.valor)
            for a in self.recorte.aberturas
            if (p := self.recorte.parede(a.parede)) is not None
        ]
        cheio = self.corpos.difference(unary_union(vaos)) if vaos else self.corpos
        poligonos = list(cheio.geoms) if isinstance(cheio, MultiPolygon) else [cheio]
        for pol in poligonos:
            if not isinstance(pol, Polygon) or pol.is_empty:
                continue
            pol = orient(pol)
            hachura = self.msp.add_hatch(dxfattribs={"layer": "PAREDE"})
            hachura.rgb = COR_PREENCHIMENTO_PAREDE
            hachura.paths.add_polyline_path(list(pol.exterior.coords)[:-1], is_closed=True)
            for furo in pol.interiors:
                hachura.paths.add_polyline_path(list(furo.coords)[:-1], is_closed=True)
            for anel in (pol.exterior, *pol.interiors):
                self.msp.add_lwpolyline(
                    list(anel.coords)[:-1], close=True, dxfattribs={"layer": "PAREDE"}
                )

    # -- aberturas

    def aberturas(self) -> None:
        for ab in self.recorte.aberturas:
            parede = self.recorte.parede(ab.parede)
            if parede is None:
                continue
            u, n = _direcao(parede)
            meia = parede.espessura.valor / 2
            a0 = _som(parede.inicio, u, ab.distancia_inicio.valor)
            a1 = _som(a0, u, ab.largura.valor)
            larg = ab.largura.valor
            if isinstance(ab, Janela):
                for off in (-meia, -20.0, 20.0, meia):
                    self.msp.add_line(
                        _som(a0, n, off), _som(a1, n, off), dxfattribs={"layer": "ABERTURA"}
                    )
                lado_etiqueta = -self.lado_do_comodo(parede)
                # tipo só se informado (janela antiga sem tipo continua como era)
                tipo = f" {NOME_JANELA[ab.abertura]}" if ab.abertura else ""
                etiqueta = f"{ab.id}{tipo} {larg}×{ab.altura.valor} peit. {ab.peitoril.valor}"
            else:
                lado_etiqueta = self.porta(ab, parede, a0, a1, u, n, meia)
                etiqueta = f"{ab.id} {larg}×{ab.altura.valor}"
            meio = _som(_som(a0, u, larg / 2), n, lado_etiqueta * (meia + self.mm(3.5)))
            self.texto(etiqueta, meio, Texto.ABERTURA, "ABERTURA", _angulo_legivel(u))

    def porta(
        self, porta: Porta, parede: Parede, a0: Vetor, a1: Vetor, u: Vetor, n: Vetor, meia: float
    ) -> int:
        """Desenha folha e arco; devolve o lado (±1) livre para a etiqueta."""
        larg = porta.largura.valor
        if porta.folha == "correr":
            for off, (ini, fim) in ((-meia / 3, (0.0, 0.55)), (meia / 3, (0.45, 1.0))):
                self.msp.add_line(
                    _som(_som(a0, u, larg * ini), n, off),
                    _som(_som(a0, u, larg * fim), n, off),
                    dxfattribs={"layer": "ABERTURA"},
                )
            return -self.lado_do_comodo(parede)
        s = 1 if porta.abre_para == parede.lado_a else -1
        dobradica, outro = (a0, a1) if porta.dobradica != "fim" else (a1, a0)
        centro = _som(dobradica, n, s * meia)
        if porta.folha == "camarao":
            # duas folhas dobradas em "V" junto da dobradiça; arco de meia largura
            v = (outro[0] - dobradica[0], outro[1] - dobradica[1])
            tam = math.hypot(*v) or 1.0
            v = (v[0] / tam, v[1] / tam)
            meia_f = larg / 2
            dobra = _som(_som(centro, v, meia_f * 0.5), n, s * meia_f * 0.866)
            volta = _som(centro, v, meia_f)
            self.msp.add_line(centro, dobra, dxfattribs={"layer": "ABERTURA"})
            self.msp.add_line(dobra, volta, dxfattribs={"layer": "ABERTURA"})
            raio = meia_f
        else:
            raio = larg
            self.msp.add_line(centro, _som(centro, n, s * larg), dxfattribs={"layer": "ABERTURA"})
        ang_folha = _angulo((n[0] * s, n[1] * s))
        ang_fecha = _angulo((outro[0] - dobradica[0], outro[1] - dobradica[1]))
        ini, fim = (ang_fecha, ang_folha)
        if round((ang_folha - ang_fecha) % 360) != 90:
            ini, fim = fim, ini
        self.msp.add_arc(centro, raio, ini, fim, dxfattribs={"layer": "ABERTURA"})
        giro = geometria.giro_porta(self.recorte, porta)
        if giro is not None:
            self.giros.append(giro)
        # soleira: linha do vão na face oposta ao giro
        self.msp.add_line(
            _som(a0, n, -s * meia), _som(a1, n, -s * meia), dxfattribs={"layer": "ABERTURA"}
        )
        return -s

    # -- móveis

    def moveis_(self) -> None:
        """Contorno, símbolo do tipo (catálogo), nome e dimensões.

        Móvel elevado (TV na parede, armário aéreo) sai tracejado, como na convenção
        de planta para o que está acima do plano de corte.
        """
        for m in self.moveis:
            cam: dict[str, object] = {"layer": "MOVEL"}
            if not m.ocupa_piso:
                cam["linetype"] = TRACEJADO
            # na forma do móvel (retângulo, arredondado, redondo, L)
            contorno = list(geometria.poligono_movel(m).exterior.coords)[:-1]
            self.msp.add_lwpolyline(contorno, close=True, dxfattribs=cam)
            for ini, fim in self.detalhes_movel(m):
                self.msp.add_line(
                    geometria.girar_movel(m, *ini), geometria.girar_movel(m, *fim), dxfattribs=cam
                )
            linhas = [m.nome or m.tipo, f"{m.largura.valor} × {m.profundidade.valor}"]
            if m.polegadas:
                linhas[1] = f'{m.polegadas}" · {linhas[1]}'
            if m.elevacao and m.elevacao.valor:
                linhas.append(f"elev. {m.elevacao.valor}")
            passo = self.mm(Texto.MOVEL * 1.6)
            y0 = m.centro[1] + passo * (len(linhas) - 1) / 2
            for i, linha in enumerate(linhas):
                altura = Texto.MOVEL if i == 0 else Texto.MOVEL * 0.85
                self.texto(linha, (m.centro[0], y0 - i * passo), altura, "MOVEL")

    def detalhes_movel(self, m: Movel) -> list[tuple[Vetor, Vetor]]:
        """Linhas do símbolo no referencial do móvel (costas em -y, frente em +y).

        O símbolo vem do catálogo (``Simbolo``); tipo fora do catálogo usa o genérico
        (seta na frente).
        """
        w, d = m.largura.valor / 2, m.profundidade.valor / 2
        linhas: list[tuple[Vetor, Vetor]] = []
        item = catalogo.item_do_tipo(m.tipo)
        simbolo = item.simbolo if item else Simbolo.GENERICO

        def ret(x0: float, y0: float, x1: float, y1: float) -> None:
            linhas.extend(
                [
                    ((x0, y0), (x1, y0)),
                    ((x1, y0), (x1, y1)),
                    ((x1, y1), (x0, y1)),
                    ((x0, y1), (x0, y0)),
                ]
            )

        def seta() -> None:
            s = min(self.mm(1.5), w / 2, d / 2)
            linhas.extend([((-s, d - 2 * s), (0, d - s)), ((0, d - s), (s, d - 2 * s))])

        def circulo(cx: float, cy: float, r: float, lados: int = 16) -> None:
            passo = 2 * math.pi / lados
            pts = [
                (cx + r * math.cos(t * passo), cy + r * math.sin(t * passo)) for t in range(lados)
            ]
            linhas.extend(zip(pts, pts[1:] + pts[:1], strict=True))

        if simbolo is Simbolo.BELICHE:  # cama + a escada na frente, junto ao lado direito
            linhas.append(((-w, -d + 60), (w, -d + 60)))
            ret(-w + 80, -d + 120, w - 80, -d + 120 + min(320.0, d))
            for x in (w - 440, w - 60):
                linhas.append(((x, d), (x, d + 40)))
            for degrau in range(3):
                x = w - 440 + (degrau + 1) * 95
                linhas.append(((x, d), (x, d + 40)))
        elif simbolo is Simbolo.CADEIRA_GIRATORIA:  # assento redondo e encosto atrás
            circulo(0.0, 0.0, min(w, d) * 0.75)
            linhas.append(((-w * 0.6, -d * 0.85), (w * 0.6, -d * 0.85)))
        elif simbolo is Simbolo.MAQUINA:  # porta (ou tampa) redonda
            circulo(0.0, 0.0, min(w, d) * 0.6)
        elif simbolo is Simbolo.CAMA:
            linhas.append(((-w, -d + 60), (w, -d + 60)))  # cabeceira
            n = 2 if m.largura.valor >= 1200 else 1
            folga = 80.0
            larg = (2 * w - folga * (n + 1)) / n
            for i in range(n):
                x0 = -w + folga + i * (larg + folga)
                ret(x0, -d + 120, x0 + larg, -d + 120 + min(320.0, d))
        elif simbolo is Simbolo.PORTAS:
            if m.portas == "correr":  # duas folhas sobrepostas
                linhas.append(((-w, d - 30), (w * 0.1, d - 30)))
                linhas.append(((-w * 0.1, d - 60), (w, d - 60)))
            else:  # de abrir: linha das portas e divisão das folhas
                linhas.append(((-w, d - 40), (w, d - 40)))
                folha = m.largura_porta.valor if m.largura_porta else 0
                if folha > 0:
                    x = -w + folha
                    while x < w - 1:
                        linhas.append(((x, d - 40), (x, d)))
                        x += folha
            if m.tipo == "guarda_roupa":
                linhas.append(((-w + 60, 0), (w - 60, 0)))  # cabideiro
        elif simbolo is Simbolo.ASSENTO:
            encosto, braco = min(200.0, d / 3), min(150.0, w / 4)
            linhas.append(((-w, -d + encosto), (w, -d + encosto)))
            linhas.append(((-w + braco, -d + encosto), (-w + braco, d)))
            linhas.append(((w - braco, -d + encosto), (w - braco, d)))
            assento = 2 * (w - braco)
            lugares = max(1, round(assento / 650))
            for i in range(1, lugares):
                x = -w + braco + assento * i / lugares
                linhas.append(((x, -d + encosto), (x, d)))
        elif simbolo is Simbolo.CADEIRA:
            linhas.append(((-w, -d + min(80.0, d / 3)), (w, -d + min(80.0, d / 3))))
        elif simbolo is Simbolo.TELA:
            linhas.append(((-w, d - 15), (w, d - 15)))  # face da tela
        elif simbolo is Simbolo.MESA:
            k = min(40.0, w / 4, d / 4)
            ret(-w + k, -d + k, w - k, d - k)
        elif simbolo is Simbolo.PRATELEIRAS:
            linhas.append(((-w, d - 30), (w, d - 30)))
            linhas.append(((-w, -d), (w, d - 30)))
            seta()
        elif simbolo is Simbolo.PIA:
            # cuba (retângulo de cantos cortados) e a torneira atrás dela
            cw, cd = min(250.0, w * 0.4), min(200.0, d * 0.4)
            k = min(40.0, cw / 4)
            pts = [(-cw + k, -cd), (cw - k, -cd), (cw, -cd + k), (cw, cd - k),
                   (cw - k, cd), (-cw + k, cd), (-cw, cd - k), (-cw, -cd + k)]  # fmt: skip
            linhas.extend(zip(pts, pts[1:] + pts[:1], strict=True))
            linhas.append(((0.0, -cd), (0.0, -cd - min(80.0, d - cd - 20))))
        elif simbolo is Simbolo.FOGAO:
            # bocas: círculos (polígonos de 12 lados) em grade 2 × n
            n = 3 if w >= 700 else 2
            r = min(w / (2 * n) - 30, d / 4 - 20, 110.0)
            for i in range(n):
                for j in (-1, 1):
                    cx, cy = -w + (2 * i + 1) * w / n, j * d / 2.2
                    circ = [(cx + r * math.cos(t * math.pi / 6), cy + r * math.sin(t * math.pi / 6))
                            for t in range(12)]  # fmt: skip
                    linhas.extend(zip(circ, circ[1:] + circ[:1], strict=True))
        elif simbolo is Simbolo.VASO:
            # caixa atrás (fundo) e a bacia oval na frente
            caixa = min(180.0, d * 0.3)
            ret(-w, -d, w, -d + caixa)
            cy, ry, rx = (-d + caixa + d) / 2, (2 * d - caixa) / 2 - 10, w - 10
            oval = [(rx * math.cos(t * math.pi / 8), cy + ry * math.sin(t * math.pi / 8))
                    for t in range(16)]  # fmt: skip
            linhas.extend(zip(oval, oval[1:] + oval[:1], strict=True))
        elif simbolo is Simbolo.BOX:
            # vidro na frente (duas folhas que se cruzam no meio) e o caimento para o ralo
            linhas.append(((-w, d - 20), (w * 0.1, d - 20)))
            linhas.append(((-w * 0.1, d - 50), (w, d - 50)))
            linhas.extend([((-w, -d), (w, d - 50)), ((-w, d - 50), (w, -d))])
        elif simbolo is Simbolo.GELADEIRA:
            linhas.extend([((-w, -d), (w, d)), ((-w, d), (w, -d))])  # X: equipamento alto
            linhas.append(((-w, d - 40), (w, d - 40)))  # porta
        else:  # gavetas e genérico
            if simbolo is Simbolo.GAVETAS:
                linhas.append(((-w, d - 30), (w, d - 30)))
            seta()
        return linhas

    # -- instalações elétricas

    def instalacoes(self) -> None:
        """Pontos e trechos de elétrica (ELETRICA) e de água/esgoto (HIDRAULICA). Gás não."""
        for inst in self.recorte.instalacoes:
            camada = _camada_instalacao(inst.tipo)
            if camada is None:
                continue
            if isinstance(inst, PontoInstalacao):
                self.ponto_instalacao(inst, camada)
            else:
                pts = [(float(x), float(y)) for x, y in inst.caminho]
                self.msp.add_lwpolyline(pts, dxfattribs={"layer": camada})
                meio = LineString(pts).interpolate(0.5, normalized=True)
                rotulo = f"{SIGLAS[inst.tipo]} h{inst.altura.valor}"
                if inst.embutido:
                    rotulo += " (embutido)"
                self.texto(rotulo, (meio.x, meio.y + self.mm(1.5)), Texto.INSTALACAO, camada)

    def ponto_instalacao(self, inst: PontoInstalacao, camada: str) -> None:
        r = self.mm(1.6)
        cam = {"layer": camada}
        pos: Vetor = (float(inst.posicao[0]), float(inst.posicao[1]))
        parede = self.recorte.parede(inst.parede) if inst.parede else None
        rot = 0.0
        dentro: Vetor | None = None
        if parede is not None:
            _, n = _direcao(parede)
            if inst.comodo is not None:
                lado = 1 if parede.lado_a == inst.comodo else -1
            else:
                lado = self.lado_do_comodo(parede)
            pos = _som(pos, n, lado * (parede.espessura.valor / 2 + r * 1.3))
            dentro = (n[0] * lado, n[1] * lado)
            rot = _angulo(dentro) - 90
        tipo = inst.tipo
        if tipo is TipoInstalacao.PONTO_LUZ:
            self.msp.add_circle(pos, r, dxfattribs=cam)
            k = r * math.sqrt(0.5)
            self.msp.add_line(_som(pos, (-k, -k)), _som(pos, (k, k)), dxfattribs=cam)
            self.msp.add_line(_som(pos, (-k, k)), _som(pos, (k, -k)), dxfattribs=cam)
        elif tipo is TipoInstalacao.TOMADA:
            ang = math.radians(rot)
            pts = [
                _som(pos, (math.cos(ang + a) * r, math.sin(ang + a) * r))
                for a in (math.pi / 2, math.pi / 2 + 2.094, math.pi / 2 + 4.189)
            ]
            self.msp.add_lwpolyline(pts, close=True, dxfattribs=cam)
        elif tipo is TipoInstalacao.INTERRUPTOR:
            self.msp.add_circle(pos, r, dxfattribs=cam)
            self.texto("S", pos, Texto.INSTALACAO, camada)
        elif tipo is TipoInstalacao.RALO:
            x, y = pos
            self.msp.add_lwpolyline(
                [(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)],
                close=True,
                dxfattribs=cam,
            )
            self.msp.add_circle(pos, r * 0.6, dxfattribs=cam)
        elif tipo is TipoInstalacao.ESGOTO:
            self.msp.add_circle(pos, r, dxfattribs=cam)
            self.msp.add_circle(pos, r * 0.5, dxfattribs=cam)
        else:  # água fria / quente
            self.msp.add_circle(pos, r, dxfattribs=cam)
            if tipo is TipoInstalacao.AGUA_QUENTE:
                self.msp.add_line(_som(pos, (-r, 0)), _som(pos, (r, 0)), dxfattribs=cam)
        sigla = "" if tipo is TipoInstalacao.INTERRUPTOR else SIGLAS[tipo]
        legenda = f"{sigla} h{inst.altura.valor}".strip()
        if dentro is None:  # no piso ou no teto: legenda embaixo do símbolo
            ponto, alinhamento = _som(pos, (0, -r - self.mm(0.6))), TextEntityAlignment.TOP_CENTER
        else:  # na parede: legenda para dentro do cômodo, sem encostar na parede
            ponto, alinhamento = _som(pos, dentro, r + self.mm(0.8)), _alinhamento_para(dentro)
        self.texto(legenda, ponto, Texto.INSTALACAO, camada, alinhamento=alinhamento)

    # -- rótulos dos cômodos

    def rotulos(self) -> None:
        obstaculos = (
            [geometria.poligono_movel(m).buffer(50) for m in self.moveis]
            + self.giros
            + [
                Point(i.posicao).buffer(self.mm(5))
                for i in self.recorte.instalacoes
                if isinstance(i, PontoInstalacao) and _camada_instalacao(i.tipo) is not None
            ]
        )
        livres = unary_union(obstaculos)
        for c in self.comodos:
            util = geometria.poligono_util(self.pavimento, c)
            if util is None or util.is_empty:
                continue
            area = geometria.area_util_m2(self.pavimento, c)
            pe = (c.pe_direito or self.pavimento.pe_direito).valor
            # afasta das paredes para o texto não encostar nelas
            miolo = util.buffer(-self.mm(4)) if not util.buffer(-self.mm(4)).is_empty else util
            vazio: BaseGeometry = miolo.difference(livres) if obstaculos else miolo
            info = f"{area:.2f} m²".replace(".", ",") + f" · pé-direito {pe}"
            # caixa do texto (mm de modelo), para achar um lugar onde ele caiba inteiro
            larg = max(len(c.nome) * Texto.TITULO_COMODO, len(info) * Texto.INFO_COMODO) * self.mm(
                LARGURA_LETRA
            )
            alt = self.mm(Texto.TITULO_COMODO * 1.4 + Texto.INFO_COMODO * 1.4)
            cabe = _onde_cabe(vazio, larg, alt)
            alvo = cabe or _maior_poligono(vazio) or _maior_poligono(util)
            if alvo is None:
                continue
            p = polylabel(alvo, tolerance=10)
            h = self.mm(Texto.TITULO_COMODO)
            self.texto(c.nome, (p.x, p.y + h * 0.7), Texto.TITULO_COMODO, "TEXTO")
            self.texto(info, (p.x, p.y - h * 0.7), Texto.INFO_COMODO, "TEXTO")

    # -- cotas

    def cota(self, p1: Vetor, p2: Vetor, normal: Vetor, distancia: float) -> None:
        """Cota linear de ``p1`` a ``p2``, a ``distancia`` na direção ``normal``.

        Os pontos são ordenados para o texto ler da esquerda para a direita ou de
        baixo para cima (nunca de cabeça para baixo).
        """
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        if dx < -1e-6 or (abs(dx) <= 1e-6 and dy < 0):
            p1, p2 = p2, p1
        base = _som(p1, normal, distancia)
        dim = self.msp.add_linear_dim(
            base=base,
            p1=p1,
            p2=p2,
            angle=_angulo((p2[0] - p1[0], p2[1] - p1[1])),
            dimstyle=ESTILO_COTA,
            dxfattribs={"layer": "COTA"},
        )
        dim.render()

    def cotas_comodo(self, c: Comodo) -> None:
        """Cota cada face interna do cômodo; com aberturas, cota em cadeia antes do total."""
        util = _maior_poligono(geometria.poligono_util(self.pavimento, c))
        if util is None:
            return
        pts = [(float(x), float(y)) for x, y in orient(util, sign=1.0).exterior.coords]
        for p, q in itertools.pairwise(pts):
            dx, dy = q[0] - p[0], q[1] - p[1]
            tam = math.hypot(dx, dy)
            if tam < 1:
                continue
            u = (dx / tam, dy / tam)
            fora = (u[1], -u[0])  # anel anti-horário: exterior à direita
            paredes = geometria.paredes_da_face(self.pavimento, c, p, q)
            esp = max((pa.espessura.valor for pa in paredes), default=0)
            cortes = sorted({0.0, tam, *self.cortes_aberturas(paredes, p, u, tam)})
            fileira = esp + self.mm(9)
            if len(cortes) > 2:
                for t0, t1 in itertools.pairwise(cortes):
                    if t1 - t0 >= 1:
                        self.cota(_som(p, u, t0), _som(p, u, t1), fora, fileira)
                fileira += self.mm(7)
            self.cota(p, q, fora, fileira)

    def cortes_aberturas(
        self, paredes: list[Parede], p: Vetor, u: Vetor, tam: float
    ) -> list[float]:
        ids = {pa.id for pa in paredes}
        cortes: list[float] = []
        for ab in self.recorte.aberturas:
            parede = self.recorte.parede(ab.parede)
            if parede is None or parede.id not in ids:
                continue
            pu, _ = _direcao(parede)
            for d in (ab.distancia_inicio.valor, ab.distancia_inicio.valor + ab.largura.valor):
                x, y = _som(parede.inicio, pu, d)
                t = (x - p[0]) * u[0] + (y - p[1]) * u[1]
                if 0 < t < tam:
                    cortes.append(round(t, 3))
        return cortes

    def cotas_gerais(self) -> None:
        """Pavimento: cotas de eixo em cadeia e total externo, embaixo e à esquerda.

        Eixos verticais (x) são cotados embaixo; horizontais (y), à esquerda.
        """
        xmin, ymin, xmax, ymax = self.corpos.bounds
        xs = sorted({float(p.inicio[0]) for p in self.recorte.paredes if p.inicio[0] == p.fim[0]})
        ys = sorted({float(p.inicio[1]) for p in self.recorte.paredes if p.inicio[1] == p.fim[1]})
        fileira, total = self.mm(11), self.mm(18)
        for a, b in itertools.pairwise(xs):
            self.cota((a, ymin), (b, ymin), (0, -1), fileira)
        for a, b in itertools.pairwise(ys):
            self.cota((xmin, a), (xmin, b), (-1, 0), fileira)
        self.cota((xmin, ymin), (xmax, ymin), (0, -1), total)
        self.cota((xmin, ymin), (xmin, ymax), (-1, 0), total)

    # -- checagens de uso

    def restricoes(self) -> list[str]:
        """Desenha na camada RESTRICAO as áreas com problema e devolve as linhas do painel."""
        problemas = [
            p
            for p in checar(
                self.carregado.projeto,
                self.carregado.dados_comodos,
                self.carregado.regras,
                comodo=self.comodos[0].id if self.por_comodo else None,
            )
            if p.comodo in self.ids_comodos and p.pavimento == self.pavimento.id
        ]
        cam = {"layer": "RESTRICAO"}
        r = self.mm(2.2)
        linhas = []
        usados: list[Vetor] = []
        for i, p in enumerate(problemas, 1):
            if p.regiao:
                self.msp.add_lwpolyline(p.regiao, close=True, dxfattribs=cam)
            if p.posicao:
                pos: Vetor = (float(p.posicao[0]), float(p.posicao[1]))
                # marcas no mesmo lugar vão para o lado, sem se sobrepor
                while any(math.dist(pos, u) < 2 * r for u in usados):
                    pos = (pos[0] + 2.2 * r, pos[1])
                usados.append(pos)
                self.msp.add_circle(pos, r, dxfattribs=cam)
                self.texto(str(i), pos, Texto.INSTALACAO * 1.2, "RESTRICAO")
            linhas.append(f"{i}. [{p.severidade}] {p.mensagem}")
        return linhas

    # -- referências para cortes e elevações

    def ids_das_paredes(self) -> None:
        """Id de cada parede junto à face, do lado do cômodo (elevação e ``--parede``)."""
        for parede in self.recorte.paredes:
            if geometria.comprimento(parede) == 0:
                continue
            u, n = geometria.direcao(parede)
            lado = self.lado_do_comodo(parede)
            meio = (
                (parede.inicio[0] + parede.fim[0]) / 2,
                (parede.inicio[1] + parede.fim[1]) / 2,
            )
            ponto = _som(meio, n, lado * (parede.espessura.valor / 2 + self.mm(2)))
            # um pouco para o lado, para não cair em cima da etiqueta da abertura
            ponto = _som(ponto, u, self.mm(8))
            self.texto(parede.id, ponto, Texto.ABERTURA, "TEXTO", _angulo_legivel(u))

    def linhas_de_corte(self) -> None:
        """Linhas AA/BB tracejadas com a letra e a seta do lado para onde o corte olha."""
        from interiores_cad.vistas import vistas_do_comodo

        r = self.mm(2.4)
        for v in vistas_do_comodo(self.pavimento, self.comodos[0]):
            if v.elevacao:
                continue
            letra = v.titulo.split()[-1][0]
            u = v.u
            # letras fora das paredes cortadas, para não cobrir parede nem etiquetas
            a = _som(v.p0, u, -self.mm(5))
            b = _som(v.p1, u, self.mm(5))
            self.msp.add_line(a, b, dxfattribs={"layer": "TEXTO", "linetype": TRACEJADO})
            for ponta in (a, b):
                self.msp.add_circle(ponta, r, dxfattribs={"layer": "TEXTO"})
                self.texto(letra, ponta, Texto.ABERTURA * 1.2, "TEXTO")
                seta = _som(ponta, v.olhar, r)
                k = r * 0.6
                lado = (-v.olhar[1], v.olhar[0])
                self.msp.add_lwpolyline(
                    [_som(seta, lado, k), _som(seta, v.olhar, r * 0.9), _som(seta, lado, -k)],
                    close=True,
                    dxfattribs={"layer": "TEXTO"},
                )

    # -- montagem

    def desenhar(self, titulo: str, escopo: str, data: str) -> Desenho:
        self.paredes()
        self.aberturas()
        self.moveis_()
        self.instalacoes()
        self.rotulos()
        if self.por_comodo:
            self.cotas_comodo(self.comodos[0])
            self.linhas_de_corte()
        else:
            self.cotas_gerais()
        self.ids_das_paredes()
        checagens = self.restricoes()
        estimadas = (
            self.carregado.estimadas(self.comodos[0].id)
            if self.por_comodo
            else self.carregado.estimadas_pavimento(self.pavimento.id)
        )
        proj = self.carregado.projeto
        desenhar_folha(
            self.msp,
            self.folha,
            DadosCarimbo(
                projeto=proj.projeto,
                apelido=proj.imovel.endereco_apelido,
                desenho=titulo,
                pavimento=self.pavimento.nome or self.pavimento.id,
                escopo=escopo,
                data=data,
                hash_curto=self.carregado.hash_curto,
                gerador=VERSAO_GERADOR,
                estimadas=estimadas,
                legenda=LEGENDA,
                checagens=checagens,
            ),
        )
        return Desenho(self.doc, self.folha, titulo, estimadas)


def _alinhamento_para(v: Vetor) -> TextEntityAlignment:
    """Alinhamento de texto que faz ele crescer na direção ``v``."""
    if abs(v[0]) >= abs(v[1]):
        return TextEntityAlignment.MIDDLE_LEFT if v[0] > 0 else TextEntityAlignment.MIDDLE_RIGHT
    return TextEntityAlignment.BOTTOM_CENTER if v[1] > 0 else TextEntityAlignment.TOP_CENTER


def _onde_cabe(area: BaseGeometry, largura: float, altura: float) -> Polygon | None:
    """Maior região de ``area`` onde o centro de uma caixa largura × altura pode ficar.

    Erosão por retângulo: encolhe meia altura em todas as direções (quadrado) e
    o resto da meia largura só na horizontal (interseção de cópias deslocadas).
    """
    meia_alt = altura / 2
    folga_h = max(0.0, largura / 2 - meia_alt)
    base = area.buffer(-meia_alt, join_style="mitre")
    if base.is_empty:
        return None
    centros = base.intersection(translate(base, folga_h, 0)).intersection(
        translate(base, -folga_h, 0)
    )
    return _maior_poligono(centros)


def _maior_poligono(geom: BaseGeometry | None) -> Polygon | None:
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return geom
    poligonos = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    return max(poligonos, key=lambda g: g.area, default=None)


def desenhar_planta(
    carregado: ProjetoCarregado,
    pavimento: str,
    comodo: str | None = None,
    data: date | None = None,
) -> Desenho:
    """Planta do cômodo (se informado) ou do pavimento inteiro.

    Levanta ``KeyError`` se o pavimento/cômodo não existir e ``ValueError`` se o
    cômodo não fechar (rode ``interiores validar`` para ver o motivo).
    """
    pav = next((p for p in carregado.projeto.pavimentos if p.id == pavimento), None)
    if pav is None:
        raise KeyError(f"pavimento '{pavimento}' não existe no projeto")
    data_txt = (data or date.today()).isoformat()
    if comodo is not None:
        c = pav.comodo(comodo)
        if c is None:
            raise KeyError(f"cômodo '{comodo}' não está no pavimento '{pavimento}'")
        if geometria.poligono_eixo(pav, c) is None:
            raise ValueError(f"cômodo '{comodo}' não fecha; rode `interiores validar`")
        recorte = geometria.recorte_do_comodo(pav, comodo)
        planta = _Planta(carregado, pav, [c], recorte, por_comodo=True)
        return planta.desenhar(f"Planta baixa — {c.nome}", f"cômodo {c.id}", data_txt)
    fechados = [c for c in pav.comodos if geometria.poligono_eixo(pav, c) is not None]
    planta = _Planta(carregado, pav, fechados, pav, por_comodo=False)
    return planta.desenhar(f"Planta baixa — {pav.nome or pav.id}", f"pavimento {pav.id}", data_txt)
