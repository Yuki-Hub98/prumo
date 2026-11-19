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
from dataclasses import dataclass
from typing import Any

from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from interiores_core import catalogo, geometria, planejado
from interiores_core.carregar import ProjetoCarregado
from interiores_core.catalogo import Simbolo
from interiores_core.modelo import (
    Comodo,
    Janela,
    Movel,
    Pavimento,
    PontoInstalacao,
    Porta,
    Variacao,
)

VERSAO_CENA = 5
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
    "tela": "#0E1116",
    "moldura": "#111111",
    "edredom": "#C8B9A6",
    "sombra": "#2B2622",
    "metal": "#8A8D91",
    "caixilho": "#ECECEA",
    "pedra": "#E3DDD2",
    "luminaria": "#FFF6E8",
    "piso_frio": "#D6D1C8",
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

TEXTURA_MOVEL = {
    "cama": "madeira",
    "comoda": "madeira",
    "criado_mudo": "madeira",
    "estante": "madeira",
    "mesa": "madeira",
    "rack": "madeira",
    "banco": "madeira",
    "sofa": "tecido",
    "poltrona": "tecido",
}
"""Textura procedural por tipo de móvel (o que não está aqui é MDF liso, ex.: guarda-roupa
branco). A cor continua vindo da variação/catálogo."""
PISO_FRIO = {"banheiro", "lavabo", "cozinha", "area_servico", "varanda", "garagem"}


def _maior_poligono(g: BaseGeometry) -> Polygon | None:
    if isinstance(g, Polygon):
        return g
    partes = [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
    return max(partes, key=lambda p: p.area) if partes else None


def textura_piso(comodo: Comodo) -> str:
    """Pelo acabamento escrito no cômodo (``piso``) ou, sem ele, pelo tipo do cômodo."""
    texto = (comodo.piso or "").lower()
    if any(p in texto for p in ("porcel", "cerâm", "ceram", "pedra", "granito", "mármore")):
        return "porcelanato"
    if any(p in texto for p in ("madeira", "laminado", "taco", "vinílico", "vinilico", "tacos")):
        return "madeira"
    return "porcelanato" if comodo.tipo in PISO_FRIO else "madeira"


LUZ_W_M2 = 3.0
"""Luz de área no teto, por m² do cômodo (com ``view_transform`` Standard)."""
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
        self.cores_paredes: dict[str, str] = {}
        self.textura_piso = textura_piso(comodo)
        if self.textura_piso == "porcelanato":  # padrão do piso frio (madeira seria marrom)
            self.cores["piso"] = CORES_PADRAO["piso_frio"]
        if variacao is not None:
            c = variacao.cores
            for chave in ("parede", "piso", "teto", "rodape"):
                valor = getattr(c, chave)
                if valor:
                    self.cores[chave] = valor
            self.cores_moveis = dict(c.moveis)
            self.cores_paredes = dict(c.paredes)
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
        chanfro: float = 0.0,
        oculto_em: list[str] | None = None,
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
                **({"chanfro": chanfro} if chanfro else {}),
                **({"oculto_em": oculto_em} if oculto_em else {}),
            }
        )

    # -- arquitetura

    def piso_teto(self) -> None:
        self.prisma(
            "piso",
            self.util,
            -20,
            0,
            self.material("piso", self.cores["piso"], rugosidade=0.45, textura=self.textura_piso),
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
        geral = self.material("parede", self.cores["parede"], rugosidade=0.85, textura="pintura")
        mat_vidro = self.material("vidro", CORES_PADRAO["vidro"], vidro=True)
        ocupado: BaseGeometry = Polygon()
        for pid in self.comodo.paredes:
            parede = self.pav.parede(pid)
            if parede is None or geometria.comprimento(parede) == 0:
                continue
            altura = float(parede.altura.valor) if parede.altura else float(self.pe)
            cor = self.cores_paredes.get(pid)  # parede de destaque
            mat = (
                self.material(f"parede-{pid}", cor, rugosidade=0.85, textura="pintura")
                if cor
                else geral
            )
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
                    self.caixilho(ab, parede, pe, topo)
                else:
                    topo = float(ab.altura.valor)
                    self.porta(ab, parede)
                    self.batente(ab, parede)
                for pol in _poligonos(vao_aqui):
                    self.prisma(f"verga-{ab.id}", pol, topo, altura, mat)

    def _no_vao(
        self, parede: Any, ao_longo: float, para_dentro: float, z: float,
        tamanho: tuple[float, float, float], nome: str, material: str, chanfro: float = 0.0,
    ) -> None:  # fmt: skip
        """Caixa no referencial da parede: ``ao_longo`` do início, ``para_dentro`` do eixo
        (positivo = lado deste cômodo), ``z`` = meio da altura; tamanho (ao longo, fundo, alto)."""
        u, n = geometria.direcao(parede)
        s = 1 if parede.lado_a == self.comodo.id else -1
        x = parede.inicio[0] + u[0] * ao_longo + n[0] * s * para_dentro
        y = parede.inicio[1] + u[1] * ao_longo + n[1] * s * para_dentro
        ang = math.degrees(math.atan2(u[1], u[0]))
        self.caixa(nome, (x, y, z), tamanho, ang, material, chanfro)

    def caixilho(self, janela: Janela, parede: Any, pe: float, topo: float) -> None:
        """Caixilho (marco + montante nas janelas largas) e peitoril de pedra por dentro."""
        mat = self.material("caixilho", CORES_PADRAO["caixilho"], rugosidade=0.35)
        pedra = self.material("pedra", CORES_PADRAO["pedra"], rugosidade=0.4)
        # 2 mm para dentro das faces do vão: encostado nelas, as faces ficam no mesmo plano
        # e saem pretas no render
        d0, larg = janela.distancia_inicio.valor + 2, janela.largura.valor - 4
        pe, topo = pe + 2, topo - 2
        meio, e, f = d0 + larg / 2, 50.0, 60.0
        alt = topo - pe
        self._no_vao(parede, meio, 0, pe + e / 2, (larg, f, e), f"caixilho-{janela.id}-b", mat)
        self._no_vao(parede, meio, 0, topo - e / 2, (larg, f, e), f"caixilho-{janela.id}-t", mat)
        # montantes entre as travessas: peças sobrepostas com faces no mesmo plano saem
        # pretas no render (o Blender não sabe qual desenhar)
        vao = alt - 2 * e
        for lado, x in (("e", d0 + e / 2), ("d", d0 + larg - e / 2)):
            self._no_vao(
                parede, x, 0, pe + alt / 2, (e, f, vao), f"caixilho-{janela.id}-{lado}", mat
            )
        if larg > 900:
            self._no_vao(
                parede, meio, 0, pe + alt / 2, (40, f - 10, vao), f"caixilho-{janela.id}-m", mat
            )
        fundo = parede.espessura.valor / 2 + 30
        self._no_vao(
            parede,
            meio,
            fundo / 2,
            pe - 10,
            (larg + 80, fundo, 20),
            f"soleira-{janela.id}",
            pedra,
            4,
        )

    def batente(self, porta: Porta, parede: Any) -> None:
        """Batente (dois montantes e a travessa) em volta do vão da porta."""
        mat = self.material("porta", CORES_PADRAO["porta"], rugosidade=0.5)
        d0, larg, alt = porta.distancia_inicio.valor, porta.largura.valor, float(porta.altura.valor)
        fundo, e = parede.espessura.valor + 20, 40.0
        # dentro do vão: invadir a parede/verga deixa faces no mesmo plano (saem pretas)
        for lado, x in (("e", d0 + e / 2), ("d", d0 + larg - e / 2)):
            self._no_vao(
                parede,
                x,
                0,
                (alt - e) / 2,
                (e, fundo, alt - e),
                f"batente-{porta.id}-{lado}",
                mat,
                4,
            )
        self._no_vao(
            parede,
            d0 + larg / 2,
            0,
            alt - e / 2,
            (larg, fundo, e),
            f"batente-{porta.id}-t",
            mat,
            4,
        )

    def luminarias(self) -> None:
        """Plafonier acesa em cada ponto de luz do teto deste cômodo."""
        mat = self.material("luminaria", CORES_PADRAO["luminaria"], emissao=4.0)
        for i in self.pav.instalacoes:
            no_teto = isinstance(i, PontoInstalacao) and i.tipo == "ponto_luz"
            if no_teto and self.util.contains(Point(i.posicao)):  # type: ignore[union-attr]
                x, y = i.posicao
                tamanho = (380.0, 380.0, 70.0)
                self.caixa(
                    f"luminaria-{i.id}", (x, y, self.pe - 35), tamanho, 0.0, mat, 30, ["superior"]
                )

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
        self.caixa(f"porta-{porta.id}", (mx, my, alt / 2), (larg, 35, alt), ang, mat, 3)
        # maçaneta perto da ponta da folha, dos dois lados
        metal = self.material("metal", CORES_PADRAO["metal"], rugosidade=0.3, metal=True)
        vx, vy = (ponta[0] - centro[0]) / larg, (ponta[1] - centro[1]) / larg
        hx, hy = centro[0] + vx * (larg - 70), centro[1] + vy * (larg - 70)
        for lado in (1, -1):
            px, py = hx - vy * 32 * lado, hy + vx * 32 * lado
            self.caixa(f"macaneta-{porta.id}-{lado}", (px, py, 1050), (120, 25, 22), ang, metal, 8)

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
            textura = {"textura": TEXTURA_MOVEL[m.tipo]} if m.tipo in TEXTURA_MOVEL else {}
            mat = self.material(f"movel-{m.id}", self.cor_movel(m), rugosidade=0.55, **textura)
            for peca in self.pecas_movel(m, mat):
                x0, y0, z0, x1, y1, z1 = peca.caixa
                cx, cy = geometria.girar_movel(m, (x0 + x1) / 2, (y0 + y1) / 2)
                self.caixa(
                    f"{m.id}-{peca.nome}",
                    (cx, cy, (z0 + z1) / 2),
                    (x1 - x0, y1 - y0, z1 - z0),
                    float(m.rotacao),
                    peca.material,
                    peca.chanfro,
                )

    def pecas_movel(self, m: Movel, mat: str) -> list[Peca]:
        """Peças no referencial do móvel (costas em -y, frente em +y), com z a partir do piso.

        Cada tipo de símbolo do catálogo tem um "construtor" com as partes que fazem o
        móvel parecer de verdade (recuos, frestas, puxadores, almofadas, edredom); as
        quinas saem arredondadas pelo ``chanfro``.
        """
        item = catalogo.item_do_tipo(m.tipo)
        simbolo = item.simbolo if item else Simbolo.GENERICO
        f = _Feitio(self, m, mat)
        if m.construcao is not None:
            f.planejado()
        elif simbolo is Simbolo.CAMA:
            f.cama()
        elif simbolo is Simbolo.ASSENTO:
            f.assento()
        elif simbolo is Simbolo.CADEIRA:
            f.cadeira()
        elif simbolo is Simbolo.MESA:
            f.mesa()
        elif simbolo is Simbolo.TELA:
            f.tela()
        elif simbolo is Simbolo.PORTAS:
            f.portas()
        elif simbolo is Simbolo.GAVETAS:
            f.gavetas()
        elif simbolo is Simbolo.PRATELEIRAS:
            f.prateleiras()
        else:
            f.p("corpo", -f.w, -f.d, f.base, f.w, f.d, f.topo, chanfro=10)
        return f.pecas

    # -- câmeras e luzes

    def _livre(self, folga: float) -> BaseGeometry:
        """Área onde dá para ficar em pé: longe de paredes, móveis no piso e giro de porta."""
        bloqueios = unary_union(
            [geometria.poligono_movel(m).buffer(folga) for m in self.moveis if m.ocupa_piso]
            + [
                g.buffer(folga)
                for ab in self.pav.aberturas
                if isinstance(ab, Porta) and (g := geometria.giro_porta(self.pav, ab)) is not None
            ]
        )
        return self.util.buffer(-folga).difference(bloqueios)

    def _ponto_livre(
        self, desejado: tuple[float, float], alvo: tuple[float, float]
    ) -> tuple[float, float] | None:
        """O ponto livre mais perto de ``desejado`` no caminho até ``alvo`` (ou ``None``)."""
        for folga in (250.0, 150.0):
            livre = self._livre(folga)
            for k in range(0, 21):  # anda de ``desejado`` em direção ao alvo
                x = desejado[0] + (alvo[0] - desejado[0]) * k / 20
                y = desejado[1] + (alvo[1] - desejado[1]) * k / 20
                if math.dist((x, y), alvo) < 900:
                    break
                if livre.contains(Point(x, y)):
                    return (x, y)
        return None

    def _olhando(self, nome: str, titulo: str, pos: tuple[float, float], alvo: tuple[float, float],
                 lente: float = 14, z_alvo: float = 1000) -> dict[str, Any]:  # fmt: skip
        return {
            "nome": nome,
            "titulo": titulo,
            "tipo": "perspectiva",
            "posicao": [round(pos[0], 1), round(pos[1], 1), ALTURA_OLHO],
            "alvo": [round(alvo[0], 1), round(alvo[1], 1), z_alvo],
            "lente": lente,
        }

    def cameras_disponiveis(self) -> dict[str, dict[str, Any]]:
        """Todas as vistas que fazem sentido neste cômodo, por nome.

        - ``perspectiva``: do ponto livre mais afastado do centro (grade de 100 mm);
        - ``porta``: de quem entra, logo depois da porta, olhando o cômodo;
        - ``cama``: em pé no pé da cama, olhando a cabeceira (se houver cama);
        - ``canto-N``: de cada canto livre, olhando o centro;
        - ``superior``: de cima, sem o teto.
        """
        c = self.util.centroid
        centro = (c.x, c.y)
        vistas: dict[str, dict[str, Any]] = {}

        pos = (c.x - 1.0, c.y - 1.0)
        for folga in (FOLGA_CAMERA, 250, 150):  # relaxa a folga em cômodo apertado
            livre = self._livre(folga)
            x0, y0, x1, y1 = self.util.bounds
            grade = [
                (x0 + i * 100.0, y0 + j * 100.0)
                for i in range(int((x1 - x0) / 100) + 1)
                for j in range(int((y1 - y0) / 100) + 1)
            ]
            longe = [g for g in grade if livre.contains(Point(g)) and math.dist(g, centro) >= 1500]
            if longe:
                pos = max(longe, key=lambda g: math.dist(g, centro))
                break
        vistas["perspectiva"] = self._olhando("perspectiva", "Perspectiva", pos, centro)

        for ab in self.pav.aberturas:
            parede = self.pav.parede(ab.parede)
            if not isinstance(ab, Porta) or parede is None or ab.parede not in self.comodo.paredes:
                continue
            u, n = geometria.direcao(parede)
            s = 1 if parede.lado_a == self.comodo.id else -1
            meio = ab.distancia_inicio.valor + ab.largura.valor / 2
            px = parede.inicio[0] + u[0] * meio + n[0] * s * 450
            py = parede.inicio[1] + u[1] * meio + n[1] * s * 450
            alvo = (c.x + (c.x - px) * 0.4, c.y + (c.y - py) * 0.4)
            vistas["porta"] = self._olhando("porta", "Da porta", (px, py), alvo, lente=16)
            break

        cama = next((m for m in self.moveis if m.tipo == "cama"), None)
        if cama is not None:
            fx, fy = geometria.frente_movel(cama)
            d = cama.profundidade.valor / 2
            pe = (cama.centro[0] + fx * (d + 1300), cama.centro[1] + fy * (d + 1300))
            cabeceira = (cama.centro[0] - fx * d, cama.centro[1] - fy * d)
            onde = self._ponto_livre(pe, cabeceira)
            if onde is not None:
                vistas["cama"] = self._olhando("cama", "De frente para a cama", onde, cabeceira,
                                               lente=18, z_alvo=700)  # fmt: skip

        anel = list(orient(_maior_poligono(self.util) or Polygon(), 1.0).exterior.coords)[:-1]
        n_canto = 0
        for x, y in anel:
            dx, dy = c.x - x, c.y - y
            dist = math.hypot(dx, dy) or 1.0
            desejado = (x + dx / dist * 450, y + dy / dist * 450)
            onde = self._ponto_livre(desejado, centro)
            if onde is None:
                continue
            n_canto += 1
            vistas[f"canto-{n_canto}"] = self._olhando(
                f"canto-{n_canto}", f"Canto {n_canto}", onde, centro
            )

        x0, y0, x1, y1 = self.util.bounds
        maior = max(x1 - x0, y1 - y0)
        vistas["superior"] = {
            "nome": "superior",
            "titulo": "De cima",
            "tipo": "ortografica",
            "posicao": [c.x - maior * 0.6, c.y - maior * 0.75, maior * 2.2],
            "alvo": [c.x, c.y, 0],
            "escala": maior * 1.45,
        }
        return vistas

    def cameras(
        self, vistas: tuple[str, ...] = ("perspectiva", "superior")
    ) -> list[dict[str, Any]]:
        disponiveis = self.cameras_disponiveis()
        fora = [v for v in vistas if v not in disponiveis]
        if fora:
            raise KeyError(
                f"vista(s) {', '.join(fora)} não existem neste cômodo ({', '.join(disponiveis)})"
            )
        return [disponiveis[v] for v in vistas]

    def luzes(self) -> list[dict[str, Any]]:
        c = self.util.centroid
        x0, y0, x1, y1 = self.util.bounds
        area_m2 = self.util.area / 1e6
        return [
            {
                "tipo": "area",
                "posicao": [c.x, c.y, self.pe - 30],
                "tamanho": [(x1 - x0) * 0.6, (y1 - y0) * 0.6],
                # calibrado para a cor escolhida aparecer na imagem (piso #9a7451 sai
                # ~7% mais claro); 30 W/m² "lavava" tudo para tons pastel
                "energia": LUZ_W_M2 * area_m2,
            },
            {"tipo": "sol", "direcao": self.direcao_sol(), "energia": 2.5},
        ]

    def direcao_sol(self) -> list[float]:
        """Sol entrando pela (primeira) janela do cômodo, a ~35° de altura; sem janela,
        uma direção fixa."""
        for ab in self.pav.aberturas:
            parede = self.pav.parede(ab.parede)
            if isinstance(ab, Janela) and parede is not None and ab.parede in self.comodo.paredes:
                _, n = geometria.direcao(parede)
                s = 1 if parede.lado_a == self.comodo.id else -1
                ex, ey = n[0] * s, n[1] * s  # para dentro do cômodo
                giro = math.radians(25)  # um pouco de lado: a luz desenha a janela no piso
                dx = ex * math.cos(giro) - ey * math.sin(giro)
                dy = ex * math.sin(giro) + ey * math.cos(giro)
                alt = math.radians(35)
                return [
                    round(dx * math.cos(alt), 3),
                    round(dy * math.cos(alt), 3),
                    round(-math.sin(alt), 3),
                ]
        return [0.45, 0.35, -0.82]


@dataclass(frozen=True)
class Peca:
    nome: str
    caixa: tuple[float, float, float, float, float, float]
    """x0, y0, z0, x1, y1, z1 no referencial do móvel."""
    material: str
    chanfro: float = 0.0


class _Feitio:
    """Monta as peças de um móvel (medidas em mm; frente em +y)."""

    RODAPE = 80.0
    FRESTA = 3.0

    def __init__(self, cena: _Cena, m: Movel, mat: str) -> None:
        self.cena, self.m, self.mat = cena, m, mat
        self.w, self.d = m.largura.valor / 2, m.profundidade.valor / 2
        self.base = float(m.elevacao.valor) if m.elevacao else 0.0
        self.h = float(m.altura.valor)
        self.topo = self.base + self.h
        self.pecas: list[Peca] = []

    def p(
        self, nome: str, x0: float, y0: float, z0: float, x1: float, y1: float, z1: float,
        material: str | None = None, chanfro: float = 0.0,
    ) -> None:  # fmt: skip
        self.pecas.append(Peca(nome, (x0, y0, z0, x1, y1, z1), material or self.mat, chanfro))

    def _mat(self, nome: str, **extra: Any) -> str:
        return self.cena.material(nome, CORES_PADRAO[nome], **extra)

    @property
    def sombra(self) -> str:
        return self._mat("sombra", rugosidade=0.9)

    @property
    def metal(self) -> str:
        return self._mat("metal", rugosidade=0.3, metal=True)

    def pes(self, altura: float, lado: float = 40.0, recuo: float = 60.0) -> None:
        w, d = self.w, self.d
        xs, ys = (-w + recuo, w - recuo - lado), (-d + recuo, d - recuo - lado)
        for i, (x, y) in enumerate((x, y) for y in ys for x in xs):
            self.p(f"pe{i}", x, y, self.base, x + lado, y + lado, self.base + altura, self.metal)

    # -- tipos

    def cama(self) -> None:
        w, d, base, topo = self.w, self.d, self.base, self.topo
        colchao = self._mat("colchao", rugosidade=0.9, textura="tecido")
        edredom = self._mat("edredom", rugosidade=0.95, textura="tecido")
        trav = self._mat("travesseiro", rugosidade=0.95, textura="tecido")
        self.p("rodape", -w + 60, -d + 120, base, w - 60, d - 60, base + 100, self.sombra)
        self.p("base", -w, -d + 60, base + 100, w, d, topo - 250, chanfro=15)
        self.p("colchao", -w + 15, -d + 75, topo - 250, w - 15, d - 15, topo - 30, colchao, 50)
        inicio = -d + 75 + (2 * d) * 0.32  # o edredom cobre os 2/3 do pé, caindo pelos lados
        self.p("edredom", -w - 25, inicio, topo - 200, w + 25, d + 25, topo, edredom, 60)
        self.p("dobra", -w - 15, inicio, topo, w + 15, inicio + 200, topo + 35, edredom, 30)
        altura_cab = max(topo + 450, 1000.0)
        self.p("cabeceira", -w - 20, -d, base, w + 20, -d + 80, altura_cab, chanfro=35)
        n = 2 if self.m.largura.valor >= 1200 else 1
        larg = (2 * w - 80 * (n + 1)) / n
        for i in range(n):
            x0 = -w + 80 + i * (larg + 80)
            self.p(
                f"travesseiro{i}",
                x0,
                -d + 110,
                topo - 30,
                x0 + larg,
                -d + 490,
                topo + 130,
                trav,
                70,
            )

    def assento(self) -> None:
        w, d, base, topo = self.w, self.d, self.base, self.topo
        enc, braco = min(200.0, d / 3), min(150.0, w / 4)
        assento = min(450.0, self.h * 0.55)
        pe = 100.0
        self.pes(pe)
        self.p("base", -w, -d, base + pe, w, d, base + assento - 120, chanfro=20)
        self.p("encosto", -w, -d, base + pe, w, -d + enc, topo, chanfro=40)
        alt_braco = base + min(650.0, self.h * 0.75)
        self.p("braco-e", -w, -d + enc, base + pe, -w + braco, d, alt_braco, chanfro=45)
        self.p("braco-d", w - braco, -d + enc, base + pe, w, d, alt_braco, chanfro=45)
        livre = 2 * (w - braco)
        n = 1 if livre < 1100 else 2 if livre < 1900 else 3
        larg = (livre - 20 * (n - 1)) / n
        for i in range(n):
            x0 = -w + braco + i * (larg + 20)
            self.p(
                f"almofada{i}",
                x0,
                -d + enc,
                base + assento - 120,
                x0 + larg,
                d - 10,
                base + assento,
                chanfro=55,
            )
            self.p(
                f"encosto{i}",
                x0 + 10,
                -d + enc,
                base + assento,
                x0 + larg - 10,
                -d + enc + 170,
                topo - 50,
                chanfro=70,
            )

    def cadeira(self) -> None:
        w, d, base, topo = self.w, self.d, self.base, self.topo
        for i, (x, y) in enumerate(
            ((-w + 20, -d + 20), (w - 50, -d + 20), (-w + 20, d - 50), (w - 50, d - 50))
        ):
            self.p(f"pe{i}", x, y, base, x + 30, y + 30, base + 430)
        self.p("assento", -w, -d, base + 430, w, d, base + 470, chanfro=12)
        self.p("encosto", -w + 20, -d, base + 470, w - 20, -d + 30, topo, chanfro=12)

    def mesa(self) -> None:
        w, d, base, topo = self.w, self.d, self.base, self.topo
        self.p("tampo", -w, -d, topo - 30, w, d, topo, chanfro=6)
        for i, (x, y) in enumerate(
            ((-w + 30, -d + 30), (w - 80, -d + 30), (-w + 30, d - 80), (w - 80, d - 80))
        ):
            self.p(f"pe{i}", x, y, base, x + 50, y + 50, topo - 30, chanfro=4)

    def tela(self) -> None:
        w, d, base, topo = self.w, self.d, self.base, self.topo
        moldura = self._mat("moldura", rugosidade=0.4)
        tela = self._mat("tela", rugosidade=0.08)
        self.p("moldura", -w, -d, base, w, d, topo, moldura, 6)
        self.p("tela", -w + 12, d - 2, base + 12, w - 12, d + 1, topo - 12, tela)

    def portas(self) -> None:
        w, d, base, topo, r, fr = self.w, self.d, self.base, self.topo, self.RODAPE, self.FRESTA
        self.p("rodape", -w + 40, -d, base, w - 40, d - 60, base + r, self.sombra)
        self.p("corpo", -w, -d, base + r, w, d - 20, topo, chanfro=4)
        alto, meio = base + r + fr, (base + r + topo) / 2
        if self.m.portas == "correr":  # duas folhas, uma na frente da outra
            self.p("folha0", -w, d - 40, alto, fr, d - 20, topo - fr, chanfro=3)
            self.p("folha1", -fr, d - 20, alto, w, d, topo - fr, chanfro=3)
            for i, x in enumerate((-w + 60, w - 75)):
                y = d - 40 if i == 0 else d - 20
                self.p(f"puxador{i}", x, y + 20, meio - 250, x + 15, y + 35, meio + 250, self.metal)
            return
        n = max(1, round(2 * w / 500))
        larg = 2 * w / n
        for i in range(n):
            x0 = -w + i * larg
            self.p(
                f"folha{i}", x0 + fr / 2, d - 20, alto, x0 + larg - fr / 2, d, topo - fr, chanfro=3
            )
            # puxador do lado que abre: as folhas abrem aos pares, a partir do meio do par
            x = x0 + larg - 50 if i % 2 == 0 else x0 + 35
            self.p(f"puxador{i}", x, d, meio - 150, x + 15, d + 25, meio + 150, self.metal)

    def gavetas(self) -> None:
        w, d, base, topo, fr = self.w, self.d, self.base, self.topo, self.FRESTA
        pe = 80.0 if self.base == 0 else 0.0
        if pe:
            self.pes(pe, lado=35, recuo=40)
        self.p("corpo", -w, -d, base + pe, w, d - 18, topo, chanfro=4)
        n = max(1, min(6, round((self.h - pe) / 220)))
        alt = (topo - base - pe) / n
        for i in range(n):
            z0 = base + pe + i * alt
            self.p(f"gaveta{i}", -w + fr, d - 18, z0 + fr, w - fr, d, z0 + alt - fr, chanfro=3)
            self.p(
                f"puxador{i}", -60, d, z0 + alt / 2 - 8, 60, d + 22, z0 + alt / 2 + 8, self.metal
            )

    def prateleiras(self) -> None:
        w, d, base, topo = self.w, self.d, self.base, self.topo
        e = 18.0
        self.p("fundo", -w, -d, base, w, -d + 6, topo)
        self.p("lateral-e", -w, -d, base, -w + e, d, topo, chanfro=2)
        self.p("lateral-d", w - e, -d, base, w, d, topo, chanfro=2)
        n = max(2, round(self.h / 350))
        for i in range(n + 1):
            z = base + i * (self.h - e) / n
            self.p(f"prateleira{i}", -w + e, -d + 6, z, w - e, d, z + e, chanfro=2)

    def planejado(self) -> None:
        w, d, base, topo = self.w, self.d, self.base, self.topo
        self.p("caixa", -w, -d, base, w, d - 20, topo, chanfro=4)
        try:
            calc = planejado.calcular(self.m)
        except planejado.ConstrucaoInvalidaError:
            calc = None
        portas = [r for r in calc.layout if r.tipo == "porta"] if calc else []
        for i, r in enumerate(portas):  # folhas um pouco afastadas: mostram as divisões
            x0 = -w + r.x + 2
            z0, z1 = base + r.y + 2, base + r.y + r.altura - 2
            self.p(f"porta{i}", x0, d - 20, z0, x0 + r.largura - 4, d, z1, chanfro=3)
            x = x0 + r.largura - 50 if i % 2 == 0 else x0 + 35
            meio = (z0 + z1) / 2
            self.p(f"puxador{i}", x, d, meio - 120, x + 15, d + 25, meio + 120, self.metal)
        if not portas:
            self.p("frente", -w, d - 20, base, w, d, topo, chanfro=3)


def montar_cena(
    carregado: ProjetoCarregado,
    comodo: str,
    variacao: str | None = None,
    largura: int = 1600,
    altura: int = 1000,
    amostras: int = 96,
    vistas: tuple[str, ...] = ("perspectiva", "superior"),
) -> dict[str, Any]:
    """Cena do cômodo em JSON, pronta para o ``bpy_cena.py``.

    ``variacao``: nome de um arquivo em ``variacoes/<comodo>/``; ``None`` = cores padrão.
    ``vistas``: quais câmeras renderizar (ver :func:`vistas_do_comodo`).
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
    cena.luminarias()
    estimadas = carregado.estimadas(comodo)
    return {
        "versao": VERSAO_CENA,
        "comodo": comodo,
        "variacao": variacao or "base",
        "prismas": cena.prismas,
        "caixas": cena.caixas,
        "materiais": cena.materiais,
        "cameras": cena.cameras(vistas),
        "luzes": cena.luzes(),
        "aviso": f"{AVISO_OBRA} · {len(estimadas)} medida(s) estimada(s)" if estimadas else None,
        "saida": {"largura": largura, "altura": altura, "amostras": amostras},
    }


def _cena_do_comodo(carregado: ProjetoCarregado, comodo: str) -> _Cena:
    pav = carregado.projeto.pavimento_do_comodo(comodo)
    if pav is None:
        raise KeyError(f"cômodo '{comodo}' não existe no projeto")
    c = pav.comodo(comodo)
    assert c is not None
    return _Cena(carregado, pav, c, None)


def vistas_do_comodo(carregado: ProjetoCarregado, comodo: str) -> list[dict[str, str]]:
    """Vistas disponíveis (nome e título) para a tela oferecer."""
    disponiveis = _cena_do_comodo(carregado, comodo).cameras_disponiveis()
    return [{"nome": n, "titulo": v["titulo"]} for n, v in disponiveis.items()]
