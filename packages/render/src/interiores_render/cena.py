"""Monta a ``cena.json`` do cômodo: geometria pronta, materiais, câmeras e luzes.

Roda no Python do projeto (importa só ``interiores_core`` e stdlib). O script do
Blender (``bpy_cena.py``) só lê este JSON e constrói a cena (CLAUDE.md §2.4).

Unidade: mm (o script converte para metros). Coordenadas do pavimento, z para
cima a partir do piso do cômodo.

Elementos:

- ``prismas``: polígono na planta extrudado de ``z0`` a ``z1`` (paredes com os
  vãos recortados, piso, teto, rodapé, vidros);
- ``caixas``: paralelepípedo com centro, tamanho e rotação em z (peças dos móveis
  e folhas de porta);
- ``oculto_em``: câmeras em que o elemento não aparece (o teto, na vista de cima).
"""

from __future__ import annotations

import math
from typing import Any

from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from interiores_core import catalogo, geometria, planejado
from interiores_core.carregar import ProjetoCarregado
from interiores_core.catalogo import Simbolo
from interiores_core.modelo import Comodo, Janela, Movel, Pavimento, Porta, Variacao

VERSAO_CENA = 1
AVISO_OBRA = "PRELIMINAR — NÃO USAR PARA OBRA"

CORES_PADRAO = {
    "parede": "#EEEAE3",
    "piso": "#A67C52",
    "teto": "#FAFAFA",
    "rodape": "#FFFFFF",
    "vidro": "#CFE6F2",
    "porta": "#F1EEE8",
    "colchao": "#F4F4F2",
    "travesseiro": "#FFFFFF",
    "tela": "#151515",
}
CORES_MOVEIS = {
    "cama": "#8B6B4F",
    "guarda_roupa": "#F2F0EC",
    "armario": "#F2F0EC",
    "comoda": "#C9A27E",
    "criado_mudo": "#C9A27E",
    "estante": "#B08968",
    "sapateira": "#F2F0EC",
    "sofa": "#7D8B99",
    "poltrona": "#A1866F",
    "cadeira": "#4A4A4A",
    "banco": "#9C8C7A",
    "mesa": "#9C7653",
    "escrivaninha": "#D8CFC4",
    "penteadeira": "#E8E2DA",
    "rack": "#6F5846",
    "tv": "#151515",
    "berco": "#FFFFFF",
}
COR_MOVEL_GENERICO = "#B5B0A8"
ALTURA_OLHO = 1600
FOLGA_CAMERA = 400
"""Distância mínima (mm) da câmera da perspectiva até paredes, móveis e giro de porta."""


def _coords(pol: Polygon) -> list[list[float]]:
    pts = list(orient(pol, sign=1.0).exterior.coords)[:-1]
    return [[round(x, 1), round(y, 1)] for x, y in pts]


def _poligonos(geom: BaseGeometry) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and g.area > 1]


class _Cena:
    def __init__(
        self, carregado: ProjetoCarregado, pav: Pavimento, comodo: Comodo, variacao: Variacao | None
    ) -> None:
        self.pav = pav
        self.comodo = comodo
        self.pe = (comodo.pe_direito or pav.pe_direito).valor
        util = geometria.poligono_util(pav, comodo)
        alvo = max(_poligonos(util), key=lambda g: g.area) if util is not None else None
        if alvo is None:
            raise ValueError(f"cômodo '{comodo.id}' não fecha; rode `interiores validar`")
        self.util: Polygon = alvo
        dados = carregado.dados_comodos.get(comodo.id)
        self.moveis: list[Movel] = list(dados.moveis) if dados else []
        self.cores = dict(CORES_PADRAO)
        self.cores_moveis: dict[str, str] = {}
        if variacao is not None:
            c = variacao.cores
            for chave in ("parede", "piso", "teto", "rodape"):
                valor = getattr(c, chave)
                if valor:
                    self.cores[chave] = valor
            self.cores_moveis = dict(c.moveis)
        self.prismas: list[dict[str, Any]] = []
        self.caixas: list[dict[str, Any]] = []
        self.materiais: dict[str, dict[str, Any]] = {}

    # -- materiais

    def material(self, nome: str, cor: str, **extra: Any) -> str:
        self.materiais.setdefault(nome, {"cor": cor, "rugosidade": 0.6, **extra})
        return nome

    def cor_movel(self, m: Movel) -> str:
        return (
            self.cores_moveis.get(m.id)
            or self.cores_moveis.get(m.tipo)
            or CORES_MOVEIS.get(m.tipo, COR_MOVEL_GENERICO)
        )

    # -- primitivas

    def prisma(
        self, nome: str, pol: Polygon, z0: float, z1: float, material: str, **extra: Any
    ) -> None:
        if pol.area < 1 or z1 - z0 < 0.5:
            return
        self.prismas.append(
            {
                "nome": nome,
                "contorno": _coords(pol),
                "z0": z0,
                "z1": z1,
                "material": material,
                **extra,
            }
        )

    def caixa(
        self,
        nome: str,
        centro: tuple[float, float, float],
        tamanho: tuple[float, float, float],
        rotacao: float,
        material: str,
    ) -> None:
        if min(tamanho) <= 0:
            return
        self.caixas.append(
            {
                "nome": nome,
                "centro": [round(v, 1) for v in centro],
                "tamanho": [round(v, 1) for v in tamanho],
                "rotacao": rotacao,
                "material": material,
            }
        )

    # -- arquitetura

    def piso_teto(self) -> None:
        self.prisma(
            "piso", self.util, -20, 0, self.material("piso", self.cores["piso"], rugosidade=0.45)
        )
        self.prisma(
            "teto",
            self.util,
            self.pe,
            self.pe + 20,
            self.material("teto", self.cores["teto"]),
            oculto_em=["superior"],
        )

    def paredes(self) -> None:
        mat = self.material("parede", self.cores["parede"], rugosidade=0.85)
        mat_vidro = self.material("vidro", CORES_PADRAO["vidro"], vidro=True)
        ocupado: BaseGeometry = Polygon()
        for pid in self.comodo.paredes:
            parede = self.pav.parede(pid)
            if parede is None or geometria.comprimento(parede) == 0:
                continue
            altura = float(parede.altura.valor) if parede.altura else float(self.pe)
            # cada parede perde o que as anteriores já ocupam: sem faces sobrepostas nas
            # quinas (no render elas brigam e saem pretas)
            inteiro = geometria.corpo(parede)
            corpo = inteiro.difference(ocupado)
            ocupado = ocupado.union(inteiro)
            u, n = geometria.direcao(parede)
            meia = parede.espessura.valor / 2 + 1
            vaos: list[tuple[Polygon, Porta | Janela]] = []
            for ab in self.pav.aberturas:
                if ab.parede != pid:
                    continue
                d0, larg = ab.distancia_inicio.valor, ab.largura.valor
                a = (parede.inicio[0] + u[0] * d0, parede.inicio[1] + u[1] * d0)
                b = (a[0] + u[0] * larg, a[1] + u[1] * larg)
                vao = Polygon(
                    [
                        (a[0] + n[0] * meia, a[1] + n[1] * meia),
                        (b[0] + n[0] * meia, b[1] + n[1] * meia),
                        (b[0] - n[0] * meia, b[1] - n[1] * meia),
                        (a[0] - n[0] * meia, a[1] - n[1] * meia),
                    ]
                )
                envelope = vao.intersection(inteiro).envelope
                if isinstance(envelope, Polygon):
                    vaos.append((envelope, ab))
            cheio = corpo.difference(unary_union([v for v, _ in vaos])) if vaos else corpo
            for i, pol in enumerate(_poligonos(cheio)):
                self.prisma(f"parede-{pid}-{i}", pol, 0, altura, mat)
            for vao, ab in vaos:
                vao_aqui = vao.intersection(corpo)
                if isinstance(ab, Janela):
                    pe, topo = float(ab.peitoril.valor), float(ab.peitoril.valor + ab.altura.valor)
                    for pol in _poligonos(vao_aqui):
                        self.prisma(f"peitoril-{ab.id}", pol, 0, pe, mat)
                    vidro = vao.intersection(geometria.eixo(parede).buffer(8, cap_style="flat"))
                    for pol in _poligonos(vidro):
                        self.prisma(f"vidro-{ab.id}", pol, pe, topo, mat_vidro)
                else:
                    topo = float(ab.altura.valor)
                    self.porta(ab, parede)
                for pol in _poligonos(vao_aqui):
                    self.prisma(f"verga-{ab.id}", pol, topo, altura, mat)

    def porta(self, porta: Porta, parede: Any) -> None:
        """Folha aberta a 90° para dentro do cômodo (portas que abrem para fora não aparecem)."""
        if porta.folha != "giro" or porta.abre_para != self.comodo.id:
            return
        giro = geometria.giro_porta(self.pav, porta)
        if giro is None:
            return
        _, n = geometria.direcao(parede)
        s = 1 if porta.abre_para == parede.lado_a else -1
        centro, *arco = list(giro.exterior.coords)[:-1]
        # ponta da folha aberta: o ponto do arco na direção da normal (para dentro)
        ponta = max(
            arco, key=lambda p: (p[0] - centro[0]) * n[0] * s + (p[1] - centro[1]) * n[1] * s
        )
        mx, my = (centro[0] + ponta[0]) / 2, (centro[1] + ponta[1]) / 2
        ang = math.degrees(math.atan2(ponta[1] - centro[1], ponta[0] - centro[0]))
        larg, alt = porta.largura.valor, porta.altura.valor
        mat = self.material("porta", CORES_PADRAO["porta"], rugosidade=0.5)
        self.caixa(f"porta-{porta.id}", (mx, my, alt / 2), (larg, 35, alt), ang, mat)

    def rodape(self) -> None:
        if not self.pav.rodape:
            return
        h = float(self.pav.rodape.valor)
        mat = self.material("rodape", self.cores["rodape"])
        faixa = self.util.difference(self.util.buffer(-12, join_style="mitre"))
        # sem rodapé atravessando as portas
        portas = []
        for ab in self.pav.aberturas:
            parede = self.pav.parede(ab.parede)
            if isinstance(ab, Porta) and parede is not None and ab.parede in self.comodo.paredes:
                u, _ = geometria.direcao(parede)
                d0 = ab.distancia_inicio.valor
                a = (parede.inicio[0] + u[0] * d0, parede.inicio[1] + u[1] * d0)
                b = (a[0] + u[0] * ab.largura.valor, a[1] + u[1] * ab.largura.valor)
                portas.append(LineString([a, b]).buffer(parede.espessura.valor, cap_style="flat"))
        if portas:
            faixa = faixa.difference(unary_union(portas))
        for i, pol in enumerate(_poligonos(faixa)):
            self.prisma(f"rodape-{i}", pol, 0, h, mat)

    # -- móveis

    def moveis_(self) -> None:
        for m in self.moveis:
            mat = self.material(f"movel-{m.id}", self.cor_movel(m), rugosidade=0.55)
            for nome, (x0, y0, z0, x1, y1, z1), material in self.pecas_movel(m, mat):
                cx, cy = geometria.girar_movel(m, (x0 + x1) / 2, (y0 + y1) / 2)
                self.caixa(
                    f"{m.id}-{nome}",
                    (cx, cy, (z0 + z1) / 2),
                    (x1 - x0, y1 - y0, z1 - z0),
                    float(m.rotacao),
                    material,
                )

    def pecas_movel(
        self, m: Movel, mat: str
    ) -> list[tuple[str, tuple[float, float, float, float, float, float], str]]:
        """Peças no referencial do móvel (costas em -y, frente em +y), com z a partir do piso."""
        w, d = m.largura.valor / 2, m.profundidade.valor / 2
        base = float(m.elevacao.valor) if m.elevacao else 0.0
        h = float(m.altura.valor)
        topo = base + h
        item = catalogo.item_do_tipo(m.tipo)
        simbolo = item.simbolo if item else Simbolo.GENERICO
        pecas: list[tuple[str, tuple[float, float, float, float, float, float], str]] = []

        def p(
            nome: str,
            x0: float,
            y0: float,
            z0: float,
            x1: float,
            y1: float,
            z1: float,
            material: str = mat,
        ) -> None:
            pecas.append((nome, (x0, y0, z0, x1, y1, z1), material))

        if simbolo is Simbolo.CAMA:
            colchao = self.material("colchao", CORES_PADRAO["colchao"], rugosidade=0.9)
            trav = self.material("travesseiro", CORES_PADRAO["travesseiro"], rugosidade=0.95)
            p("base", -w, -d + 60, base, w, d, topo - 250)
            p("colchao", -w + 15, -d + 75, topo - 250, w - 15, d - 15, topo, colchao)
            p("cabeceira", -w, -d, base, w, -d + 60, max(topo + 450, 1000))
            n = 2 if m.largura.valor >= 1200 else 1
            larg = (2 * w - 80 * (n + 1)) / n
            for i in range(n):
                x0 = -w + 80 + i * (larg + 80)
                p(
                    f"travesseiro{i}",
                    x0,
                    -d + 110,
                    topo,
                    x0 + larg,
                    -d + 110 + 380,
                    topo + 120,
                    trav,
                )
        elif simbolo is Simbolo.ASSENTO:
            enc, braco = min(200.0, d / 3), min(150.0, w / 4)
            assento = min(450.0, h * 0.55)
            p("assento", -w + braco, -d + enc, base, w - braco, d, base + assento)
            p("encosto", -w, -d, base, w, -d + enc, topo)
            p("braco-e", -w, -d + enc, base, -w + braco, d, base + min(650.0, h * 0.75))
            p("braco-d", w - braco, -d + enc, base, w, d, base + min(650.0, h * 0.75))
        elif simbolo is Simbolo.CADEIRA:
            p("assento", -w, -d, base, w, d, base + 450)
            p("encosto", -w, -d, base + 450, w, -d + 60, topo)
        elif simbolo is Simbolo.MESA:
            p("tampo", -w, -d, topo - 30, w, d, topo)
            for i, (x, y) in enumerate(((-w, -d), (w - 50, -d), (-w, d - 50), (w - 50, d - 50))):
                p(f"pe{i}", x, y, base, x + 50, y + 50, topo - 30)
        elif simbolo is Simbolo.TELA:
            tela = self.material("tela", CORES_PADRAO["tela"], rugosidade=0.2)
            p("tela", -w, -d, base, w, d, topo, tela)
        elif m.construcao is not None:
            p("caixa", -w, -d, base, w, d - 20, topo)
            try:
                calc = planejado.calcular(m)
            except planejado.ConstrucaoInvalidaError:
                calc = None
            portas = [r for r in calc.layout if r.tipo == "porta"] if calc else []
            for i, r in enumerate(portas):  # folhas um pouco afastadas: mostram as divisões
                x0 = -w + r.x + 2
                p(
                    f"porta{i}",
                    x0,
                    d - 20,
                    base + r.y + 2,
                    x0 + r.largura - 4,
                    d,
                    base + r.y + r.altura - 2,
                )
            if not portas:
                p("frente", -w, d - 20, base, w, d, topo)
        else:
            p("corpo", -w, -d, base, w, d, topo)
        return pecas

    # -- câmeras e luzes

    def cameras(self) -> list[dict[str, Any]]:
        """Perspectiva de um canto livre, na altura dos olhos; e vista de cima sem o teto.

        A perspectiva fica no ponto livre mais afastado do centro (grade de 100 mm),
        longe de paredes, móveis e giro de porta; a folga é relaxada de 400 até 150 mm
        se o cômodo for apertado.
        """
        c = self.util.centroid
        pos = (c.x - 1.0, c.y - 1.0)
        for folga in (FOLGA_CAMERA, 250, 150):  # relaxa a folga em cômodo apertado
            bloqueios = unary_union(
                [geometria.poligono_movel(m).buffer(folga) for m in self.moveis if m.ocupa_piso]
                + [
                    g.buffer(folga)
                    for ab in self.pav.aberturas
                    if isinstance(ab, Porta)
                    and (g := geometria.giro_porta(self.pav, ab)) is not None
                ]
            )
            livre = self.util.buffer(-folga).difference(bloqueios)
            x0, y0, x1, y1 = self.util.bounds
            grade = [
                (x0 + i * 100.0, y0 + j * 100.0)
                for i in range(int((x1 - x0) / 100) + 1)
                for j in range(int((y1 - y0) / 100) + 1)
            ]
            livres = [g for g in grade if livre.contains(Point(g))]
            longe = [g for g in livres if math.dist(g, (c.x, c.y)) >= 1500]
            if longe:
                pos = max(longe, key=lambda g: math.dist(g, (c.x, c.y)))
                break
        x0, y0, x1, y1 = self.util.bounds
        maior = max(x1 - x0, y1 - y0)
        return [
            {
                "nome": "perspectiva",
                "tipo": "perspectiva",
                "posicao": [pos[0], pos[1], ALTURA_OLHO],
                "alvo": [c.x, c.y, 1000],
                "lente": 14,
            },
            {
                "nome": "superior",
                "tipo": "ortografica",
                "posicao": [c.x - maior * 0.6, c.y - maior * 0.75, maior * 2.2],
                "alvo": [c.x, c.y, 0],
                "escala": maior * 1.45,
            },
        ]

    def luzes(self) -> list[dict[str, Any]]:
        c = self.util.centroid
        x0, y0, x1, y1 = self.util.bounds
        area_m2 = self.util.area / 1e6
        return [
            {
                "tipo": "area",
                "posicao": [c.x, c.y, self.pe - 30],
                "tamanho": [(x1 - x0) * 0.6, (y1 - y0) * 0.6],
                "energia": 30 * area_m2,
            },
            {"tipo": "sol", "direcao": [0.45, 0.35, -0.82], "energia": 2.0},
        ]


def montar_cena(
    carregado: ProjetoCarregado,
    comodo: str,
    variacao: str | None = None,
    largura: int = 1600,
    altura: int = 1000,
    amostras: int = 96,
) -> dict[str, Any]:
    """Cena do cômodo em JSON, pronta para o ``bpy_cena.py``.

    ``variacao``: nome de um arquivo em ``variacoes/<comodo>/``; ``None`` = cores padrão.
    """
    pav = carregado.projeto.pavimento_do_comodo(comodo)
    if pav is None:
        raise KeyError(f"cômodo '{comodo}' não existe no projeto")
    c = pav.comodo(comodo)
    assert c is not None
    var = None
    if variacao is not None:
        var = carregado.variacoes.get(comodo, {}).get(variacao)
        if var is None:
            disponiveis = ", ".join(sorted(carregado.variacoes.get(comodo, {}))) or "nenhuma"
            raise KeyError(f"variação '{variacao}' não existe para '{comodo}' ({disponiveis})")
    cena = _Cena(carregado, pav, c, var)
    cena.piso_teto()
    cena.paredes()
    cena.rodape()
    cena.moveis_()
    estimadas = carregado.estimadas(comodo)
    return {
        "versao": VERSAO_CENA,
        "comodo": comodo,
        "variacao": variacao or "base",
        "prismas": cena.prismas,
        "caixas": cena.caixas,
        "materiais": cena.materiais,
        "cameras": cena.cameras(),
        "luzes": cena.luzes(),
        "aviso": f"{AVISO_OBRA} · {len(estimadas)} medida(s) estimada(s)" if estimadas else None,
        "saida": {"largura": largura, "altura": altura, "amostras": amostras},
    }
