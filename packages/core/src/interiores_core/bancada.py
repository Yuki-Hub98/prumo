"""Bancada/mesa planejada: trechos do tampo, módulos, pernas, peças e ferragens.

Referencial do móvel (como em :mod:`interiores_core.geometria`): centro na origem,
costas em -y, frente em +y; a esquerda de quem olha de frente é +x.

O tampo é reto (um trecho, ``costas``) ou em L (``Movel.forma == "L"``): o trecho das
``costas`` ocupa a largura toda na faixa de trás (com o canto) e o ``braco`` vem para a
frente do lado ``lado_l``. Cada trecho tem coordenadas próprias:

- ``u`` ao longo do trecho, a partir da ponta: nas costas, a ponta esquerda de quem
  olha de frente; no braço, a ponta do braço (andando para as costas);
- ``v`` do fundo (parede) para o lado de uso.

Os módulos ficam no piso, com o fundo encostado no fundo do trecho e a altura livre
sob o tampo; cada um vira um :class:`Movel` planejado comum (mesmo cálculo, desenho e
3D dos outros planejados). As pernas vão nos cantos do tampo que não estão sobre um
módulo e no meio dos vãos maiores que ``VAO_MAX``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Literal

from shapely import Point, Polygon

from interiores_core import geometria, planejado
from interiores_core.medidas import Medida
from interiores_core.modelo import Bancada, ModuloBancada, Movel
from interiores_core.planejado import Ferragem, Peca, Planejado, Retangulo

BEIRAL = 20
"""mm que o tampo passa da frente do módulo (sem valor de profundidade)."""
PERNA = 50
"""Lado da perna (tubo 50 × 50; o pé de madeira usa o mesmo espaço)."""
RECUO_PERNA = 30
"""Da borda do tampo até a face da perna."""
VAO_MAX = 1800
"""Vão livre do tampo, entre apoios, acima do qual entra perna no meio."""
BRACO_PADRAO = geometria.BRACO_BANCADA
"""Largura dos dois trechos do tampo em L sem medida (fundo de bancada/mesa)."""

TipoTrecho = Literal["costas", "braco"]
_ROTACAO_DA_FRENTE = {(0, 1): 0, (-1, 0): 90, (0, -1): 180, (1, 0): 270}


class BancadaInvalidaError(planejado.ConstrucaoInvalidaError):
    """Módulo fora do tampo, sobreposto a outro ou com construção que não cabe."""


@dataclass(frozen=True)
class Trecho:
    nome: TipoTrecho
    inicio: tuple[float, float]
    """Canto de trás (lado da parede) na ponta do trecho, no referencial do móvel."""
    eixo: tuple[int, int]
    """Direção em que ``u`` cresce."""
    frente: tuple[int, int]
    """Do fundo para o lado de uso (``v``)."""
    comprimento: float
    profundidade: float

    def ponto(self, u: float, v: float) -> tuple[float, float]:
        """(u, v) do trecho → (x, y) no referencial do móvel."""
        return (
            self.inicio[0] + u * self.eixo[0] + v * self.frente[0],
            self.inicio[1] + u * self.eixo[1] + v * self.frente[1],
        )

    def uv(self, x: float, y: float) -> tuple[float, float]:
        dx, dy = x - self.inicio[0], y - self.inicio[1]
        return (dx * self.eixo[0] + dy * self.eixo[1], dx * self.frente[0] + dy * self.frente[1])


@dataclass(frozen=True)
class Perna:
    x: float
    y: float
    """Centro, no referencial do móvel."""
    painel: bool = False
    """Painel de chapa (ponta livre com ``pernas="painel"``): ``x, y`` é o meio dele."""
    comprimento: float = PERNA
    """Painel: ao longo da profundidade do trecho."""
    trecho: TipoTrecho = "costas"


@dataclass
class ModuloCalculado:
    modulo: ModuloBancada
    movel: Movel
    """O módulo como móvel planejado comum, no referencial global (centro e rotação)."""
    calculo: Planejado
    trecho: TipoTrecho
    u0: float
    u1: float
    profundidade: float
    centro_local: tuple[float, float] = (0.0, 0.0)
    """Centro do módulo no referencial da bancada."""
    rotacao_local: int = 0
    """Giro do módulo em relação à bancada (a frente dele aponta para a frente do trecho)."""


@dataclass
class BancadaCalculada(Planejado):
    """Resultado do cálculo da bancada: peças e ferragens de tudo (tampo, pernas, painéis e
    módulos), as vistas de frente por trecho e onde ficam pernas e módulos."""

    trechos: list[Trecho] = field(default_factory=list)
    pernas: list[Perna] = field(default_factory=list)
    modulos: list[ModuloCalculado] = field(default_factory=list)
    vistas: dict[str, list[Retangulo]] = field(default_factory=dict)
    """Vista de frente de cada trecho (como o ``layout`` dos planejados): x de quem olha."""


def eh_bancada(movel: Movel) -> bool:
    return movel.bancada is not None


def braco(movel: Movel) -> float:
    """Largura dos trechos do L (dada ou ``BRACO_PADRAO``, até 60 % do lado menor)."""
    return geometria.braco_l(movel)


def esquerda_no_inicio(t: Trecho) -> bool:
    """Se o começo do trecho (u = 0) fica à esquerda de quem olha a frente dele."""
    return t.eixo == (-t.frente[1], t.frente[0])


def x_da_vista(t: Trecho, u0: float, u1: float) -> float:
    """Onde começa, na vista de frente do trecho (x da esquerda de quem olha), o pedaço
    [u0, u1] do trecho."""
    return u0 if esquerda_no_inicio(t) else t.comprimento - u1


def trechos(movel: Movel) -> list[Trecho]:
    """O trecho das costas e, no L, o do braço."""
    w, d = movel.largura.valor / 2, movel.profundidade.valor / 2
    if movel.forma != "L":
        return [Trecho("costas", (w, -d), (-1, 0), (0, 1), 2 * w, 2 * d)]
    b = braco(movel)
    s = -1 if movel.lado_l == "direita" else 1
    return [
        Trecho("costas", (w, -d), (-1, 0), (0, 1), 2 * w, b),
        Trecho("braco", (s * w, d), (0, -1), (-s, 0), 2 * d - b, b),
    ]


def _trecho(ts: list[Trecho], nome: str) -> Trecho | None:
    return next((t for t in ts if t.nome == nome), None)


def _medida(valor: float, base: Medida, obs: str) -> Medida:
    return Medida(valor=round(valor), origem=base.origem, obs=obs)


def modulo_como_movel(movel: Movel, mod: ModuloBancada, t: Trecho) -> Movel:
    """O módulo como móvel planejado comum (centro e rotação globais)."""
    assert movel.bancada is not None
    e = movel.bancada.tampo.espessura.valor
    prof = mod.profundidade.valor if mod.profundidade else t.profundidade - BEIRAL
    u = mod.distancia.valor + mod.largura.valor / 2
    cx, cy = t.ponto(u, prof / 2)
    rot_local = _ROTACAO_DA_FRENTE[t.frente]
    gx, gy = geometria.girar_movel(movel, cx, cy)
    dados = {
        "id": f"{movel.id}-{mod.id}"[:64],
        "tipo": "modulo_bancada",
        "nome": f"{movel.nome or movel.id} · {mod.id}",
        "centro": [round(gx), round(gy)],
        "rotacao": (movel.rotacao + rot_local) % 360,
        "largura": mod.largura,
        "profundidade": mod.profundidade
        or _medida(prof, movel.profundidade, "profundidade do tampo menos o beiral"),
        "altura": _medida(movel.altura.valor - e, movel.altura, "altura da bancada menos o tampo"),
        "portas": mod.portas,
        "construcao": mod.construcao,
        "acabamento": movel.acabamento,
        "puxador": movel.puxador,
    }
    if movel.elevacao:
        dados["elevacao"] = movel.elevacao
    return Movel.model_validate({k: v for k, v in dados.items() if v is not None})


def _modulos(movel: Movel, ts: list[Trecho]) -> list[ModuloCalculado]:
    assert movel.bancada is not None
    nome = movel.nome or movel.id
    feitos: list[ModuloCalculado] = []
    for mod in movel.bancada.modulos:
        t = _trecho(ts, mod.trecho)
        if t is None:
            raise BancadaInvalidaError(
                f"'{nome}': o módulo '{mod.id}' está no braço do L, mas o tampo é reto"
            )
        u0 = mod.distancia.valor
        u1 = u0 + mod.largura.valor
        prof = mod.profundidade.valor if mod.profundidade else t.profundidade - BEIRAL
        if u1 > t.comprimento + 0.5 or prof > t.profundidade:
            raise BancadaInvalidaError(
                f"'{nome}': o módulo '{mod.id}' sai do tampo ({u0:.0f} a {u1:.0f} mm, "
                f"fundo {prof:.0f} mm; o trecho tem {t.comprimento:.0f} × "
                f"{t.profundidade:.0f} mm)"
            )
        sint = modulo_como_movel(movel, mod, t)
        try:
            calc = planejado.calcular(sint)
        except planejado.ConstrucaoInvalidaError as e:
            raise BancadaInvalidaError(f"'{nome}', módulo '{mod.id}': {e}") from e
        centro = t.ponto((u0 + u1) / 2, prof / 2)
        rot = _ROTACAO_DA_FRENTE[t.frente]
        feitos.append(ModuloCalculado(mod, sint, calc, mod.trecho, u0, u1, prof, centro, rot))
    # módulos que se cruzam (no mesmo trecho, ou um do braço entrando no canto das costas)
    poligonos = [(m, geometria.poligono_movel(m.movel)) for m in feitos]
    for i, (a, pa) in enumerate(poligonos):
        for b, pb in poligonos[i + 1 :]:
            if pa.intersection(pb).area > 100:
                raise BancadaInvalidaError(
                    f"'{nome}': os módulos '{a.modulo.id}' e '{b.modulo.id}' se sobrepõem"
                )
    return feitos


def _pernas(movel: Movel, ts: list[Trecho], mods: list[ModuloCalculado]) -> list[Perna]:
    """Pernas nos cantos do tampo sem módulo embaixo e no meio dos vãos longos."""
    assert movel.bancada is not None
    meio = RECUO_PERNA + PERNA / 2
    contorno = geometria.contorno_local(movel)
    sob_modulo: list[Polygon] = []
    for m in mods:
        t = _trecho(ts, m.trecho)
        assert t is not None
        cantos_mod = ((m.u0, 0), (m.u1, 0), (m.u1, m.profundidade), (m.u0, m.profundidade))
        sob_modulo.append(Polygon([t.ponto(u, v) for u, v in cantos_mod]).buffer(meio))

    def livre(x: float, y: float) -> bool:
        return not any(p.contains(Point(x, y)) for p in sob_modulo)

    cantos = [
        (float(x), float(y))
        for x, y in contorno.buffer(-meio, join_style="mitre").exterior.coords[:-1]
    ]
    pernas = [Perna(x, y) for x, y in cantos if livre(x, y)]
    # vãos longos: por trecho, apoios (pernas e módulos) projetados no eixo
    for t in ts:
        apoios: list[tuple[float, float]] = []
        for p in pernas:
            u, v = t.uv(p.x, p.y)
            if -meio <= u <= t.comprimento + meio and -1 <= v <= t.profundidade + 1:
                apoios.append((u - PERNA / 2, u + PERNA / 2))
        apoios += [(m.u0, m.u1) for m in mods if m.trecho == t.nome]
        if t.nome == "braco":  # a ponta de trás do braço apoia no trecho das costas
            apoios.append((t.comprimento, t.comprimento))
        apoios.sort()
        fim_anterior = None
        for ini, fim in apoios:
            if fim_anterior is not None and ini - fim_anterior > VAO_MAX:
                u = (ini + fim_anterior) / 2
                for v in (meio, t.profundidade - meio):
                    x, y = t.ponto(u, v)
                    pernas.append(Perna(x, y, trecho=t.nome))
            fim_anterior = fim if fim_anterior is None else max(fim_anterior, fim)
    # marca o trecho de cada perna (a do canto do L fica com as costas)
    marcadas = []
    for p in pernas:
        nome: TipoTrecho = "costas"
        costas = _trecho(ts, "costas")
        assert costas is not None
        _, v = costas.uv(p.x, p.y)
        if v > costas.profundidade + 1:
            nome = "braco"
        marcadas.append(Perna(p.x, p.y, trecho=nome))
    if movel.bancada.pernas == "painel":
        marcadas = _paineis(movel, ts, marcadas)
    return marcadas


def _paineis(movel: Movel, ts: list[Trecho], pernas: list[Perna]) -> list[Perna]:
    """Pontas livres do tampo (sem módulo): o par de pernas vira um painel de chapa."""
    meio = RECUO_PERNA + PERNA / 2
    pontas: list[tuple[Trecho, float]] = []
    costas = _trecho(ts, "costas")
    assert costas is not None
    if movel.forma == "L":
        pontas.append((costas, costas.comprimento - meio))  # ponta longe do braço
        b = _trecho(ts, "braco")
        assert b is not None
        pontas.append((b, meio))  # ponta do braço
    else:
        pontas += [(costas, meio), (costas, costas.comprimento - meio)]
    if movel.forma == "L" and movel.lado_l == "direita":
        # com o braço à direita, a ponta livre das costas é a do começo (u = 0)
        pontas[0] = (costas, meio)
    restantes = list(pernas)
    for t, u in pontas:
        par = [p for p in restantes if abs(t.uv(p.x, p.y)[0] - u) < 1]
        if len(par) != 2:
            continue  # ponta com módulo: já está apoiada
        for p in par:
            restantes.remove(p)
        cx, cy = t.ponto(u, t.profundidade / 2)
        restantes.append(
            Perna(cx, cy, painel=True, comprimento=t.profundidade - 2 * RECUO_PERNA, trecho=t.nome)
        )
    return restantes


def _juntar(ferragens: list[Ferragem]) -> list[Ferragem]:
    soma: dict[tuple[str, str], int] = defaultdict(int)
    for f in ferragens:
        soma[(f.nome, f.obs)] += f.quantidade
    return [Ferragem(nome, qtd, obs) for (nome, obs), qtd in soma.items()]


def calcular(movel: Movel) -> BancadaCalculada:
    """Tampo, pernas/painéis e módulos da bancada, com peças, ferragens e vistas.

    Levanta ``BancadaInvalidaError`` se um módulo não couber.
    """
    b: Bancada | None = movel.bancada
    if b is None:
        raise ValueError(f"o móvel '{movel.id}' não é bancada planejada")
    ts = trechos(movel)
    mods = _modulos(movel, ts)
    pernas = _pernas(movel, ts, mods)
    e = b.tampo.espessura.valor
    mat = b.tampo.material
    alt = movel.altura.valor
    h_perna = alt - e
    r = BancadaCalculada(movel, trechos=ts, pernas=pernas, modulos=mods)

    # ------------------------------------------------------------ tampo
    larg, prof = movel.largura.valor, movel.profundidade.valor
    if movel.forma == "L":
        br = braco(movel)
        r.pecas += [
            Peca("Tampo (trecho das costas)", mat, e, larg, br, 1, "2C2L", "com o canto do L"),
            Peca(
                "Tampo (braço do L)", mat, e, prof - br, br, 1, "2C1L",
                "emenda no canto com o trecho das costas",
            ),
        ]  # fmt: skip
        r.ferragens.append(Ferragem("Conector de emenda de tampo", 2, "na emenda do canto"))
    else:
        r.pecas.append(Peca("Tampo", mat, e, larg, prof, 1, "2C2L"))

    # ------------------------------------------------------------ pernas e painéis
    paineis = [p for p in pernas if p.painel]
    pes = [p for p in pernas if not p.painel]
    for p in paineis:
        r.pecas.append(Peca("Pé painel", mat, e, h_perna, p.comprimento, 1, "2C1L"))
    if paineis:
        r.ferragens.append(Ferragem("Cantoneira de fixação do pé painel", 2 * len(paineis)))
    if pes:
        if b.pernas == "madeira":
            r.ferragens.append(Ferragem(f"Pé de madeira {h_perna} mm", len(pes)))
        else:
            r.ferragens += [
                Ferragem(
                    f"Perna metálica 50 × 50 mm, {h_perna} mm, com sapata regulável", len(pes)
                ),
                Ferragem("Placa de fixação da perna no tampo", len(pes)),
            ]

    # ------------------------------------------------------------ módulos
    for m in mods:
        r.pecas += [replace(p, nome=f"{m.modulo.id}: {p.nome}") for p in m.calculo.pecas]
        r.ferragens += m.calculo.ferragens
    if mods:
        r.ferragens.append(Ferragem("Parafuso de fixação do módulo no tampo", 4 * len(mods)))
    r.ferragens = _juntar(r.ferragens)

    # ------------------------------------------------------------ vistas de frente
    for t in ts:
        vista = [Retangulo("tampo", 0, alt - e, t.comprimento, e, "tampo")]
        for p in pernas:
            if p.trecho != t.nome:
                continue
            u, _ = t.uv(p.x, p.y)
            lado = e if p.painel else PERNA
            x = x_da_vista(t, u - lado / 2, u + lado / 2)
            tipo = "painel" if p.painel else "perna"
            vista.append(Retangulo(tipo, x, 0, lado, h_perna, tipo))
        for i, m in enumerate(x for x in mods if x.trecho == t.nome):
            x0 = x_da_vista(t, m.u0, m.u1)
            for ret in m.calculo.layout:
                vista.append(replace(ret, x=x0 + ret.x, vao=i))
        r.vistas[t.nome] = vista
    r.layout = r.vistas["costas"]
    return r


# ---------------------------------------------------------------- modelos prontos


def _est(valor: int, obs: str) -> dict[str, object]:
    return {"valor": valor, "origem": "estimada", "obs": f"estimada: {obs}"}


def modulo_pronto(
    id_: str, tipo: str, distancia: int, largura: int = 450, trecho: TipoTrecho = "costas"
) -> dict[str, object]:
    """Módulo pronto: ``gaveteiro`` (3 gavetas), ``nicho`` (2 prateleiras, aberto) ou
    ``armario`` (porta de abrir e 1 prateleira)."""
    espacos = {
        "gaveteiro": [{"tipo": "gaveta"}, {"tipo": "gaveta"}, {"tipo": "gaveta"}],
        "nicho": [{"tipo": "nicho"}, {"tipo": "nicho"}, {"tipo": "nicho"}],
        "armario": [{"tipo": "nicho"}, {"tipo": "nicho"}],
    }[tipo]
    mod: dict[str, object] = {
        "id": id_,
        "trecho": trecho,
        "distancia": _est(distancia, "posição sugerida do módulo"),
        "largura": _est(largura, f"{tipo} de {largura} mm"),
        "construcao": {
            "chapa": {"material": "MDF branco", "espessura": _est(18, "MDF 18 mm")},
            "fundo": {"material": "HDF branco", "espessura": _est(6, "fundo em HDF 6 mm")},
            "rodape": _est(80, "rodapé de 80 mm"),
            "vaos": [{"espacos": espacos, "porta": tipo == "armario"}],
        },
    }
    if tipo in ("armario", "gaveteiro"):
        mod["portas"] = "abrir" if tipo == "armario" else None
    return {k: v for k, v in mod.items() if v is not None}


def bancada_sugerida(movel: Movel) -> dict[str, object]:
    """Bancada pronta para o modelo do catálogo (sem modelo: só tampo e pernas).

    Mesa (até 80 cm de altura): tampo MDF 25 e gaveteiro na ponta direita; bancada de
    cozinha (mais alta): tampo de granito 30 e armários sob o trecho das costas.
    """
    cozinha = movel.altura.valor > 800
    tampo = (
        {"material": "Granito", "espessura": _est(30, "tampo de granito 30 mm")}
        if cozinha
        else {"material": "MDF branco", "espessura": _est(25, "tampo MDF 25 mm")}
    )
    modulos: list[dict[str, object]] = []
    larg = movel.largura.valor
    if movel.modelo in ("reta_gaveteiro", "l_gaveteiro"):
        # gaveteiro na ponta longe do braço do L (à direita de quem olha, se não houver L)
        direita = movel.forma == "L" and movel.lado_l == "direita"
        modulos.append(modulo_pronto("gaveteiro", "gaveteiro", 30 if direita else larg - 480))
    elif movel.modelo in ("cozinha_reta", "cozinha_l"):
        # no L o canto fica livre, com as pernas à vista; os armários vêm depois dele
        canto = movel.forma == "L" and movel.lado_l != "direita"
        inicio = 30 + (round(braco(movel)) if canto else 0)
        n = max(1, int((larg - inicio - 30) // 800))
        for i in range(n):
            modulos.append(modulo_pronto(f"armario{i + 1}", "armario", inicio + i * 800, 800))
    return {"tampo": tampo, "pernas": "metal", "modulos": modulos}
