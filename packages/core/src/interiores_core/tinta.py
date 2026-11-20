"""Cálculo de tinta: áreas a pintar, litros e latas, por cor (CLAUDE.md §5.6, imóvel).

Paredes e teto em tinta látex; rodapé e folhas de porta em esmalte. As áreas saem da
geometria (face de cada parede voltada para o cômodo × altura, menos portas, janelas e a
faixa do rodapé) e as cores da variação escolhida em cada cômodo: parede de destaque é
outra cor, outra lata. Rendimento, demãos, perda e tamanhos de lata têm padrões típicos
de rótulo e podem ser trocados na seção ``[tinta]`` do ``regras.toml``.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from itertools import pairwise
from typing import Literal

from shapely import Polygon
from shapely.geometry.base import BaseGeometry

from interiores_core import geometria
from interiores_core.modelo import Comodo, CoresVariacao, Janela, Parede, Pavimento, Porta

Tinta = Literal["latex", "esmalte"]


@dataclass(frozen=True)
class Parametros:
    """Padrões típicos de rótulo (estimativa); trocáveis em ``[tinta]`` do regras.toml."""

    rendimento_latex: float = 10.0
    """m² por litro por demão (látex acrílico; rótulos dão de 8 a 12)."""
    demaos_latex: int = 2
    rendimento_esmalte: float = 8.0
    """m² por litro por demão (esmalte sintético/acrílico)."""
    demaos_esmalte: int = 2
    perda: float = 0.10
    """Fração a mais pela perda (rolo, bandeja, retoque)."""
    latas_latex: tuple[float, ...] = (18.0, 3.6, 0.9)
    latas_esmalte: tuple[float, ...] = (3.6, 0.9, 0.225)

    @classmethod
    def do_projeto(cls, regras: Mapping[str, object]) -> Parametros:
        secao = regras.get("tinta")
        if not isinstance(secao, Mapping):
            return cls()
        conhecidos = {k: v for k, v in secao.items() if k in cls.__dataclass_fields__}
        for k in ("latas_latex", "latas_esmalte"):
            if k in conhecidos:
                conhecidos[k] = tuple(float(x) for x in conhecidos[k])
        return replace(cls(), **conhecidos)


@dataclass(frozen=True)
class Superficie:
    comodo: str
    """Id do cômodo (portas: o cômodo para onde a folha abre)."""
    nome: str
    tinta: Tinta
    cor: str | None
    """Hex da variação; ``None`` = cor padrão do projeto."""
    area_m2: float


@dataclass(frozen=True)
class Grupo:
    """Uma tinta numa cor: o que comprar."""

    tinta: Tinta
    cor: str | None
    area_m2: float
    litros: float
    latas: dict[float, int]
    """Tamanho da lata (L) → quantidade."""


@dataclass
class Resultado:
    superficies: list[Superficie]
    grupos: list[Grupo]
    parametros: Parametros
    litros_por_superficie: list[float] = field(default_factory=list)


def litros(area_m2: float, tinta: Tinta, p: Parametros) -> float:
    """Litros para ``area_m2`` com as demãos, o rendimento e a perda."""
    rend, demaos = (
        (p.rendimento_latex, p.demaos_latex)
        if tinta == "latex"
        else (p.rendimento_esmalte, p.demaos_esmalte)
    )
    return area_m2 * demaos / rend * (1 + p.perda)


def latas(total: float, tamanhos: tuple[float, ...]) -> dict[float, int]:
    """Latas para ``total`` litros: as maiores primeiro e, no que sobra, a menor lata que
    cubra (ou uma da menor). Se as latas menores somam 75 % ou mais de uma maior, compra-se a
    maior (mais barata por litro e menos latas). Ex.: 15 L → 1 × 18; 20 L → 18 + 3,6."""
    if total <= 0:
        return {}
    ordem = sorted(tamanhos, reverse=True)
    resto = total
    conta: dict[float, int] = defaultdict(int)
    for t in ordem:
        n = math.floor(resto / t + 1e-9)
        if n:
            conta[t] += n
            resto -= n * t
    if resto > 1e-6:
        cobre = [t for t in sorted(tamanhos) if t >= resto]
        conta[cobre[0] if cobre else min(tamanhos)] += 1
    for i in range(len(ordem) - 1, 0, -1):  # das menores para as maiores
        maior = ordem[i - 1]
        menores = sum(conta.get(t, 0) * t for t in ordem[i:])
        if menores >= 0.75 * maior - 1e-9:
            for t in ordem[i:]:
                conta.pop(t, None)
            conta[maior] += 1
    return {t: n for t, n in sorted(conta.items(), reverse=True) if n}


def _maior(g: BaseGeometry | None) -> Polygon | None:
    if g is None or g.is_empty:
        return None
    if isinstance(g, Polygon):
        return g
    partes = [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
    return max(partes, key=lambda p: p.area) if partes else None


def _trecho(parede: Parede, p: tuple[float, float], q: tuple[float, float]) -> tuple[float, float]:
    """Trecho [s0, s1] da face p→q medido ao longo da parede, a partir do início dela."""
    u, _ = geometria.direcao(parede)
    x0, y0 = parede.inicio
    s = [(a - x0) * u[0] + (b - y0) * u[1] for a, b in (p, q)]
    return min(s), max(s)


def _sobreposto(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def superficies(
    pavimento: Pavimento, cores: Mapping[str, CoresVariacao | None] | None = None
) -> list[Superficie]:
    """O que pintar em cada cômodo do pavimento, com a cor da variação dele (``cores``:
    cômodo → cores da variação; sem ela, a cor padrão)."""
    cores = cores or {}
    rodape = float(pavimento.rodape.valor) if pavimento.rodape else 0.0
    saida: list[Superficie] = []
    for c in pavimento.comodos:
        saida += _do_comodo(pavimento, c, cores.get(c.id), rodape)
    for ab in pavimento.aberturas:
        if isinstance(ab, Porta) and ab.folha in ("giro", "correr", "camarao"):
            # folha pintada dos dois lados
            area = 2 * ab.largura.valor * ab.altura.valor / 1e6
            dono = ab.abre_para if ab.abre_para and ab.abre_para != "externo" else ab.de or ""
            saida.append(Superficie(dono, f"Porta {ab.id} (dois lados)", "esmalte", None, area))
    return saida


def _do_comodo(
    pav: Pavimento, c: Comodo, cores: CoresVariacao | None, rodape: float
) -> list[Superficie]:
    util = _maior(geometria.poligono_util(pav, c))
    if util is None:
        return []
    pe = float((c.pe_direito or pav.pe_direito).valor)
    por_cor: dict[str | None, float] = defaultdict(float)
    destaque: dict[str, tuple[str, float]] = {}
    faixa_rodape = 0.0
    anel: list[tuple[float, float]] = [(float(x), float(y)) for x, y in util.exterior.coords]
    for p0, p1 in pairwise(anel):
        tam = math.dist(p0, p1)
        paredes = geometria.paredes_da_face(pav, c, p0, p1)
        if not paredes or tam < 1:
            continue
        w = paredes[0]
        h = min(float(w.altura.valor) if w.altura else pe, pe)
        area = tam * h
        trecho = _trecho(w, p0, p1)
        portas_na_face = 0.0
        for ab in pav.aberturas:
            if ab.parede != w.id:
                continue
            d0 = float(ab.distancia_inicio.valor)
            ov = _sobreposto(trecho, (d0, d0 + ab.largura.valor))
            if ov <= 0:
                continue
            area -= ov * ab.altura.valor
            if isinstance(ab, Porta):
                portas_na_face += ov
            elif isinstance(ab, Janela) and ab.peitoril.valor < rodape:
                portas_na_face += ov  # janela até o chão também corta o rodapé
        faixa = max(0.0, tam - portas_na_face) * rodape
        faixa_rodape += faixa
        area -= faixa
        propria = cores.paredes.get(w.id) if cores else None
        if propria:
            atual = destaque.get(w.id, (propria, 0.0))
            destaque[w.id] = (propria, atual[1] + area)
        else:
            por_cor[cores.parede if cores else None] += area
    saida = [
        Superficie(c.id, "Paredes", "latex", cor, a / 1e6) for cor, a in por_cor.items() if a > 0
    ]
    saida += [
        Superficie(c.id, f"Parede {pid} (destaque)", "latex", cor, a / 1e6)
        for pid, (cor, a) in sorted(destaque.items())
        if a > 0
    ]
    saida.append(Superficie(c.id, "Teto", "latex", cores.teto if cores else None, util.area / 1e6))
    if faixa_rodape > 0:
        cor_rodape = cores.rodape if cores else None
        saida.append(Superficie(c.id, "Rodapé", "esmalte", cor_rodape, faixa_rodape / 1e6))
    return saida


def calcular(
    pavimento: Pavimento,
    cores: Mapping[str, CoresVariacao | None] | None = None,
    regras: Mapping[str, object] | None = None,
) -> Resultado:
    """Superfícies, litros de cada uma e o que comprar por tinta e cor (latas)."""
    p = Parametros.do_projeto(regras or {})
    sup = superficies(pavimento, cores)
    soma: dict[tuple[Tinta, str | None], float] = defaultdict(float)
    for s in sup:
        soma[(s.tinta, s.cor)] += s.area_m2
    grupos = []
    for (tinta, cor), area in sorted(soma.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        total = litros(area, tinta, p)
        tamanhos = p.latas_latex if tinta == "latex" else p.latas_esmalte
        grupos.append(Grupo(tinta, cor, round(area, 2), round(total, 2), latas(total, tamanhos)))
    return Resultado(sup, grupos, p, [round(litros(s.area_m2, s.tinta, p), 2) for s in sup])
