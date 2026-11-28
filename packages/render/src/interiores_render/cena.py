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
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Any

from shapely import LineString, Point, Polygon
from shapely import box as shapely_box
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from interiores_core import bancada, catalogo, escadas, geometria, planejado
from interiores_core.acabamentos import ACABAMENTOS
from interiores_core.carregar import ProjetoCarregado
from interiores_core.catalogo import Simbolo
from interiores_core.modelo import (
    Comodo,
    Escada,
    Janela,
    Laje,
    Movel,
    Pavimento,
    Pilar,
    PontoInstalacao,
    Porta,
    Variacao,
)
from interiores_core.partes import ALTURA_MIN_CAIXA, CORPO, eh_cooktop, parte_da_peca

VERSAO_CENA = 19
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
    "inox": "#B9BCC0",
    "vidro_preto": "#1C1D20",
    "escada": "#CFC8BC",
}
CORES_MOVEIS = {
    "pia": "#F2F0EC",
    "beliche": "#B08968",
    "aparador": "#8B6B4F",
    "painel_tv": "#7A5C44",
    "cadeira_escritorio": "#3A3A3A",
    "puff": "#9C8C7A",
    "maquina_lavar": "#F4F4F2",
    "tanque": "#F4F4F2",
    "lavatorio": "#F2F0EC",
    "vaso": "#FBFBFA",
    "box": "#D8D4CC",
    "fogao": "#D9DBDE",
    "geladeira": "#E9EAEC",
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
    "monitor": "#1A1A1A",
    "notebook": "#A7ABB0",
    "computador": "#1E1E1E",
    "teclado": "#2C2C2C",
    "impressora": "#E6E6E4",
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
    "beliche": "madeira",
    "aparador": "madeira",
    "painel_tv": "madeira",
    "puff": "tecido",
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


def _sem_furos(pol: Polygon) -> list[Polygon]:
    """Pedaços sem buraco (o prisma só leva o contorno de fora): corta numa vertical pelo
    meio de cada furo até não sobrar nenhum (laje com o vão da escada, por exemplo)."""
    if not pol.interiors:
        return [pol]
    x = Polygon(pol.interiors[0]).centroid.x
    x0, y0, x1, y1 = pol.bounds
    pedacos = []
    for a, b in ((x0 - 1, x), (x, x1 + 1)):
        for p in _poligonos(pol.intersection(shapely_box(a, y0 - 1, b, y1 + 1))):
            pedacos += _sem_furos(p)
    return pedacos


CORTE_SUPERIOR = 120.0
"""Altura (mm) das paredes do lado da câmera na vista de cima do cômodo (o resto sai)."""


@dataclass
class _PecasParede:
    """O que uma parede gerou na cena (fatias das listas) e o corpo dela sem os vãos."""

    p0: int
    p1: int
    c0: int
    c1: int
    cheio: list[Polygon]
    material: str


class _Cena:
    def __init__(
        self,
        carregado: ProjetoCarregado,
        pav: Pavimento,
        comodo: Comodo,
        variacao: Variacao | None,
        no_pavimento: bool = False,
    ) -> None:
        """``no_pavimento``: o cômodo é parte da cena do pavimento inteiro — nomes de
        piso, teto, rodapé e móveis levam o id do cômodo (não colidem com os vizinhos)."""
        self.pav = pav
        self.comodo = comodo
        self.no_pavimento = no_pavimento
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
        self.cores_pecas: dict[str, dict[str, str]] = {}
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
            self.cores_pecas = {k: dict(v) for k, v in c.pecas.items()}
        self.prismas: list[dict[str, Any]] = []
        self.caixas: list[dict[str, Any]] = []
        self.materiais: dict[str, dict[str, Any]] = {}
        self.ocupado: BaseGeometry = Polygon()
        """Corpo das paredes já construídas (sem faces sobrepostas nas quinas)."""
        self.paredes_feitas: set[str] = set()
        self.pecas_parede: dict[str, _PecasParede] = {}
        """Paredes já construídas: no pavimento, a parede entre dois cômodos sai uma vez."""
        self._marca: dict[str, str] = {}
        """``extras`` que toda peça criada agora leva (ver :meth:`marcando`)."""

    @contextmanager
    def marcando(self, **marca: str) -> Iterator[None]:
        """As peças criadas dentro do bloco levam ``marca`` nos ``extras`` (ex.: ``parede`` e
        ``abertura``: o visor isola uma porta/janela com o trecho de parede dela)."""
        antes = self._marca
        self._marca = {**antes, **marca}
        try:
            yield
        finally:
            self._marca = antes

    def _n(self, nome: str) -> str:
        return f"{nome}-{self.comodo.id}" if self.no_pavimento else nome

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
        if self._marca:
            extra["extras"] = {**self._marca, **extra.get("extras", {})}
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
        extras: dict[str, str] | None = None,
    ) -> None:
        """``extras``: vão para o .glb (ex.: ``movel`` e ``parte``, para o visor pintar)."""
        if min(tamanho) <= 0:
            return
        if self._marca:
            extras = {**self._marca, **(extras or {})}
        self.caixas.append(
            {
                "nome": nome,
                "centro": [round(v, 1) for v in centro],
                "tamanho": [round(v, 1) for v in tamanho],
                "rotacao": rotacao,
                "material": material,
                **({"chanfro": chanfro} if chanfro else {}),
                **({"oculto_em": oculto_em} if oculto_em else {}),
                **({"extras": extras} if extras else {}),
            }
        )

    # -- arquitetura

    def piso_teto(self) -> None:
        piso = self.material(
            self._n("piso"), self.cores["piso"], rugosidade=0.45, textura=self.textura_piso
        )
        self.prisma(self._n("piso"), self.util, -20, 0, piso)
        if self._laje_cobre():
            return  # a laje faz o teto (ver :meth:`vigas_e_lajes`)
        teto = self.material("teto", self.cores["teto"])
        self.prisma(
            self._n("teto"), self.util, self.pe, self.pe + 20, teto, oculto_em=self._oculto_teto
        )

    @property
    def _oculto_teto(self) -> list[str]:
        """Vistas onde o teto (e a laje e as vigas) some: no pavimento as duas vistas são de
        fora, por cima."""
        return ["superior", "perspectiva"] if self.no_pavimento else ["superior"]

    def _laje_cobre(self) -> bool:
        """Alguma laje do pavimento cobre (quase todo) este cômodo."""
        for e in self.pav.estrutura:
            if isinstance(e, Laje):
                g = geometria.poligono_estrutura(self.pav, e)
                if g is not None and g.intersection(self.util).area >= 0.5 * self.util.area:
                    return True
        return False

    # -- estrutura

    def _recorte(self) -> BaseGeometry | None:
        """Na cena do cômodo, só a estrutura em volta dele (com a espessura das paredes);
        no pavimento, tudo."""
        if self.no_pavimento:
            return None
        esp = max((p.espessura.valor for p in self.pav.paredes), default=150)
        return self.util.buffer(esp, join_style="mitre")

    def pilares(self) -> None:
        """Pilares do piso ao pé-direito, antes das paredes: a parede sai recortada em volta
        (faces sobrepostas saem pretas no render)."""
        mat = self.material("parede", self.cores["parede"], rugosidade=0.85, textura="pintura")
        recorte, pe = self._recorte(), float(self.pav.pe_direito.valor)
        for e in self.pav.estrutura:
            if not isinstance(e, Pilar):
                continue
            g = geometria.poligono_estrutura(self.pav, e)
            if g is None or (recorte is not None and not recorte.intersects(g)):
                continue
            with self.marcando(estrutura=e.id):
                self.prisma(f"pilar-{e.id}", g, 0, pe, mat)
            self.ocupado = self.ocupado.union(g)

    def escadas_(self) -> None:
        """Escada de alvenaria maciça: cada degrau (e o patamar) cheio do piso até o topo dele;
        no caracol, o núcleo do piso à chegada."""
        recorte = self._recorte()
        pedra = self.material("escada", CORES_PADRAO["escada"], rugosidade=0.6)
        for e in self.pav.estrutura:
            if not isinstance(e, Escada):
                continue
            calc = escadas.calcular(self.pav, e)
            if recorte is not None and not recorte.intersects(calc.contorno):
                continue
            with self.marcando(estrutura=e.id):
                for d in calc.degraus:
                    self.prisma(f"degrau-{e.id}-{d.numero}", d.poligono, 0, d.z, pedra)
                if calc.nucleo is not None:
                    self.prisma(f"nucleo-{e.id}", calc.nucleo, 0, calc.desnivel, pedra)

    def vigas_e_lajes(self) -> None:
        """Vigas (só o trecho fora das paredes: dentro delas não aparece) descendo da laje, e
        lajes do pé-direito para cima, no lugar do teto (somem nas vistas de cima)."""
        recorte, pe = self._recorte(), float(self.pav.pe_direito.valor)
        paredes = unary_union(
            [geometria.corpo(p) for p in self.pav.paredes if geometria.comprimento(p) > 0]
        )
        parede = self.material("parede", self.cores["parede"], rugosidade=0.85, textura="pintura")
        teto = self.material("teto", self.cores["teto"])
        oculto = self._oculto_teto
        for e in self.pav.estrutura:
            if isinstance(e, Pilar | Escada):
                continue
            g: BaseGeometry | None = geometria.poligono_estrutura(self.pav, e)
            if g is None:
                continue
            if recorte is not None:
                g = g.intersection(recorte)
            with self.marcando(estrutura=e.id):
                if isinstance(e, Laje):
                    pedacos = [q for p in _poligonos(g) for q in _sem_furos(p)]
                    for i, pol in enumerate(pedacos):
                        z1 = pe + e.espessura.valor
                        self.prisma(f"laje-{e.id}-{i}", pol, pe, z1, teto, oculto_em=oculto)
                else:
                    z0 = pe - e.altura.valor
                    for i, pol in enumerate(_poligonos(g.difference(paredes))):
                        self.prisma(f"viga-{e.id}-{i}", pol, z0, pe, parede, oculto_em=oculto)

    def paredes(self, ids: list[str] | None = None) -> None:
        """Paredes do cômodo (ou as ``ids`` pedidas) com os vãos, caixilhos e portas."""
        geral = self.material("parede", self.cores["parede"], rugosidade=0.85, textura="pintura")
        mat_vidro = self.material("vidro", CORES_PADRAO["vidro"], vidro=True)
        for pid in self.comodo.paredes if ids is None else ids:
            parede = self.pav.parede(pid)
            if parede is None or geometria.comprimento(parede) == 0:
                continue
            if pid in self.paredes_feitas:  # já saiu pelo cômodo vizinho: só a folha da porta
                for ab in self.pav.aberturas:
                    if ab.parede == pid and isinstance(ab, Porta):
                        with self.marcando(parede=pid, abertura=ab.id):
                            self.porta(ab, parede)
                continue
            self.paredes_feitas.add(pid)
            ini_p, ini_c = len(self.prismas), len(self.caixas)
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
            corpo = inteiro.difference(self.ocupado)
            self.ocupado = self.ocupado.union(inteiro)
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
            with self.marcando(parede=pid):
                for i, pol in enumerate(_poligonos(cheio)):
                    self.prisma(f"parede-{pid}-{i}", pol, 0, altura, mat)
            for vao, ab in vaos:
                with self.marcando(parede=pid, abertura=ab.id):
                    self._vao(parede, vao, ab, corpo, altura, mat, mat_vidro)
            self.pecas_parede[pid] = _PecasParede(
                ini_p, len(self.prismas), ini_c, len(self.caixas), _poligonos(cheio), mat
            )

    def _vao(
        self, parede: Any, vao: Polygon, ab: Porta | Janela, corpo: BaseGeometry,
        altura: float, mat: str, mat_vidro: str,
    ) -> None:  # fmt: skip
        """Peças de um vão: peitoril, vidro e caixilho (janela) ou folha e batente (porta),
        e a verga em cima."""
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

    def cortar_paredes_da_frente(self, camera: dict[str, Any], outras: list[str]) -> None:
        """Vista de cima (oblíqua, de um canto): as paredes do lado da câmera escondem o que
        está encostado nelas. Nessa vista elas saem inteiras de cena e entram só "tocos" de
        ``CORTE_SUPERIOR`` mm (o contorno do cômodo continua), como numa maquete cortada.
        ``outras``: as outras vistas desta cena, onde os tocos não aparecem."""
        c = self.util.centroid
        dx, dy = camera["posicao"][0] - c.x, camera["posicao"][1] - c.y
        tam = math.hypot(dx, dy)
        if tam < 1:
            return  # câmera bem em cima: nada esconde nada
        dx, dy = dx / tam, dy / tam
        for pid, pecas in self.pecas_parede.items():
            parede = self.pav.parede(pid)
            if parede is None:
                continue
            _, n = geometria.direcao(parede)
            s = 1 if parede.lado_a == self.comodo.id else -1
            fora = (-n[0] * s, -n[1] * s)  # normal para fora do cômodo
            if fora[0] * dx + fora[1] * dy < 0.2:
                continue  # parede do fundo ou de lado: fica inteira
            for item in self.prismas[pecas.p0 : pecas.p1] + self.caixas[pecas.c0 : pecas.c1]:
                item["oculto_em"] = [*item.get("oculto_em", []), "superior"]
            for i, pol in enumerate(pecas.cheio):
                extra = {"oculto_em": outras} if outras else {}
                self.prisma(
                    f"parede-{pid}-corte-{i}", pol, 0, CORTE_SUPERIOR, pecas.material, **extra
                )

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
        # sem tipo informado: como sempre foi (montante no meio só nas janelas largas)
        tipo = janela.abertura or "correr"
        folhas = janela.folhas or (2 if janela.abertura or larg > 900 else 1)
        if tipo in ("correr", "abrir"):
            for i in range(1, folhas):  # montantes entre as folhas
                x = d0 + larg * i / folhas
                self._no_vao(
                    parede, x, 0, pe + alt / 2, (40, f - 10, vao), f"caixilho-{janela.id}-m{i}", mat
                )
        elif tipo == "basculante":  # palhetas horizontais
            for i in (1, 2):
                z = pe + e + vao * i / 3
                self._no_vao(
                    parede,
                    meio,
                    0,
                    z,
                    (larg - 2 * e, f - 10, 30),
                    f"caixilho-{janela.id}-p{i}",
                    mat,
                )
        if tipo in ("maxim_ar", "basculante", "abrir"):  # puxador
            metal = self.material("metal", CORES_PADRAO["metal"], rugosidade=0.3, metal=True)
            self._no_vao(
                parede,
                meio,
                f / 2 + 12,
                pe + e + 20,
                (90, 20, 18),
                f"caixilho-{janela.id}-px",
                metal,
                6,
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
                oculto = ["superior", "perspectiva"] if self.no_pavimento else ["superior"]
                self.caixa(f"luminaria-{i.id}", (x, y, self.pe - 35), tamanho, 0.0, mat, 30, oculto)

    def porta(self, porta: Porta, parede: Any) -> None:
        """Folha aberta a 90° para dentro do cômodo (portas que abrem para fora não aparecem).
        Camarão: as duas folhas dobradas em "V" junto da dobradiça."""
        if porta.folha not in ("giro", "camarao") or porta.abre_para != self.comodo.id:
            return
        if porta.folha == "camarao":
            self.porta_camarao(porta, parede)
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
        self.folha_porta(porta, (mx, my), ang, larg, float(alt), mat)
        # maçaneta perto da ponta da folha, dos dois lados
        metal = self.material("metal", CORES_PADRAO["metal"], rugosidade=0.3, metal=True)
        vx, vy = (ponta[0] - centro[0]) / larg, (ponta[1] - centro[1]) / larg
        hx, hy = centro[0] + vx * (larg - 70), centro[1] + vy * (larg - 70)
        for lado in (1, -1):
            px, py = hx - vy * 32 * lado, hy + vx * 32 * lado
            self.caixa(f"macaneta-{porta.id}-{lado}", (px, py, 1050), (120, 25, 22), ang, metal, 8)

    def folha_porta(
        self, porta: Porta, meio: tuple[float, float], ang: float, larg: float, alt: float,
        mat: str, nome: str | None = None,
    ) -> None:  # fmt: skip
        """Uma folha de porta (centro ``meio`` na planta, girada ``ang``) com o estilo dela:
        lisa, almofadada (almofadas salientes nas duas faces), vidro (visor no alto) ou
        veneziana (palhetas na metade de baixo)."""
        nome = nome or f"porta-{porta.id}"
        estilo = porta.estilo or "lisa"
        mx, my = meio
        r = math.radians(ang)
        ux, uy = math.cos(r), math.sin(r)

        def em(ao_longo: float) -> tuple[float, float]:
            return mx + ux * ao_longo, my + uy * ao_longo

        if estilo != "vidro":
            self.caixa(nome, (mx, my, alt / 2), (larg, 35, alt), ang, mat, 3)
        m = min(120.0, larg * 0.15)
        if estilo == "almofadada":
            meio_z = alt * 0.48
            for i, (z0, z1) in enumerate(
                ((m * 1.5, meio_z - m / 2), (meio_z + m / 2, alt - m * 1.5))
            ):
                self.caixa(
                    f"{nome}-almofada{i}",
                    (mx, my, (z0 + z1) / 2),
                    (larg - 2 * m, 43, z1 - z0),
                    ang,
                    mat,
                    6,
                )
        elif estilo == "vidro":
            vidro = self.material("vidro", CORES_PADRAO["vidro"], vidro=True)
            z_vidro = alt * 0.45
            self.caixa(nome, (mx, my, z_vidro / 2), (larg, 35, z_vidro), ang, mat, 3)
            topo = alt - m * 1.5
            self.caixa(
                f"{nome}-travessa", (mx, my, (topo + alt) / 2), (larg, 35, alt - topo), ang, mat, 3
            )
            for lado in (-1, 1):
                cx, cy = em(lado * (larg - m) / 2)
                self.caixa(
                    f"{nome}-montante{lado}",
                    (cx, cy, (z_vidro + topo) / 2),
                    (m, 35, topo - z_vidro),
                    ang,
                    mat,
                    3,
                )
            self.caixa(
                f"{nome}-vidro",
                (mx, my, (z_vidro + topo) / 2),
                (larg - 2 * m, 10, topo - z_vidro),
                ang,
                vidro,
            )
        elif estilo == "veneziana":
            z = m * 1.5
            i = 0
            while z < alt * 0.45:
                self.caixa(f"{nome}-palheta{i}", (mx, my, z), (larg - 2 * m, 41, 18), ang, mat, 2)
                z += 60.0
                i += 1

    def porta_camarao(self, porta: Porta, parede: Any) -> None:
        """Duas folhas de meia largura dobradas em "V" (60°) junto da dobradiça."""
        u, n = geometria.direcao(parede)
        s = 1 if porta.abre_para == parede.lado_a else -1
        d0, larg, alt = porta.distancia_inicio.valor, porta.largura.valor, float(porta.altura.valor)
        meia = parede.espessura.valor / 2
        ini = (parede.inicio[0] + u[0] * d0, parede.inicio[1] + u[1] * d0)
        fim = (ini[0] + u[0] * larg, ini[1] + u[1] * larg)
        dobradica, outro = (ini, fim) if porta.dobradica != "fim" else (fim, ini)
        v = ((outro[0] - dobradica[0]) / larg, (outro[1] - dobradica[1]) / larg)
        w = (n[0] * s, n[1] * s)
        p0 = (dobradica[0] + w[0] * meia, dobradica[1] + w[1] * meia)
        f = larg / 2
        p1 = (p0[0] + v[0] * f * 0.5 + w[0] * f * 0.866, p0[1] + v[1] * f * 0.5 + w[1] * f * 0.866)
        p2 = (p0[0] + v[0] * f, p0[1] + v[1] * f)
        mat = self.material("porta", CORES_PADRAO["porta"], rugosidade=0.5)
        for i, (a, b) in enumerate(((p0, p1), (p1, p2))):
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            self.folha_porta(
                porta,
                ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
                ang,
                f - 6,
                alt,
                mat,
                f"porta-{porta.id}-{i}",
            )

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
            self.prisma(self._n(f"rodape-{i}"), pol, 0, h, mat)

    # -- móveis

    def moveis_(self) -> None:
        for m in self.moveis:
            mat = self.material_movel(m)
            if m.forma is not None and _forma_em_bloco(m):
                self.movel_com_forma(m, mat)
                continue
            for peca in self.pecas_movel(m, mat):
                x0, y0, z0, x1, y1, z1 = peca.caixa
                cx, cy = geometria.girar_movel(m, (x0 + x1) / 2, (y0 + y1) / 2)
                parte = parte_da_peca(peca.nome)
                self.caixa(
                    self._n(f"{m.id}-{peca.nome}"),
                    (cx, cy, (z0 + z1) / 2),
                    (x1 - x0, y1 - y0, z1 - z0),
                    float(m.rotacao),
                    self.material_da_parte(m, parte, peca.material),
                    peca.chanfro,
                    extras={"movel": m.id, "parte": parte, **peca.extras},
                )

    def material_movel(self, m: Movel) -> str:
        """Material da caixa: o acabamento escolhido (textura, brilho e cor padrão) ou o
        padrão do tipo. A cor da variação vale por cima dos dois."""
        acab = ACABAMENTOS.get(m.acabamento) if m.acabamento else None
        if acab is None:
            textura = {"textura": TEXTURA_MOVEL[m.tipo]} if m.tipo in TEXTURA_MOVEL else {}
            return self.material(f"movel-{m.id}", self.cor_movel(m), rugosidade=0.55, **textura)
        pintada = self.cores_moveis.get(m.id) or self.cores_moveis.get(m.tipo)
        extra: dict[str, Any] = {}
        if acab.textura == "madeira":
            extra["textura"] = "madeira"
        elif acab.textura == "madeira_lisa":
            extra.update(textura="madeira", tabuas=False)
        return self.material(
            f"movel-{m.id}", pintada or acab.cor, rugosidade=acab.rugosidade, **extra
        )

    def movel_com_forma(self, m: Movel, mat: str) -> None:
        """Móvel arredondado, redondo ou em L: o corpo (ou o tampo, na mesa) é a forma
        extrudada; a mesa ganha pés distribuídos por dentro da forma."""
        base = float(m.elevacao.valor) if m.elevacao else 0.0
        topo = base + m.altura.valor
        forma = geometria.poligono_movel(m)
        item = catalogo.item_do_tipo(m.tipo)
        if item is None or item.simbolo is not Simbolo.MESA:
            self.prisma(self._n(f"{m.id}-corpo"), forma, base, topo, mat,
                        extras={"movel": m.id, "parte": CORPO})  # fmt: skip
            return
        tampo = self.material_da_parte(m, "tampo", mat)
        self.prisma(self._n(f"{m.id}-tampo"), forma, topo - 30, topo, tampo,
                    extras={"movel": m.id, "parte": "tampo"})  # fmt: skip
        pe = self.material_da_parte(m, "pes", mat)
        for i, (x, y) in enumerate(_pes_da_forma(m)):
            cx, cy = geometria.girar_movel(m, x, y)
            self.caixa(self._n(f"{m.id}-pe{i}"), (cx, cy, (base + topo - 30) / 2),
                       (50, 50, topo - 30 - base), float(m.rotacao), pe, 4,
                       extras={"movel": m.id, "parte": "pes"})  # fmt: skip

    def material_da_parte(self, m: Movel, parte: str, base: str) -> str:
        """Material da peça: o dela, ou uma cópia com a cor da parte na variação (o id do
        móvel vale mais que o tipo). Mantém textura e acabamento do original."""
        if parte == CORPO:
            return base
        cor = self.cores_pecas.get(m.id, {}).get(parte) or self.cores_pecas.get(m.tipo, {}).get(
            parte
        )
        if not cor:
            return base
        props = {k: v for k, v in self.materiais[base].items() if k != "cor"}
        # ``base@móvel@parte``: o visor 3D lê a base para voltar à cor dela
        return self.material(f"{base}@{m.id}@{parte}", cor, **props)

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
        elif m.bancada is not None:
            f.bancada()
        elif simbolo is Simbolo.CAMA:
            f.cama()
        elif simbolo is Simbolo.ASSENTO and m.forma == "L" and m.tipo == "sofa":
            f.assento_l()
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
        elif simbolo is Simbolo.PIA:
            f.pia()
        elif simbolo is Simbolo.FOGAO:
            f.fogao()
        elif simbolo is Simbolo.GELADEIRA:
            f.geladeira()
        elif simbolo is Simbolo.VASO:
            f.vaso()
        elif simbolo is Simbolo.BOX:
            f.box()
        elif simbolo is Simbolo.BELICHE:
            f.beliche()
        elif simbolo is Simbolo.CADEIRA_GIRATORIA:
            f.cadeira_giratoria()
        elif simbolo is Simbolo.MAQUINA:
            f.maquina()
        elif simbolo is Simbolo.MONITOR:
            f.monitor()
        elif simbolo is Simbolo.NOTEBOOK:
            f.notebook()
        elif simbolo is Simbolo.GABINETE:
            f.gabinete()
        elif simbolo is Simbolo.TECLADO:
            f.teclado()
        else:
            f.p("corpo", -f.w, -f.d, f.base, f.w, f.d, f.topo, chanfro=10)
        return f.pecas

    # -- câmeras e luzes

    def _livre(self, folga: float) -> BaseGeometry:
        """Área onde dá para ficar em pé: longe de paredes, pilares, escadas, móveis no piso e
        giro de porta."""
        bloqueios = unary_union(
            [geometria.poligono_movel(m).buffer(folga) for m in self.moveis if m.ocupa_piso]
            + [
                g.buffer(folga)
                for e in self.pav.estrutura
                if isinstance(e, Pilar | Escada)
                and (g := geometria.poligono_estrutura(self.pav, e))
            ]
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
            # mira um pouco acima do piso e com folga: as paredes do fundo (inteiras) sobem no
            # quadro; as da frente saem cortadas (``cortar_paredes_da_frente``)
            "posicao": [c.x - maior * 0.6, c.y - maior * 0.75, maior * 2.2 + self.pe * 0.15],
            "alvo": [c.x, c.y, self.pe * 0.15],
            "escala": maior * 1.85,
        }
        return vistas

    def cameras(
        self, vistas: tuple[str, ...] = ("perspectiva", "superior")
    ) -> list[dict[str, Any]]:
        if not vistas:  # cena para a tela (3D ao vivo): sem câmeras, sem a busca de ponto livre
            return []
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


def _forma_em_bloco(m: Movel) -> bool:
    """Móvel cuja forma sai como bloco extrudado (genérico, mesa); o sofá em L é montado
    peça a peça (:meth:`_Feitio.assento_l`)."""
    return m.tipo != "sofa" and m.bancada is None and len(geometria.formas_possiveis(m)) > 1


def _pes_da_forma(m: Movel) -> list[tuple[float, float]]:
    """Onde vão os pés de uma mesa com forma (referencial do móvel): redonda, nos quatro
    "cantos" da elipse; arredondada e em L, nos cantos da forma recuados para dentro."""
    w, d = m.largura.valor / 2, m.profundidade.valor / 2
    if m.forma == "redondo":
        return [(0.62 * w * math.cos(a), 0.62 * d * math.sin(a))
                for a in (math.pi / 4 * k for k in (1, 3, 5, 7))]  # fmt: skip
    recuo = 70.0
    if m.forma == "arredondado":
        r = min(float(m.raio.valor) if m.raio else geometria.RAIO_PADRAO, w, d)
        recuo = max(recuo, r * 0.6 + 40)
        return [(sx * (w - recuo), sy * (d - recuo)) for sx in (-1, 1) for sy in (-1, 1)]
    dentro = geometria.contorno_local(m).buffer(-recuo, join_style="mitre")
    if dentro.is_empty or not isinstance(dentro, Polygon):
        return [(0.0, 0.0)]
    return [(float(x), float(y)) for x, y in list(dentro.exterior.coords)[:-1]]


def _divide(a: float, b: float, folga: float = 20.0) -> list[tuple[float, float]]:
    """Trecho [a, b] em 1 a 3 almofadas iguais (como no sofá reto), com ``folga`` entre elas."""
    livre = b - a
    n = 1 if livre < 1100 else 2 if livre < 1900 else 3
    larg = (livre - folga * (n - 1)) / n
    return [(a + i * (larg + folga), a + i * (larg + folga) + larg) for i in range(n)]


_COS_SEN = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}


@dataclass(frozen=True)
class Peca:
    nome: str
    caixa: tuple[float, float, float, float, float, float]
    """x0, y0, z0, x1, y1, z1 no referencial do móvel."""
    material: str
    chanfro: float = 0.0
    extras: dict[str, str] = field(default_factory=dict)
    """Vão para os ``extras`` da peça na cena (ex.: ``da_porta`` no puxador da porta)."""


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
        material: str | None = None, chanfro: float = 0.0, extras: dict[str, str] | None = None,
    ) -> None:  # fmt: skip
        caixa = (x0, y0, z0, x1, y1, z1)
        self.pecas.append(Peca(nome, caixa, material or self.mat, chanfro, dict(extras or {})))

    def _mat(self, nome: str, **extra: Any) -> str:
        return self.cena.material(nome, CORES_PADRAO[nome], **extra)

    @property
    def sombra(self) -> str:
        return self._mat("sombra", rugosidade=0.9)

    @property
    def metal(self) -> str:
        return self._mat("metal", rugosidade=0.3, metal=True)

    def pes(
        self, altura: float, lado: float = 40.0, recuo: float = 60.0,
        pontos: list[tuple[float, float]] | None = None,
    ) -> None:  # fmt: skip
        """Quatro pés no estilo escolhido: quadrado (metal, o padrão), palito (fino, na cor
        do móvel), metálico fino ou nenhum (rodapé recuado escuro). ``pontos``: centros dos
        pés para quem não é retângulo (sofá em L); o rodapé segue o contorno recuado."""
        w, d, estilo = self.w, self.d, self.m.pes or "quadrado"
        if pontos is not None:
            self._pes_em(altura, lado, recuo, pontos, estilo)
            return
        if estilo == "rodape":
            self.p("rodape", -w + recuo, -d + recuo, self.base, w - recuo, d - recuo,
                   self.base + altura, self.sombra)  # fmt: skip
            return
        mat, chanfro = self.metal, 0.0
        if estilo == "palito":
            lado, recuo, mat, chanfro = lado * 0.7, recuo + 10, self.mat, lado * 0.3
        elif estilo == "metalico":
            lado = 18.0
        xs, ys = (-w + recuo, w - recuo - lado), (-d + recuo, d - recuo - lado)
        for i, (x, y) in enumerate((x, y) for y in ys for x in xs):
            self.p(f"pe{i}", x, y, self.base, x + lado, y + lado, self.base + altura, mat,
                   chanfro=chanfro)  # fmt: skip

    def _pes_em(
        self, altura: float, lado: float, recuo: float, pontos: list[tuple[float, float]],
        estilo: str,
    ) -> None:  # fmt: skip
        if estilo == "rodape":  # sem pé: rodapé escuro recuado nos dois trechos do L
            w, d, b = self.w, self.d, geometria.braco_l(self.m)
            s = -1.0 if self.m.lado_l == "direita" else 1.0
            trechos = ((-w + recuo, -d + recuo, w - recuo, -d + b - recuo),
                       (w - b + recuo, -d + b - recuo, w - recuo, d - recuo))  # fmt: skip
            for nome, (x0, y0, x1, y1) in zip(("rodape", "rodape-l"), trechos, strict=True):
                xa, xb = sorted((x0 * s, x1 * s))
                self.p(nome, xa, y0, self.base, xb, y1, self.base + altura, self.sombra)
            return
        mat, chanfro = self.metal, 0.0
        if estilo == "palito":
            lado, mat, chanfro = lado * 0.7, self.mat, lado * 0.3
        elif estilo == "metalico":
            lado = 18.0
        for i, (x, y) in enumerate(pontos):
            self.p(f"pe{i}", x - lado / 2, y - lado / 2, self.base, x + lado / 2, y + lado / 2,
                   self.base + altura, mat, chanfro=chanfro)  # fmt: skip

    def puxador(
        self, nome: str, x: float, y: float, z: float, comprido: float, deitado: bool
    ) -> None:
        """Puxador centrado em (x, z) na face ``y`` da frente, no estilo escolhido: barra
        (metal), botão, perfil de alumínio (longo e fino) ou cava (recorte escuro, sem
        puxador saliente)."""
        estilo = self.m.puxador or "barra"
        if estilo == "botao":
            self.p(nome, x - 14, y, z - 14, x + 14, y + 22, z + 14, self.metal, chanfro=12)
            return
        if estilo == "cava":
            c, e, mat, sai = comprido * 1.4, 12.0, self.sombra, 1.0
        elif estilo == "perfil":
            c, e, mat, sai = comprido * 1.6, 10.0, self.metal, 12.0
        else:
            c, e, mat, sai = comprido, 16.0, self.metal, 25.0
        if deitado:
            self.p(nome, x - c / 2, y, z - e / 2, x + c / 2, y + sai, z + e / 2, mat)
        else:
            self.p(nome, x - e / 2, y, z - c / 2, x + e / 2, y + sai, z + c / 2, mat)

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

    def assento_l(self) -> None:
        """Sofá de canto: trecho das costas (largura toda) e trecho do braço do L, que vem
        para a frente do lado ``lado_l`` (esquerda de quem olha de frente = +x). Encosto
        nas costas e na lateral de fora do braço; braços nas duas pontas; almofadas de
        assento e de costas nos dois trechos (o canto fica com o trecho das costas)."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        b = geometria.braco_l(self.m)
        enc, braco = min(200.0, b / 6), min(150.0, w / 4, d / 4)
        assento = min(450.0, self.h * 0.55)
        pe, alt_braco = 100.0, base + min(650.0, self.h * 0.75)
        s = -1.0 if self.m.lado_l == "direita" else 1.0

        def q(nome: str, x0: float, y0: float, z0: float, x1: float, y1: float, z1: float,
              material: str | None = None, chanfro: float = 0.0) -> None:  # fmt: skip
            xa, xb = sorted((x0 * s, x1 * s))
            self.p(nome, xa, y0, z0, xb, y1, z1, material, chanfro)

        r = 60.0  # recuo dos pés
        pes = [(-w + r, -d + r), (w - r, -d + r), (w - r, d - r), (w - b + r, d - r),
               (w - b + r, -d + b - r), (-w + r, -d + b - r)]  # fmt: skip
        self.pes(pe, pontos=[(x * s, y) for x, y in pes])
        # estrutura: os dois trechos
        q("base", -w, -d, base + pe, w, -d + b, base + assento - 120, chanfro=20)
        q("base-l", w - b, -d + b, base + pe, w, d, base + assento - 120, chanfro=20)
        q("encosto", -w, -d, base + pe, w, -d + enc, topo, chanfro=40)
        q("encosto-l", w - enc, -d + enc, base + pe, w, d - braco, topo, chanfro=40)
        q("braco-e", -w, -d + enc, base + pe, -w + braco, -d + b, alt_braco, chanfro=45)
        q("braco-d", w - b, d - braco, base + pe, w, d, alt_braco, chanfro=45)
        # almofadas do trecho das costas (com o canto) e do trecho do braço
        costas = (-w + braco, w - enc)
        lado = (-d + b, d - braco)
        fundo = 170.0
        for i, (x0, x1) in enumerate(_divide(*costas)):
            q(f"almofada{i}", x0, -d + enc, base + assento - 120, x1, -d + b - 10,
              base + assento, chanfro=55)  # fmt: skip
            x1e = min(x1, w - enc - fundo)
            if x1e - x0 > 150:
                q(f"encosto{i}", x0 + 10, -d + enc, base + assento, x1e - 10, -d + enc + fundo,
                  topo - 50, chanfro=70)  # fmt: skip
        n = len(_divide(*costas))
        q(f"encosto{n}", w - enc - fundo, -d + enc, base + assento, w - enc, -d + b,
          topo - 50, chanfro=70)  # fmt: skip
        for j, (y0, y1) in enumerate(_divide(*lado)):
            k = n + 1 + j
            q(f"almofada{k}", w - b + 10, y0 + 10, base + assento - 120, w - enc, y1,
              base + assento, chanfro=55)  # fmt: skip
            q(f"encosto{k}", w - enc - fundo, y0 + 10, base + assento, w - enc, y1 - 10,
              topo - 50, chanfro=70)  # fmt: skip

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
        estilo = self.m.pes or "quadrado"
        if estilo != "quadrado":
            self.pes(topo - 30 - base, lado=50, recuo=30)
            return
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
        correr = self.m.portas == "correr"
        # de correr, a folha de trás fica na frente do corpo (1 mm de folga): com a face no
        # mesmo plano da frente do corpo ela "piscava" no 3D quando tinha outra cor
        self.p("corpo", -w, -d, base + r, w, d - (41 if correr else 20), topo, chanfro=4)
        alto, meio = base + r + fr, (base + r + topo) / 2
        if correr:  # duas folhas, uma na frente da outra
            self.p("folha0", -w, d - 40, alto, fr, d - 20, topo - fr, chanfro=3)
            self.p("folha1", -fr, d - 20, alto, w, d, topo - fr, chanfro=3)
            for i, x in enumerate((-w + 60, w - 75)):
                y = d - 40 if i == 0 else d - 20
                self.puxador(f"puxador{i}", x + 7.5, y + 20, meio, 500, deitado=False)
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
            self.puxador(f"puxador{i}", x + 7.5, d, meio, 300, deitado=False)

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
            self.puxador(f"puxador{i}", 0, d, z0 + alt / 2, 120, deitado=True)

    def pia(self) -> None:
        """Gabinete com portas, bancada de pedra, cuba embutida e torneira atrás dela."""
        w, d, base, topo, r, fr = self.w, self.d, self.base, self.topo, self.RODAPE, self.FRESTA
        tampo = 30.0
        self.p("rodape", -w + 40, -d, base, w - 40, d - 60, base + r, self.sombra)
        self.p("corpo", -w, -d, base + r, w, d - 40, topo - tampo, chanfro=4)
        n = max(1, round(2 * w / 450))
        larg = 2 * w / n
        alto, baixo = topo - tampo - fr, base + r + fr
        for i in range(n):
            x0 = -w + i * larg
            self.p(f"folha{i}", x0 + fr / 2, d - 40, baixo, x0 + larg - fr / 2, d - 20, alto,
                   chanfro=3)  # fmt: skip
            x = x0 + larg - 50 if i % 2 == 0 else x0 + 35
            self.puxador(f"puxador{i}", x + 7.5, d - 20, alto - 125, 150, deitado=False)
        pedra = self._mat("pedra", rugosidade=0.25)
        self.p("bancada", -w, -d, topo - tampo, w, d + 20, topo, pedra, chanfro=3)
        cw, cd = min(250.0, w * 0.4), min(200.0, d * 0.4)
        inox = self._mat("inox", rugosidade=0.25, metal=True)
        self.p("cuba", -cw, -cd, topo - 2, cw, cd, topo + 1, inox, chanfro=8)
        ty = -cd - min(70.0, d - cd - 15)
        self.p("torneira0", -18, ty - 18, topo, 18, ty + 18, topo + 260, inox, chanfro=8)
        self.p("torneira1", -12, ty, topo + 220, 12, ty + 170, topo + 250, inox, chanfro=6)

    def fogao(self) -> None:
        """Fogão de piso (forno com porta de vidro) ou cooktop na bancada; bocas em cima."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        inox, preto = self._mat("inox", rugosidade=0.25, metal=True), self._mat("vidro_preto")
        cooktop = eh_cooktop(self.m)
        if cooktop:
            self.p("tampo", -w, -d, base, w, d, topo, preto, chanfro=6)
        else:
            self.p("corpo", -w, -d, base + 20, w, d - 20, topo - 30, inox, chanfro=6)
            self.p("tampo", -w, -d, topo - 30, w, d, topo, preto, chanfro=4)
            forno_alto = base + min(self.h - 200, 650.0)
            self.p("folha0", -w + 40, d - 20, base + 120, w - 40, d, forno_alto, preto, chanfro=6)
            self.p("puxador0", -w + 80, d, forno_alto - 60, w - 80, d + 30, forno_alto - 40,
                   self.metal)  # fmt: skip
        n = 3 if w >= 350 else 2
        lado = min(2 * w / n - 80, d - 60, 200.0)
        for i in range(n):
            for j, y in enumerate((-d / 2, d / 2)):
                cx = -w + (2 * i + 1) * w / n
                self.p(f"boca{2 * i + j}", cx - lado / 2, y - lado / 2, topo, cx + lado / 2,
                       y + lado / 2, topo + 25, self.sombra, chanfro=lado / 2 - 1)  # fmt: skip

    def vaso(self) -> None:
        """Louça: pé, bacia, assento com tampa e caixa acoplada (ou só a bacia, suspenso)."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        suspenso = self.h < ALTURA_MIN_CAIXA
        caixa = 0.0 if suspenso else min(180.0, d * 0.3)
        bacia = base + (380.0 if not suspenso else self.h - 40)
        if not suspenso:
            self.p("pe", -w * 0.55, -d + caixa, base, w * 0.55, d - 120, bacia - 120, chanfro=60)
        else:
            self.p("pe", -w, -d, bacia - 300, w, -d + 120, bacia - 40, chanfro=40)
        self.p("bacia", -w, -d + caixa, bacia - 120 if not suspenso else bacia - 300, w, d,
               bacia, chanfro=min(w, 120.0))  # fmt: skip
        self.p("assento", -w, -d + caixa + 30, bacia, w, d, bacia + 40, chanfro=min(w, 110.0))
        if not suspenso:
            self.p("caixa", -w, -d, base + 380, w, -d + caixa, topo, chanfro=30)
            self.p("botao", -30, -d + caixa / 2 - 30, topo, 30, -d + caixa / 2 + 30, topo + 8,
                   self.metal, chanfro=20)  # fmt: skip

    def box(self) -> None:
        """Piso do box rebaixado, duas folhas de vidro de correr na frente e perfis."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        vidro = self.cena.material("vidro", CORES_PADRAO["vidro"], vidro=True)
        self.p("corpo", -w, -d, base, w, d - 60, base + 8)  # piso do box, sobre o piso
        self.p("vidro0", -w + 20, d - 40, base + 20, w * 0.1, d - 30, topo - 40, vidro)
        self.p("vidro1", -w * 0.1, d - 60, base + 20, w - 20, d - 50, topo - 40, vidro)
        self.p("perfil0", -w, d - 70, topo - 40, w, d - 20, topo, self.metal)
        self.p("perfil1", -w, d - 70, base, w, d - 20, base + 20, self.metal)
        self.p("perfil2", -w, d - 70, base, -w + 20, d - 20, topo, self.metal)
        self.p("perfil3", w - 20, d - 70, base, w, d - 20, topo, self.metal)

    def beliche(self) -> None:
        """Quatro postes, duas camas (embaixo e em cima, com grade), colchões e escada na
        frente, do lado direito."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        colchao = self._mat("colchao", rugosidade=0.9, textura="tecido")
        edredom = self._mat("edredom", rugosidade=0.95, textura="tecido")
        p = 60.0
        for i, (x, y) in enumerate(((-w, -d), (w - p, -d), (-w, d - p), (w - p, d - p))):
            self.p(f"poste{i}", x, y, base, x + p, y + p, topo, chanfro=6)
        for k, z in enumerate((base + 300, base + 1150)):
            self.p(f"estrado{k}", -w + p, -d + p, z - 60, w - p, d - p, z, chanfro=4)
            self.p(f"colchao{k}", -w + p + 10, -d + p + 10, z, w - p - 10, d - p - 10, z + 160,
                   colchao, 40)  # fmt: skip
            self.p(f"edredom{k}", -w + p + 5, -d + (d * 0.5), z + 120, w - p - 5, d - p - 5,
                   z + 175, edredom, 40)  # fmt: skip
        # grade de proteção em cima (fundo e frente até a escada)
        self.p("grade0", -w + p, -d, base + 1350, w - p, -d + 30, base + 1450, chanfro=4)
        self.p("grade1", -w + p, d - 30, base + 1350, w - p - 420, d, base + 1450, chanfro=4)
        # escada: dois banzos e degraus na frente, junto ao poste da direita
        ex0, ex1 = w - p - 400, w - p - 20
        for j, x in enumerate((ex0, ex1)):
            self.p(f"banzo{j}", x - 20, d, base, x + 20, d + 40, base + 1450, chanfro=4)
        for k in range(4):
            z = base + 300 + k * 280
            self.p(f"degrau{k}", ex0, d + 5, z, ex1, d + 35, z + 30, chanfro=4)

    def cadeira_giratoria(self) -> None:
        """Base em estrela (cinco patas como cruz + diagonal), coluna, assento e encosto."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        preto = self._mat("sombra", rugosidade=0.6)
        r = min(w, d) * 0.9
        self.p("pata0", -r, -30, base + 40, r, 30, base + 80, preto, chanfro=10)
        self.p("pata1", -30, -r, base + 40, 30, r, base + 80, preto, chanfro=10)
        for i, (x, y) in enumerate(((-r, 0), (r, 0), (0, -r), (0, r))):
            self.p(
                f"rodizio{i}", x - 30, y - 30, base, x + 30, y + 30, base + 50, preto, chanfro=25
            )
        self.p("coluna", -30, -30, base + 80, 30, 30, base + 430, self.metal, chanfro=10)
        self.p("assento", -w * 0.8, -d * 0.75, base + 430, w * 0.8, d * 0.8, base + 510, chanfro=35)
        self.p("encosto", -w * 0.7, -d * 0.9, base + 560, w * 0.7, -d * 0.72, topo, chanfro=40)
        # haste que prende o encosto no assento (sem ela o encosto fica solto no ar)
        self.p("coluna1", -30, -d * 0.86, base + 470, 30, -d * 0.76, base + 600, self.metal)

    def monitor(self) -> None:
        """Monitor: tela fina (moldura com o vidro na frente) sobre haste e pé achatado."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        tela = self._mat("tela", rugosidade=0.08)
        baixo = base + max(60.0, self.h * 0.22)  # borda de baixo da tela
        self.p("suporte0", -w * 0.35, -d, base, w * 0.35, d * 0.7, base + 12, chanfro=6)
        self.p("suporte1", -25, -50, base + 12, 25, -20, baixo + 60, chanfro=8)
        self.p("moldura", -w, -20, baixo, w, 10, topo, chanfro=6)
        self.p("tela", -w + 8, 10, baixo + 8, w - 8, 12, topo - 8, tela)

    def notebook(self) -> None:
        """Notebook aberto: base com teclado e a tampa em pé atrás, com a tela para a frente."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        tela = self._mat("tela", rugosidade=0.08)
        escuro = self._mat("sombra", rugosidade=0.6)
        self.p("corpo", -w, -d + 10, base, w, d, base + 18, chanfro=6)
        fundo = -d + 35 + (2 * d) * 0.45
        self.p("teclas", -w + 25, -d + 35, base + 18, w - 25, fundo, base + 20, escuro)
        self.p("tampa", -w, -d, base + 10, w, -d + 8, topo, chanfro=4)
        self.p("tela", -w + 12, -d + 8, base + 30, w - 12, -d + 10, topo - 12, tela)

    def gabinete(self) -> None:
        """Gabinete (torre): caixa com painel da frente escuro, botão e pezinhos."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        frente = self._mat("vidro_preto", rugosidade=0.25)
        self.p("rodape", -w + 15, -d + 20, base, w - 15, d - 20, base + 20, self.sombra)
        self.p("corpo", -w, -d, base + 20, w, d - 8, topo, chanfro=6)
        self.p("frente", -w + 6, d - 8, base + 30, w - 6, d, topo - 10, frente, chanfro=4)
        self.p("botao", -12, d, topo - 50, 12, d + 4, topo - 26, self.metal, chanfro=10)

    def teclado(self) -> None:
        """Teclado (base e bloco de teclas) e o mouse à direita."""
        w, d, base = self.w, self.d, self.base
        escuro = self._mat("sombra", rugosidade=0.6)
        fim = w - 110  # o mouse fica nos últimos 11 cm
        self.p("corpo", -w, -d, base, fim, d, base + 20, chanfro=6)
        self.p("teclas", -w + 12, -d + 12, base + 20, fim - 12, d - 12, base + 28, escuro)
        meio = min(55.0, d - 5)
        self.p("mouse", w - 75, -meio, base, w - 10, meio, base + 35, chanfro=25)

    def maquina(self) -> None:
        """Máquina de lavar: corpo, painel de comandos em cima e porta redonda na frente
        (ou tampa em cima, nas de abertura superior)."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        vidro = self.cena.material("vidro", CORES_PADRAO["vidro"], vidro=True)
        self.p("corpo", -w, -d, base + 20, w, d - 10, topo, chanfro=12)
        self.p("rodape", -w + 30, -d + 30, base, w - 30, d - 40, base + 20, self.sombra)
        if self.h > 950:  # abertura em cima: tampa e painel atrás
            self.p("porta0", -w + 40, -d + 120, topo, w - 40, d - 40, topo + 12, vidro, chanfro=10)
            self.p("painel", -w, -d, topo, w, -d + 110, topo + 120, chanfro=10)
            return
        self.p("painel", -w + 20, d - 10, topo - 140, w - 20, d, topo - 20, self.sombra, chanfro=4)
        lado = min(2 * w, self.h) * 0.55
        meio = base + 20 + (self.h - 160) / 2
        self.p("porta0", -lado / 2, d - 10, meio - lado / 2, lado / 2, d + 25, meio + lado / 2,
               vidro, chanfro=lado / 2 - 2)  # fmt: skip

    def geladeira(self) -> None:
        """Duplex: freezer em cima (1/3) e geladeira embaixo, puxadores verticais."""
        w, d, base, topo, fr = self.w, self.d, self.base, self.topo, self.FRESTA
        self.p("rodape", -w + 30, -d, base, w - 30, d - 40, base + 40, self.sombra)
        self.p("corpo", -w, -d, base + 40, w, d - 40, topo, chanfro=20)
        corte = topo - (topo - base) / 3
        for i, (z0, z1) in enumerate(((base + 40 + fr, corte - fr), (corte + fr, topo - fr))):
            self.p(f"folha{i}", -w + fr, d - 40, z0, w - fr, d, z1, chanfro=12)
            meio = (z0 + z1) / 2
            alto = min(300.0, (z1 - z0) / 2 - 40)
            self.p(f"puxador{i}", w - 70, d, meio - alto / 2, w - 50, d + 35, meio + alto / 2,
                   self.metal)  # fmt: skip

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

    def bancada(self) -> None:
        """Bancada planejada: tampo (reto, ou os dois trechos do L), pernas/painéis e os
        módulos montados como planejados, trazidos para o referencial da bancada."""
        b = self.m.bancada
        assert b is not None
        base, topo = self.base, self.topo
        e = float(b.tampo.espessura.valor)
        try:
            calc = bancada.calcular(self.m)
        except planejado.ConstrucaoInvalidaError:  # não fecha: só o tampo (a checagem avisa)
            self.p("tampo", -self.w, -self.d, topo - e, self.w, self.d, topo, chanfro=3)
            return
        for t in calc.trechos:
            # trecho do braço vai só até a frente do trecho das costas (sem sobrepor o canto)
            x0, y0 = t.ponto(0, 0)
            x1, y1 = t.ponto(t.comprimento, t.profundidade)
            nome = "tampo" if t.nome == "costas" else "tampo-l"
            self.p(nome, min(x0, x1), min(y0, y1), topo - e, max(x0, x1), max(y0, y1), topo,
                   chanfro=3)  # fmt: skip
        mat_perna = self.metal if b.pernas == "metal" else self.mat
        for i, p in enumerate(calc.pernas):
            t = next(t for t in calc.trechos if t.nome == p.trecho)
            u, v = t.uv(p.x, p.y)
            if p.painel:
                cantos = (t.ponto(u - e / 2, v - p.comprimento / 2),
                          t.ponto(u + e / 2, v + p.comprimento / 2))  # fmt: skip
                material, chanfro = self.mat, 2.0
            else:
                meia = bancada.PERNA / 2
                cantos = (t.ponto(u - meia, v - meia), t.ponto(u + meia, v + meia))
                material, chanfro = mat_perna, (8.0 if b.pernas == "madeira" else 0.0)
            (xa, ya), (xb, yb) = cantos
            self.p(f"{'painel' if p.painel else 'perna'}{i}", min(xa, xb), min(ya, yb), base,
                   max(xa, xb), max(ya, yb), topo - e, material, chanfro)  # fmt: skip
        contagem: dict[str, int] = {}
        for mod in calc.modulos:
            f = _Feitio(self.cena, mod.movel, self.mat)
            f.base = base
            f.topo = base + f.h
            f.planejado()
            cos, sen = _COS_SEN[mod.rotacao_local]
            cx, cy = mod.centro_local
            for peca in f.pecas:
                ax0, ay0, z0, ax1, ay1, z1 = peca.caixa
                xs, ys = [], []
                for x, y in ((ax0, ay0), (ax1, ay1)):
                    xs.append(cx + x * cos - y * sen)
                    ys.append(cy + x * sen + y * cos)
                raiz = peca.nome.rstrip("0123456789")
                n = contagem.get(raiz, 0)
                contagem[raiz] = n + 1
                self.pecas.append(
                    Peca(
                        f"{raiz}{n}" if raiz != peca.nome or n else peca.nome,
                        (min(xs), min(ys), z0, max(xs), max(ys), z1),
                        peca.material,
                        peca.chanfro,
                    )
                )

    def planejado(self) -> None:
        """Móvel montado por dentro: caixa, portas, frentes de gaveta (com puxador) e, nos
        vãos sem porta, o fundo escuro dos nichos e as prateleiras à vista.

        A vista de frente do cálculo tem ``u`` da esquerda para a direita **de quem olha
        de frente**; no referencial do móvel a frente é +y, então a esquerda de quem olha
        é +x: ``x = w - u`` (sem isso o móvel sairia espelhado em relação ao desenho)."""
        w, d, base, topo = self.w, self.d, self.base, self.topo
        self.p("caixa", -w, -d, base, w, d - 20, topo, chanfro=4)
        try:
            calc = planejado.calcular(self.m)
        except planejado.ConstrucaoInvalidaError:
            calc = None
        if calc is None:
            self.p("frente", -w, d - 20, base, w, d, topo, chanfro=3)
            return

        def faixa(u: float, largura: float) -> tuple[float, float]:
            """Trecho [u, u + largura] da vista de frente → (x0, x1) do móvel."""
            return w - u - largura, w - u

        portas = [r for r in calc.layout if r.tipo == "porta"]

        def coberto(r: Any) -> bool:  # atrás de uma porta (fica dentro da folha)
            cx, cy = r.x + r.largura / 2, r.y + r.altura / 2
            return any(p.x <= cx <= p.x + p.largura and p.y <= cy <= p.y + p.altura for p in portas)

        n_pux = 0

        def puxador(u: float, z: float, comprido: float, deitado: bool) -> None:
            nonlocal n_pux
            self.puxador(f"puxador{n_pux}", w - u, d, z, comprido, deitado)
            n_pux += 1

        for i, r in enumerate(portas):  # folhas um pouco afastadas: mostram as divisões
            x0, x1 = faixa(r.x + 2, r.largura - 4)
            z0, z1 = base + r.y + 2, base + r.y + r.altura - 2
            self.p(f"porta{i}", x0, d - 20, z0, x1, d, z1, chanfro=3)
            # pares abrem do meio: puxador do lado de dentro do par (de quem olha)
            u = r.x + r.largura - 50 if i % 2 == 0 else r.x + 50
            puxador(u, (z0 + z1) / 2, min(240.0, (z1 - z0) * 0.4), deitado=False)
            # o visor esconde junto com as folhas (editar em detalhe, "esconder as portas")
            self.pecas[-1] = replace(self.pecas[-1], extras={"da_porta": "1"})
        # o que fica atrás de uma porta também sai, por dentro do volume da folha: com a
        # porta à vista não aparece; o editar em detalhe esconde as portas para ver
        atras = {"atras_da_porta": "1"}
        for i, r in enumerate(x for x in calc.layout if x.tipo == "gaveta"):
            x0, x1 = faixa(r.x + 2, r.largura - 4)
            z0, z1 = base + r.y + 2, base + r.y + r.altura - 2
            if coberto(r):  # gaveta interna: frente mais fina, sem puxador
                self.p(f"gaveta{i}", x0, d - 20, z0, x1, d - 4, z1, chanfro=3, extras=atras)
                continue
            self.p(f"gaveta{i}", x0, d - 20, z0, x1, d, z1, chanfro=3)
            puxador(r.x + r.largura / 2, z1 - min(60.0, (z1 - z0) / 3),
                    min(160.0, (x1 - x0) * 0.4), deitado=True)  # fmt: skip
        for i, r in enumerate(x for x in calc.layout if x.tipo in ("nicho", "cabideiro")):
            # fundo escuro 1 mm à frente da caixa: o nicho aberto "fundo" na imagem
            x0, x1 = faixa(r.x, r.largura)
            z0 = base + r.y
            extras = atras if coberto(r) else {}
            self.p(f"nicho{i}", x0, d - 20, z0, x1, d - 19, z0 + r.altura, self.sombra,
                   extras=extras)  # fmt: skip
        for i, r in enumerate(x for x in calc.layout if x.tipo == "prateleira"):
            x0, x1 = faixa(r.x, r.largura)
            z0 = base + r.y
            extras = atras if coberto(r) else {}
            self.p(f"prateleira{i}", x0, d - 19, z0, x1, d - 4, z0 + r.altura, extras=extras)


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
    cena.pilares()
    cena.paredes()
    cena.escadas_()
    cena.vigas_e_lajes()
    cena.rodape()
    cena.moveis_()
    cena.luminarias()
    estimadas = carregado.estimadas(comodo)
    cameras = cena.cameras(vistas)
    for cam in cameras:
        if cam["nome"] == "superior":
            cena.cortar_paredes_da_frente(
                cam, [v["nome"] for v in cameras if v["nome"] != "superior"]
            )
    return {
        "versao": VERSAO_CENA,
        "comodo": comodo,
        "variacao": variacao or "base",
        "prismas": cena.prismas,
        "caixas": cena.caixas,
        "materiais": cena.materiais,
        "cameras": cameras,
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


# ---------------------------------------------------------------- pavimento inteiro

VISTAS_PAVIMENTO: tuple[str, ...] = ("perspectiva", "superior")
"""Vistas do pavimento: de cima (planta 3D) e em perspectiva aérea, as duas sem teto."""
ARQUIVO_PAVIMENTO = "_geral"
"""Pasta das saídas do pavimento (CLAUDE.md §5.5): ``out/<projeto>/<pavimento>/_geral/``."""


def _pavimento(carregado: ProjetoCarregado, pavimento: str) -> Pavimento:
    pav = next((p for p in carregado.projeto.pavimentos if p.id == pavimento), None)
    if pav is None:
        disponiveis = ", ".join(p.id for p in carregado.projeto.pavimentos) or "nenhum"
        raise KeyError(f"pavimento '{pavimento}' não existe no projeto ({disponiveis})")
    return pav


def _cameras_pavimento(contorno: BaseGeometry, proporcao: float) -> dict[str, dict[str, Any]]:
    """``proporcao``: largura / altura do quadro (a escala ortográfica vale na largura)."""
    x0, y0, x1, y1 = contorno.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    maior = max(x1 - x0, y1 - y0)
    # cabe na largura e na altura, com folga para a faixa do aviso no rodapé
    escala = max((x1 - x0) * 1.12, (y1 - y0) * 1.25 * proporcao)
    return {
        # vista aérea pelo canto de baixo à esquerda da planta, como uma maquete na mesa
        "perspectiva": {
            "nome": "perspectiva",
            "titulo": "Perspectiva aérea",
            "tipo": "perspectiva",
            "posicao": [
                round(cx - maior * 0.6, 1),
                round(cy - maior * 1.1, 1),
                round(maior * 1.2, 1),
            ],
            "alvo": [round(cx, 1), round(cy, 1), 0],
            "lente": 24,
        },
        "superior": {
            "nome": "superior",
            "titulo": "De cima",
            "tipo": "ortografica",
            "posicao": [round(cx, 1), round(cy - 1, 1), round(maior * 2.2, 1)],
            "alvo": [round(cx, 1), round(cy, 1), 0],
            "escala": round(escala, 1),
        },
    }


def montar_cena_pavimento(
    carregado: ProjetoCarregado,
    pavimento: str,
    largura: int = 1600,
    altura: int = 1000,
    amostras: int = 96,
    vistas: tuple[str, ...] = VISTAS_PAVIMENTO,
) -> dict[str, Any]:
    """Cena do pavimento inteiro em JSON, pronta para o ``bpy_cena.py``.

    Todos os cômodos com piso, rodapé, móveis e luminárias; cada parede sai uma vez
    só (a do vizinho não se repete); teto e luminárias somem nas duas vistas (corte
    no teto, CLAUDE.md §5.6) e vão marcados no .glb para o visor esconder. Cores
    padrão: as variações são por cômodo.
    """
    pav = _pavimento(carregado, pavimento)
    if not pav.comodos:
        raise ValueError(f"pavimento '{pavimento}' não tem cômodos")
    prismas: list[dict[str, Any]] = []
    caixas: list[dict[str, Any]] = []
    materiais: dict[str, dict[str, Any]] = {}
    ocupado: BaseGeometry = Polygon()
    feitas: set[str] = set()
    luzes: list[dict[str, Any]] = []
    cenas: list[_Cena] = []
    for comodo in pav.comodos:
        cena = _Cena(carregado, pav, comodo, None, no_pavimento=True)
        # tudo no mesmo acervo: listas, materiais e paredes já feitas
        cena.prismas, cena.caixas, cena.materiais = prismas, caixas, materiais
        cena.ocupado, cena.paredes_feitas = ocupado, feitas
        cena.piso_teto()
        if not cenas:
            cena.pilares()  # uma vez só, para o pavimento inteiro
        cena.paredes()
        ocupado = cena.ocupado
        cena.rodape()
        cena.moveis_()
        cena.luminarias()
        luzes.append(cena.luzes()[0])  # a luz de teto de cada cômodo
        cenas.append(cena)
    soltas = [p.id for p in pav.paredes if p.id not in feitas]
    if soltas:  # paredes que nenhum cômodo usa (muro, mureta): saem também
        cenas[0].ocupado = ocupado
        cenas[0].paredes(soltas)
    cenas[0].escadas_()
    cenas[0].vigas_e_lajes()
    luzes.append({"tipo": "sol", "direcao": [0.45, 0.35, -0.82], "energia": 2.5})
    disponiveis = _cameras_pavimento(
        unary_union([geometria.corpo(p) for p in pav.paredes if geometria.comprimento(p) > 0]),
        largura / altura,
    )
    fora = [v for v in vistas if v not in disponiveis]
    if fora:
        raise KeyError(
            f"vista(s) {', '.join(fora)} não existem no pavimento ({', '.join(disponiveis)})"
        )
    estimadas = carregado.estimadas_pavimento(pavimento)
    return {
        "versao": VERSAO_CENA,
        "comodo": ARQUIVO_PAVIMENTO,
        "pavimento": pavimento,
        "modelo": pavimento,
        "variacao": "base",
        "prismas": prismas,
        "caixas": caixas,
        "materiais": materiais,
        "cameras": [disponiveis[v] for v in vistas],
        "luzes": luzes,
        "aviso": f"{AVISO_OBRA} · {len(estimadas)} medida(s) estimada(s)" if estimadas else None,
        "saida": {"largura": largura, "altura": altura, "amostras": amostras},
    }
