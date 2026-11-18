"""Cálculo do móvel planejado: layout da frente, peças, ferragens e chapas.

Coordenadas do layout no referencial do móvel visto de frente: x da esquerda para
a direita, y do piso para cima, origem no canto inferior esquerdo da caixa (mm).

Construção padrão (ver :class:`interiores_core.modelo.Construcao`):

- laterais inteiras (altura total × profundidade);
- base e tampo entre as laterais; rodapé frontal recuado sob a base, se houver;
- divisórias entre a base e o tampo;
- fundo sobreposto (largura × altura da caixa);
- prateleiras entre espaços do vão, recuadas 20 mm da frente (80 mm com porta de
  correr, por causa do trilho);
- gavetas com corrediça telescópica (12,5 mm por lado) e frente com 2 mm de folga;
- portas sobrepostas de abrir (até 600 mm, uma folha; acima, duas) com 3 mm de
  folga, ou portas de correr cobrindo o vão interno com 25 mm de transpasse.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from interiores_core.modelo import Construcao, Movel

FOLGA_PORTA = 3
FOLGA_FRENTE_GAVETA = 4
"""Folga total (2 mm por lado) da frente da gaveta dentro do vão."""
CORREDICA_LADO = 12.5
"""Espaço da corrediça telescópica em cada lado da gaveta."""
CORREDICAS = (250, 300, 350, 400, 450, 500, 550)
"""Comprimentos comerciais de corrediça telescópica (mm)."""
RECUO_PRATELEIRA = 20
RECUO_TRILHO = 80
"""Profundidade tomada pelo trilho da porta de correr."""
FOLHA_MAX_ABRIR = 600
"""Vão mais largo que isso leva duas folhas de porta de abrir."""
TRANSPASSE_CORRER = 25
CHAPA_INTEIRA = (2750, 1850)
"""Chapa comercial de MDF/MDP (mm)."""
PERDA = 0.15
"""Perda de corte usada na estimativa de chapas (sem plano de corte otimizado)."""


class ConstrucaoInvalidaError(ValueError):
    """As medidas da construção não cabem no móvel."""


@dataclass(frozen=True)
class Retangulo:
    """Elemento da vista frontal."""

    tipo: str
    """lateral, base, tampo, divisoria, rodape, prateleira, gaveta, nicho, cabideiro,
    porta."""
    x: float
    y: float
    largura: float
    altura: float
    rotulo: str = ""
    vao: int | None = None


@dataclass(frozen=True)
class Peca:
    nome: str
    material: str
    espessura: int
    comprimento: float
    largura: float
    quantidade: int
    fita: str = ""
    """Bordas com fita: "1C" = um lado comprido, "2C2L" = os quatro lados..."""
    obs: str = ""

    @property
    def fita_metros(self) -> float:
        """Metros de fita de borda (todas as unidades)."""
        total = 0.0
        if self.fita:
            for qtd, lado in zip(self.fita[::2], self.fita[1::2], strict=True):
                medida = self.comprimento if lado == "C" else self.largura
                total += int(qtd) * medida
        return total * self.quantidade / 1000

    @property
    def area_m2(self) -> float:
        return self.comprimento * self.largura * self.quantidade / 1_000_000


@dataclass(frozen=True)
class Ferragem:
    nome: str
    quantidade: int
    obs: str = ""


@dataclass(frozen=True)
class ChapasNecessarias:
    material: str
    espessura: int
    area_m2: float
    chapas: int
    fita_metros: float


@dataclass
class Planejado:
    """Resultado do cálculo de um móvel planejado."""

    movel: Movel
    layout: list[Retangulo] = field(default_factory=list)
    pecas: list[Peca] = field(default_factory=list)
    ferragens: list[Ferragem] = field(default_factory=list)
    larguras_vaos: list[float] = field(default_factory=list)
    alturas: list[list[float]] = field(default_factory=list)
    """Altura de cada espaço, por vão (mesma ordem de ``construcao``)."""

    @property
    def chapas(self) -> list[ChapasNecessarias]:
        """Área por material/espessura e quantidade estimada de chapas (com perda)."""
        area: dict[tuple[str, int], float] = defaultdict(float)
        fita: dict[tuple[str, int], float] = defaultdict(float)
        for p in self.pecas:
            area[(p.material, p.espessura)] += p.area_m2
            fita[(p.material, p.espessura)] += p.fita_metros
        inteira = CHAPA_INTEIRA[0] * CHAPA_INTEIRA[1] / 1_000_000
        return [
            ChapasNecessarias(
                material=mat,
                espessura=esp,
                area_m2=round(a, 2),
                chapas=math.ceil(a * (1 + PERDA) / inteira),
                fita_metros=round(fita[(mat, esp)], 1),
            )
            for (mat, esp), a in sorted(area.items())
        ]


def _dividir(total: float, dadas: list[float | None], o_que: str) -> list[float]:
    """Completa as medidas que faltam dividindo igualmente o que sobra."""
    soma = sum(d for d in dadas if d is not None)
    livres = sum(1 for d in dadas if d is None)
    sobra = total - soma
    if sobra < -0.5 or (livres and sobra / livres < 1):
        raise ConstrucaoInvalidaError(
            f"{o_que}: as medidas informadas somam {soma:.0f} mm, mas cabem {total:.0f} mm"
        )
    return [d if d is not None else sobra / livres for d in dadas]


def _corredica(profundidade: float) -> int | None:
    cabem = [c for c in CORREDICAS if c <= profundidade]
    return max(cabem) if cabem else None


def _dobradicas(altura: float) -> int:
    if altura <= 900:
        return 2
    if altura <= 1600:
        return 3
    if altura <= 2100:
        return 4
    return 5


def calcular(movel: Movel) -> Planejado:
    """Layout, peças e ferragens do móvel. Levanta ``ConstrucaoInvalidaError`` se não couber."""
    c: Construcao | None = movel.construcao
    if c is None:
        raise ValueError(f"o móvel '{movel.id}' não tem construção (planejado)")
    larg, prof, alt = movel.largura.valor, movel.profundidade.valor, movel.altura.valor
    e, f = c.chapa.espessura.valor, c.fundo.espessura.valor
    mat, mat_fundo = c.chapa.material, c.fundo.material
    rodape = c.rodape.valor if c.rodape else 0
    n = len(c.vaos)
    alt_int = alt - rodape - 2 * e
    larg_int = larg - 2 * e - (n - 1) * e
    if alt_int <= 0 or larg_int <= 0:
        raise ConstrucaoInvalidaError("a chapa e o rodapé não deixam espaço interno")
    correr = movel.portas == "correr"
    prof_prat = prof - (RECUO_TRILHO if correr else RECUO_PRATELEIRA)

    r = Planejado(movel)
    r.larguras_vaos = _dividir(
        larg_int, [v.largura.valor if v.largura else None for v in c.vaos], "largura dos vãos"
    )

    # ------------------------------------------------------------ caixa
    r.layout += [
        Retangulo("lateral", 0, 0, e, alt),
        Retangulo("lateral", larg - e, 0, e, alt),
        Retangulo("base", e, rodape, larg - 2 * e, e),
        Retangulo("tampo", e, alt - e, larg - 2 * e, e),
    ]
    r.pecas += [
        Peca("Lateral", mat, e, alt, prof, 2, "1C"),
        Peca("Base", mat, e, larg - 2 * e, prof, 1, "1C"),
        Peca("Tampo", mat, e, larg - 2 * e, prof, 1, "1C"),
        Peca("Fundo", mat_fundo, f, larg, alt - rodape, 1, obs="sobreposto, pregado/grampeado"),
    ]
    if rodape:
        r.layout.append(Retangulo("rodape", e, 0, larg - 2 * e, rodape))
        r.pecas.append(Peca("Rodapé", mat, e, larg - 2 * e, rodape, 1, "1C", "recuado 50 mm"))
    if n > 1:
        r.pecas.append(Peca("Divisória", mat, e, alt_int, prof, n - 1, "1C"))

    # ------------------------------------------------------------ vãos
    prateleiras: dict[float, int] = defaultdict(int)
    gavetas: list[tuple[float, float]] = []
    cabideiros: list[float] = []
    x = float(e)
    y0 = rodape + e
    for i, (vao, w) in enumerate(zip(c.vaos, r.larguras_vaos, strict=True)):
        if i > 0:
            r.layout.append(Retangulo("divisoria", x - e, y0, e, alt_int))
        tipos = [esp.tipo for esp in vao.espacos]
        n_prat = sum(1 for a, b in itertools.pairwise(tipos) if not (a == b == "gaveta"))
        alturas = _dividir(
            alt_int - n_prat * e,
            [esp.altura.valor if esp.altura else None for esp in vao.espacos],
            f"altura dos espaços do vão {i + 1}",
        )
        r.alturas.append(alturas)
        y = float(y0)
        for j, (esp, h) in enumerate(zip(vao.espacos, alturas, strict=True)):
            rotulo = {"gaveta": "gaveta", "nicho": "nicho", "cabideiro": "cabideiro"}[esp.tipo]
            r.layout.append(Retangulo(esp.tipo, x, y, w, h, rotulo, i))
            if esp.tipo == "gaveta":
                gavetas.append((w, h))
            elif esp.tipo == "cabideiro":
                cabideiros.append(w)
            y += h
            if j + 1 < len(tipos) and not (tipos[j] == tipos[j + 1] == "gaveta"):
                r.layout.append(Retangulo("prateleira", x, y, w, e, vao=i))
                prateleiras[round(w, 1)] += 1
                y += e
        x += w + e

    for w, qtd in sorted(prateleiras.items()):
        r.pecas.append(Peca("Prateleira", mat, e, w, prof_prat, qtd, "1C"))

    # ------------------------------------------------------------ gavetas
    prof_gav = _corredica(prof - (RECUO_TRILHO if correr else 0) - 50)
    if gavetas and prof_gav is None:
        raise ConstrucaoInvalidaError(f"profundidade {prof} mm não comporta corrediça de gaveta")
    for (w, h), qtd in sorted(Counter(gavetas).items()):
        caixa_l = w - 2 * CORREDICA_LADO
        caixa_h = h - 50
        assert prof_gav is not None
        r.pecas += [
            Peca(
                "Frente de gaveta",
                mat,
                e,
                w - FOLGA_FRENTE_GAVETA,
                h - FOLGA_FRENTE_GAVETA,
                qtd,
                "2C2L",
            ),
            Peca("Lateral de gaveta", mat, e, prof_gav, caixa_h, 2 * qtd, "1C"),
            Peca(
                "Contrafrente/traseira de gaveta", mat, e, caixa_l - 2 * e, caixa_h, 2 * qtd, "1C"
            ),
            Peca("Fundo de gaveta", mat_fundo, f, caixa_l, prof_gav, qtd),
        ]
        r.ferragens.append(
            Ferragem(f"Corrediça telescópica {prof_gav} mm (par)", qtd, f"gaveta {w:.0f} mm")
        )
    if gavetas:
        r.ferragens.append(Ferragem("Puxador de gaveta", len(gavetas)))

    # ------------------------------------------------------------ cabideiros
    for w, qtd in sorted(Counter(cabideiros).items()):
        r.ferragens += [
            Ferragem(f"Tubo de cabideiro oblongo {w - 2:.0f} mm", qtd),
            Ferragem("Suporte de cabideiro", 2 * qtd),
        ]

    # ------------------------------------------------------------ portas
    alt_porta = alt - rodape - FOLGA_PORTA
    if movel.portas == "abrir":
        folhas: list[tuple[float, float]] = []
        x = float(e)
        for i, (vao, w) in enumerate(zip(c.vaos, r.larguras_vaos, strict=True)):
            ini = 0.0 if i == 0 else x - e / 2
            fim = float(larg) if i == n - 1 else x + w + e / 2
            x += w + e
            if not vao.porta:
                continue
            qtd = 1 if fim - ini <= FOLHA_MAX_ABRIR else 2
            larg_folha = (fim - ini) / qtd - FOLGA_PORTA
            for k in range(qtd):
                r.layout.append(
                    Retangulo(
                        "porta",
                        ini + k * (fim - ini) / qtd,
                        rodape,
                        (fim - ini) / qtd,
                        alt - rodape,
                        "porta",
                        i,
                    )
                )
                folhas.append((larg_folha, alt_porta))
        for (wf, hf), qtd in sorted(Counter(folhas).items()):
            r.pecas.append(Peca("Porta de abrir", mat, e, hf, wf, qtd, "2C2L"))
            r.ferragens.append(
                Ferragem(
                    "Dobradiça 35 mm com amortecedor",
                    _dobradicas(hf) * qtd,
                    f"{_dobradicas(hf)} por folha de {hf:.0f} mm",
                )
            )
        if folhas:
            r.ferragens.append(Ferragem("Puxador de porta", len(folhas)))
    elif correr:
        qtd = 2 if larg_int + (n - 1) * e <= 1800 else 3
        vao_total = larg - 2 * e
        larg_folha = vao_total / qtd + TRANSPASSE_CORRER
        alt_folha = alt_int - 40
        for k in range(qtd):
            r.layout.append(
                Retangulo(
                    "porta",
                    e + k * vao_total / qtd,
                    y0,
                    vao_total / qtd,
                    alt_int,
                    "porta de correr",
                )
            )
        r.pecas.append(Peca("Porta de correr", mat, e, alt_folha, larg_folha, qtd, "2C2L"))
        r.ferragens += [
            Ferragem(f"Kit trilho de porta de correr {vao_total:.0f} mm", 1, "superior e inferior"),
            Ferragem("Roldana de porta de correr", 2 * qtd),
            Ferragem("Puxador de porta de correr (cava ou embutido)", qtd),
        ]

    # ------------------------------------------------------------ apoio e fixação
    total_prat = sum(prateleiras.values())
    if total_prat:
        r.ferragens.append(Ferragem("Pino/suporte de prateleira", 4 * total_prat))
    if not rodape:
        r.ferragens.append(Ferragem("Sapata niveladora", 4 if larg <= 1200 else 6))
    r.ferragens.append(Ferragem("Parafusos, cavilhas e minifix", 1, "a definir pelo marceneiro"))
    return r


# ---------------------------------------------------------------- construções sugeridas


def _est(valor: int, obs: str) -> dict[str, object]:
    return {"valor": valor, "origem": "estimada", "obs": f"estimada: {obs}"}


def _espaco(tipo: str, altura: int | None = None, obs: str = "") -> dict[str, object]:
    esp: dict[str, object] = {"tipo": tipo}
    if altura is not None:
        esp["altura"] = _est(altura, obs or "sugestão da construção padrão")
    return esp


def _vaos(quantidade: int, *modelos: list[dict[str, object]]) -> list[dict[str, object]]:
    """``quantidade`` vãos alternando os modelos de espaços dados."""
    return [{"espacos": modelos[i % len(modelos)]} for i in range(max(1, quantidade))]


TIPOS_PLANEJAVEIS = (
    "guarda_roupa",
    "armario",
    "comoda",
    "criado_mudo",
    "estante",
    "rack",
    "sapateira",
    "penteadeira",
)


def construcao_sugerida(movel: Movel) -> dict[str, object]:
    """Construção padrão para o tipo do móvel (JSON pronto para ``Movel.construcao``).

    Medidas sugeridas entram como ``estimada`` para o usuário ajustar. Levanta
    ``KeyError`` se o tipo não for planejável.
    """
    larg = movel.largura.valor
    gaveta = "gaveta"
    maleiro = _espaco("nicho", 400, "maleiro de 400 mm")
    cabide = [_espaco(gaveta, 180), _espaco(gaveta, 180), _espaco("cabideiro"), maleiro]
    prateleiras = [_espaco("nicho") for _ in range(4)] + [maleiro]
    sugestoes: dict[str, tuple[list[dict[str, object]], int | None]] = {
        "guarda_roupa": (_vaos(round(larg / 800), cabide, prateleiras), 100),
        "armario": (_vaos(round(larg / 700), [_espaco("nicho") for _ in range(3)]), 100),
        "comoda": (_vaos(round(larg / 900), [_espaco(gaveta) for _ in range(4)]), 100),
        "criado_mudo": (_vaos(1, [_espaco("nicho"), _espaco(gaveta, 150)]), None),
        "estante": (_vaos(math.ceil(larg / 800), [_espaco("nicho") for _ in range(5)]), 100),
        "rack": (
            [
                {"espacos": [_espaco("nicho")], "porta": False},
                {"espacos": [_espaco(gaveta), _espaco(gaveta)]},
                {"espacos": [_espaco("nicho")], "porta": False},
            ]
            if larg >= 1500
            else _vaos(2, [_espaco("nicho")], [_espaco(gaveta), _espaco(gaveta)]),
            None,
        ),
        "sapateira": (_vaos(1, [_espaco("nicho") for _ in range(6)]), 100),
        "penteadeira": (_vaos(1, [_espaco("nicho"), _espaco(gaveta, 150)]), None),
    }
    if movel.tipo not in sugestoes:
        raise KeyError(f"'{movel.tipo}' não é planejável (tipos: {', '.join(TIPOS_PLANEJAVEIS)})")
    vaos, rodape = sugestoes[movel.tipo]
    construcao: dict[str, object] = {
        "chapa": {"material": "MDF branco", "espessura": _est(18, "MDF 18 mm, padrão de móvel")},
        "fundo": {"material": "HDF branco", "espessura": _est(6, "fundo em HDF 6 mm")},
        "vaos": vaos,
    }
    suspenso = movel.elevacao is not None and movel.elevacao.valor > 0
    if rodape and not suspenso:
        construcao["rodape"] = _est(rodape, "rodapé de 100 mm")
    return construcao
