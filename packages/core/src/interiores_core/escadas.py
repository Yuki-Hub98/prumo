"""Conta da escada: quantos degraus, espelho, piso, onde fica cada degrau e o furo na laje.

Referencial local da escada (mm): ``u`` no sentido da subida do 1º lance, ``v`` à
esquerda de quem sobe; a origem é o meio da borda do 1º degrau. ``gira="direita"``
espelha ``v``. No caracol a origem é o centro e o 1º degrau começa no ângulo
``direcao``.

Regras de bolso (padrões; as checagens usam os limites do ``regras.toml``):
espelho até 185 mm; piso pela fórmula de Blondel (2 × espelho + piso ≈ 635 mm),
nunca menos de 250 mm; altura livre de 2,10 m embaixo da laje.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely import Polygon
from shapely.affinity import rotate, translate
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from interiores_core.modelo import Escada, Laje, Pavimento

ESPELHO_ALVO = 175.0
"""Espelho que a conta procura (mm); nunca passa de ``ESPELHO_MAX``."""
ESPELHO_MAX = 185.0
BLONDEL = 635.0
"""2 × espelho + piso (mm): passo confortável."""
PISO_MIN = 250.0
PISO_MAX = 320.0
ALTURA_LIVRE = 2100.0
"""Altura livre embaixo da laje (mm): onde for menos, a laje é furada."""
LAJE_PADRAO = 120.0
"""Espessura da laje quando o pavimento não tem laje lançada (desnível estimado)."""
FOLGA_U = 100.0
"""Escada em U: espaço entre os dois lances (parede ou vão central)."""
NUCLEO = 100.0
"""Caracol: raio do núcleo (coluna central)."""
ARCO = 6
"""Lados por degrau no desenho do caracol."""


@dataclass(frozen=True)
class Degrau:
    numero: int
    """1 = o primeiro a pisar."""
    poligono: Polygon
    """Projeção na planta (coordenadas do pavimento)."""
    z: float
    """Altura do topo (mm a partir do piso do pavimento)."""
    patamar: bool = False


@dataclass(frozen=True)
class EscadaCalculada:
    desnivel: float
    espelhos: int
    espelho: float
    piso: float
    degraus: list[Degrau]
    caminho: list[tuple[float, float]]
    """Linha de subida (para a seta da planta), do pé à chegada."""
    nucleo: Polygon | None = None
    giro: float | None = None
    """Caracol: quanto a escada gira (graus)."""
    lances: tuple[int, ...] = field(default_factory=tuple)
    """Pisos de cada lance (sem o patamar)."""

    @property
    def blondel(self) -> float:
        return 2 * self.espelho + self.piso

    @property
    def contorno(self) -> Polygon:
        """Tudo que a escada ocupa no piso."""
        partes = [d.poligono for d in self.degraus] + ([self.nucleo] if self.nucleo else [])
        return _juntar(unary_union(partes))


def desnivel(pav: Pavimento, e: Escada) -> float:
    """Altura a vencer: a informada, ou pé-direito + espessura da laje do pavimento."""
    if e.desnivel is not None:
        return float(e.desnivel.valor)
    laje = next((x for x in pav.estrutura if isinstance(x, Laje)), None)
    return float(pav.pe_direito.valor) + (laje.espessura.valor if laje else LAJE_PADRAO)


def espelhos_e_piso(h: float, piso: float | None = None) -> tuple[int, float, float]:
    """Número de espelhos, espelho e piso para vencer ``h`` (piso pela fórmula de Blondel,
    em passos de 5 mm, se não vier pronto)."""
    n = max(2, round(h / ESPELHO_ALVO))
    if h / n > ESPELHO_MAX:
        n += 1
    espelho = h / n
    if piso is None:
        piso = min(PISO_MAX, max(PISO_MIN, round((BLONDEL - 2 * espelho) / 5) * 5))
    return n, espelho, piso


def calcular(pav: Pavimento, e: Escada) -> EscadaCalculada:
    """Degraus, patamar e linha de subida da escada, já no lugar do pavimento."""
    h = desnivel(pav, e)
    n, espelho, piso = espelhos_e_piso(h, float(e.piso.valor) if e.piso else None)
    w = float(e.largura.valor)
    s = 1.0 if e.gira == "esquerda" else -1.0
    pisos = n - 1  # o último espelho chega no piso de cima

    def ret(u0: float, u1: float, v0: float, v1: float) -> Polygon:
        return Polygon([(u0, s * v0), (u1, s * v0), (u1, s * v1), (u0, s * v1)])

    locais: list[tuple[Polygon, bool]] = []
    caminho: list[tuple[float, float]] = []
    nucleo: Polygon | None = None
    giro: float | None = None
    lances: tuple[int, ...]
    if e.forma == "reta" or (e.forma in ("L", "U") and pisos < 3):
        locais = [(ret(i * piso, (i + 1) * piso, -w / 2, w / 2), False) for i in range(pisos)]
        caminho = [(0.0, 0.0), (pisos * piso, 0.0)]
        lances = (pisos,)
    elif e.forma in ("L", "U"):
        # pisos = k1 (1º lance) + patamar + k2 (2º lance)
        k1 = e.degraus_primeiro_lance or (pisos - 1) // 2
        k1 = min(max(1, k1), pisos - 2)
        k2 = pisos - 1 - k1
        a = k1 * piso  # onde começa o patamar
        locais = [(ret(i * piso, (i + 1) * piso, -w / 2, w / 2), False) for i in range(k1)]
        if e.forma == "L":
            locais.append((ret(a, a + w, -w / 2, w / 2), True))
            locais += [
                (ret(a, a + w, w / 2 + j * piso, w / 2 + (j + 1) * piso), False) for j in range(k2)
            ]
            meio = a + w / 2
            caminho = [(0.0, 0.0), (meio, 0.0), (meio, s * (w / 2 + k2 * piso))]
        else:
            v2 = w / 2 + FOLGA_U + w / 2  # eixo do 2º lance
            locais.append((ret(a, a + w, -w / 2, v2 + w / 2), True))
            locais += [
                (ret(a - (j + 1) * piso, a - j * piso, v2 - w / 2, v2 + w / 2), False)
                for j in range(k2)
            ]
            meio = a + w / 2
            caminho = [(0.0, 0.0), (meio, 0.0), (meio, s * v2), (a - k2 * piso, s * v2)]
        lances = (k1, k2)
    else:  # caracol / leque, em volta do centro
        r0, r1 = NUCLEO, NUCLEO + w
        rl = (r0 + r1) / 2  # linha de piso
        passo = piso / rl  # rad por degrau na linha de piso
        giro = math.degrees(passo * pisos)

        def setor(t0: float, t1: float) -> Polygon:
            ts = [t0 + (t1 - t0) * k / ARCO for k in range(ARCO + 1)]
            fora = [(r1 * math.cos(t), s * r1 * math.sin(t)) for t in ts]
            dentro = [(r0 * math.cos(t), s * r0 * math.sin(t)) for t in reversed(ts)]
            return Polygon(fora + dentro)

        locais = [(setor(i * passo, (i + 1) * passo), False) for i in range(pisos)]
        caminho = [
            (rl * math.cos(passo * k / 2), s * rl * math.sin(passo * k / 2))
            for k in range(0, 2 * pisos + 1)
        ]
        nucleo = Polygon(
            [(r0 * math.cos(t), r0 * math.sin(t)) for t in (k * math.pi / 8 for k in range(16))]
        )
        lances = (pisos,)

    def no_lugar(g: Polygon) -> Polygon:
        girado = rotate(g, e.direcao, origin=(0, 0))
        return translate(girado, e.inicio[0], e.inicio[1])

    # o patamar é um piso como os outros (só maior): o i-ésimo fica em (i + 1) espelhos
    degraus = [
        Degrau(i + 1, no_lugar(pol), (i + 1) * espelho, patamar)
        for i, (pol, patamar) in enumerate(locais)
    ]
    rad = math.radians(e.direcao)
    c, sn = math.cos(rad), math.sin(rad)
    caminho_global = [
        (e.inicio[0] + u * c - v * sn, e.inicio[1] + u * sn + v * c) for u, v in caminho
    ]
    return EscadaCalculada(
        desnivel=h,
        espelhos=n,
        espelho=espelho,
        piso=piso,
        degraus=degraus,
        caminho=caminho_global,
        nucleo=no_lugar(nucleo) if nucleo is not None else None,
        giro=giro,
        lances=lances,
    )


def furo(pav: Pavimento, e: Escada) -> Polygon | None:
    """Furo na laje do pavimento: em cima dos degraus onde a cabeça bateria (menos de
    ``ALTURA_LIVRE`` do degrau até o fundo da laje), até a chegada."""
    calc = calcular(pav, e)
    fundo = float(pav.pe_direito.valor)
    altos = [d.poligono for d in calc.degraus if fundo - d.z < ALTURA_LIVRE]
    if calc.nucleo is not None and altos:
        altos.append(calc.nucleo)
    if not altos:
        return None
    # fecha frestas estreitas (o vão entre os lances da U): ninguém deixa tira de laje ali
    juntos = unary_union(altos).buffer(FOLGA_U, join_style="mitre")
    return _juntar(juntos.buffer(-FOLGA_U, join_style="mitre"))


def _juntar(g: BaseGeometry) -> Polygon:
    """Um polígono só (degraus encostados viram uma peça; o maior pedaço, se separados)."""
    g = g.buffer(1, join_style="mitre").buffer(-1, join_style="mitre")
    if isinstance(g, Polygon):
        return g
    partes = [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
    return max(partes, key=lambda p: p.area)
