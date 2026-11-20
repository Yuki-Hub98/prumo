"""Regras da cozinha (CLAUDE.md §6, "Por tipo de cômodo").

- **triângulo de trabalho**: pia, fogão e geladeira, medido entre os meios das frentes;
- **pia com água e esgoto**: ponto de água fria e de esgoto a menos de ``pia_ponto_max``;
- **fogão a gás** com ponto de gás no cômodo e ventilação (janela ou porta para fora);
- **fogão sob janela** (vento apaga a chama, cortina pega fogo);
- **altura da bancada** da pia.
"""

from __future__ import annotations

import math

from shapely import LineString

from interiores_core import catalogo, geometria
from interiores_core.modelo import Janela, Movel, Porta
from interiores_core.regras.contexto import Contexto, Regra, de_tipo, lado_local
from interiores_core.validacao import Severidade

LIMITES = {
    "triangulo_min": 3600,
    "triangulo_max": 6600,
    "pia_ponto_max": 300,
    "altura_bancada": 900,
    "altura_bancada_tolerancia": 50,
    "fogao_janela": 300,
}
"""Padrões em mm; o ``regras.toml`` do projeto pode sobrescrever (seção ``[cozinha]``).

``fogao_janela``: distância (na planta) abaixo da qual o fogão conta como "sob a janela".
"""


def _nome(m: Movel) -> str:
    return m.nome or m.id


def _meio_da_frente(m: Movel) -> tuple[float, float]:
    (a, b), _ = lado_local(m, "frente")
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def triangulo(ctx: Contexto) -> None:
    """Soma das distâncias pia-fogão-geladeira entre ``triangulo_min`` e ``triangulo_max``."""
    trio = {t: de_tipo(ctx.moveis, t) for t in ("pia", "fogao", "geladeira")}
    faltando = [t for t, ms in trio.items() if not ms]
    if faltando:
        if len(faltando) < 3:  # começou a montar a cozinha
            nomes = {"pia": "pia", "fogao": "fogão", "geladeira": "geladeira"}
            ctx.add(
                Severidade.INFO,
                "triangulo_incompleto",
                f"triângulo de trabalho incompleto: falta {', '.join(nomes[t] for t in faltando)}",
            )
        return
    pia, fogao, geladeira = trio["pia"][0], trio["fogao"][0], trio["geladeira"][0]
    pts = [_meio_da_frente(m) for m in (pia, fogao, geladeira)]
    lados = [math.dist(pts[0], pts[1]), math.dist(pts[1], pts[2]), math.dist(pts[2], pts[0])]
    soma = sum(lados)
    lo, hi = ctx.limites["triangulo_min"], ctx.limites["triangulo_max"]
    if not lo <= soma <= hi:
        longe = (
            "longe demais (anda muito)" if soma > hi else "apertado demais (sem bancada entre eles)"
        )
        ctx.add(
            Severidade.AVISO,
            "triangulo_trabalho",
            f"triângulo pia-fogão-geladeira soma {soma:.0f} mm, {longe}; "
            f"o recomendado é de {lo} a {hi} mm "
            f"(pia-fogão {lados[0]:.0f}, fogão-geladeira {lados[1]:.0f}, "
            f"geladeira-pia {lados[2]:.0f})",
            regiao=LineString([*pts, pts[0]]).buffer(60),
        )


def pia_com_agua_e_esgoto(ctx: Contexto) -> None:
    """Toda pia precisa de ponto de água fria e de esgoto a menos de ``pia_ponto_max``."""
    limite = ctx.limites["pia_ponto_max"]
    for pia in de_tipo(ctx.moveis, "pia"):
        pol = ctx.poligonos[pia.id]
        for tipo, codigo, nome in (
            ("agua_fria", "pia_sem_agua", "água fria"),
            ("esgoto", "pia_sem_esgoto", "esgoto"),
        ):
            if not any(pol.distance(p) <= limite for p in ctx.instalacoes(tipo)):
                ctx.add(
                    Severidade.ERRO,
                    codigo,
                    f"pia '{_nome(pia)}' sem ponto de {nome} a menos de {limite} mm "
                    "(marque o ponto na parede atrás da pia)",
                    elemento=pia.id,
                    regiao=pol.buffer(limite),
                )


def _a_gas(fogao: Movel) -> bool:
    """Fogão a gás pelo modelo do catálogo; sem modelo conhecido, considera a gás."""
    item = catalogo.item_do_tipo(fogao.tipo)
    modelo = item.modelo(fogao.modelo) if item and fogao.modelo else None
    return modelo is None or modelo.energia != "eletrico"


def _janelas(ctx: Contexto) -> list[tuple[Janela, LineString, float]]:
    """Janelas nas paredes do cômodo: (janela, trecho do vão no eixo, meia espessura)."""
    saida = []
    for ab in ctx.pavimento.aberturas:
        if not isinstance(ab, Janela) or ab.parede not in ctx.comodo.paredes:
            continue
        parede = ctx.pavimento.parede(ab.parede)
        if parede is None:
            continue
        u, _ = geometria.direcao(parede)
        x0, y0 = parede.inicio
        d0, d1 = ab.distancia_inicio.valor, ab.distancia_inicio.valor + ab.largura.valor
        trecho = LineString([(x0 + u[0] * d0, y0 + u[1] * d0), (x0 + u[0] * d1, y0 + u[1] * d1)])
        saida.append((ab, trecho, parede.espessura.valor / 2))
    return saida


def fogao_gas_e_ventilacao(ctx: Contexto) -> None:
    """Fogão a gás: ponto de gás no cômodo e ventilação (janela ou porta para fora)."""
    fogoes = [f for f in de_tipo(ctx.moveis, "fogao") if _a_gas(f)]
    if not fogoes:
        return
    perto = ctx.util.buffer(200)
    tem_gas = any(perto.intersects(p) for p in ctx.instalacoes("gas"))
    ventila = bool(_janelas(ctx)) or any(
        "externo" in (p.de, p.para) for p in ctx.portas if isinstance(p, Porta)
    )
    for f in fogoes:
        pol = ctx.poligonos[f.id]
        if not tem_gas:
            ctx.add(
                Severidade.ERRO,
                "fogao_sem_gas",
                f"fogão a gás '{_nome(f)}' sem ponto de gás na cozinha (marque o ponto ou use um "
                "modelo elétrico/indução)",
                elemento=f.id,
                regiao=pol.buffer(150),
            )
        if not ventila:
            ctx.add(
                Severidade.ERRO,
                "fogao_sem_ventilacao",
                f"fogão a gás '{_nome(f)}' numa cozinha sem janela nem porta para fora "
                "(ventilação obrigatória para gás)",
                elemento=f.id,
                regiao=pol.buffer(150),
            )


def fogao_sob_janela(ctx: Contexto) -> None:
    """Fogão encostado embaixo de uma janela: o vento apaga a chama e a cortina pega fogo."""
    limite = ctx.limites["fogao_janela"]
    for f in de_tipo(ctx.moveis, "fogao"):
        pol = ctx.poligonos[f.id]
        for janela, trecho, meia in _janelas(ctx):
            faixa = trecho.buffer(meia + limite, cap_style="flat")
            if faixa.intersection(pol).area > 1:
                ctx.add(
                    Severidade.AVISO,
                    "fogao_sob_janela",
                    f"fogão '{_nome(f)}' embaixo da janela '{janela.id}': vento apaga a chama e "
                    "cortina pega fogo (afaste ou use cortina fora do alcance)",
                    elemento=f.id,
                    regiao=faixa.intersection(ctx.util),
                )


def altura_bancada(ctx: Contexto) -> None:
    """Bancada da pia perto de ``altura_bancada`` (± ``altura_bancada_tolerancia``)."""
    alvo, tol = ctx.limites["altura_bancada"], ctx.limites["altura_bancada_tolerancia"]
    for pia in de_tipo(ctx.moveis, "pia"):
        topo = pia.altura.valor + (pia.elevacao.valor if pia.elevacao else 0)
        if abs(topo - alvo) > tol:
            ctx.add(
                Severidade.AVISO,
                "altura_bancada",
                f"bancada da pia '{_nome(pia)}' a {topo} mm do piso; o confortável é {alvo} mm "
                f"(± {tol})",
                elemento=pia.id,
                regiao=ctx.poligonos[pia.id],
            )


REGRAS: list[Regra] = [
    triangulo,
    pia_com_agua_e_esgoto,
    fogao_gas_e_ventilacao,
    fogao_sob_janela,
    altura_bancada,
]
