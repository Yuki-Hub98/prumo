"""Regras do banheiro (CLAUDE.md §6, "Por tipo de cômodo").

- **área livre** à frente do vaso e do lavatório;
- **tomada perto do box** (água + eletricidade);
- **box sem ralo**;
- **vaso sem esgoto** e **lavatório sem água fria ou esgoto** (como a pia da cozinha).
"""

from __future__ import annotations

from shapely import Point

from interiores_core.modelo import Movel, PontoInstalacao, TipoInstalacao
from interiores_core.regras.contexto import Contexto, Regra, de_tipo, lado_local
from interiores_core.validacao import Severidade

LIMITES = {
    "frente_vaso": 600,
    "frente_lavatorio": 600,
    "tomada_box": 600,
    "ponto_max": 300,
}
"""Padrões em mm; o ``regras.toml`` do projeto pode sobrescrever (seção ``[banheiro]``).

``ponto_max``: até onde o ponto de água/esgoto conta como "do" vaso ou lavatório.
"""


def _nome(m: Movel) -> str:
    return m.nome or m.id


def area_livre(ctx: Contexto) -> None:
    """Espaço livre à frente do vaso e do lavatório (para sentar, levantar e usar)."""
    for tipo, chave, nome in (
        ("vaso", "frente_vaso", "vaso"),
        ("lavatorio", "frente_lavatorio", "lavatório"),
    ):
        limite = ctx.limites[chave]
        for m in de_tipo(ctx.moveis, tipo):
            lado, direcao = lado_local(m, "frente")
            folga = ctx.folga(lado, direcao, exceto=m.id)
            if folga < limite:
                ctx.add(
                    Severidade.AVISO,
                    f"frente_{tipo}",
                    f"frente do {nome} '{_nome(m)}' tem {folga:.0f} mm livres; mínimo {limite}",
                    elemento=m.id,
                    regiao=ctx.faixa(lado, direcao, limite).intersection(ctx.util),
                )


def tomada_perto_do_box(ctx: Contexto) -> None:
    """Tomada a menos de ``tomada_box`` da área do box: erro (respingo no chuveiro)."""
    limite = ctx.limites["tomada_box"]
    boxes = de_tipo(ctx.moveis, "box")
    if not boxes:
        return
    for inst in ctx.pavimento.instalacoes:
        if not isinstance(inst, PontoInstalacao) or inst.tipo != TipoInstalacao.TOMADA:
            continue
        if inst.comodo not in (None, ctx.comodo.id):
            continue
        parede = ctx.pavimento.parede(inst.parede) if inst.parede else None
        if parede is not None and ctx.comodo.id not in (parede.lado_a, parede.lado_b):
            continue  # tomada do outro lado da parede
        # o ponto fica no eixo da parede: a face (onde a tomada está) é meia espessura antes
        meia = parede.espessura.valor / 2 if parede is not None else 0.0
        ponto = Point(inst.posicao)
        for box in boxes:
            dist = max(0.0, ctx.poligonos[box.id].distance(ponto) - meia)
            if dist < limite:
                ctx.add(
                    Severidade.ERRO,
                    "tomada_box",
                    f"tomada '{inst.id}' a {dist:.0f} mm do box '{_nome(box)}'; "
                    f"mínimo {limite} (água e eletricidade)",
                    elemento=inst.id,
                    regiao=ponto.buffer(150),
                )


def box_com_ralo(ctx: Contexto) -> None:
    """Todo box precisa de um ralo dentro da área dele."""
    ralos = ctx.instalacoes("ralo")
    for box in de_tipo(ctx.moveis, "box"):
        pol = ctx.poligonos[box.id]
        if not any(pol.buffer(1).intersects(r) for r in ralos):
            ctx.add(
                Severidade.ERRO,
                "box_sem_ralo",
                f"box '{_nome(box)}' sem ralo dentro dele (marque o ralo no piso do box)",
                elemento=box.id,
                regiao=pol,
            )


def pontos_de_agua(ctx: Contexto) -> None:
    """Vaso com esgoto; lavatório com água fria e esgoto, a menos de ``ponto_max``."""
    limite = ctx.limites["ponto_max"]
    precisa = {
        "vaso": (("esgoto", "vaso_sem_esgoto", "esgoto"),),
        "lavatorio": (
            ("agua_fria", "lavatorio_sem_agua", "água fria"),
            ("esgoto", "lavatorio_sem_esgoto", "esgoto"),
        ),
    }
    nomes = {"vaso": "vaso", "lavatorio": "lavatório"}
    for tipo, pontos in precisa.items():
        for m in de_tipo(ctx.moveis, tipo):
            pol = ctx.poligonos[m.id]
            for inst, codigo, nome in pontos:
                if not any(pol.distance(p) <= limite for p in ctx.instalacoes(inst)):
                    ctx.add(
                        Severidade.ERRO,
                        codigo,
                        f"{nomes[tipo]} '{_nome(m)}' sem ponto de {nome} a menos de {limite} mm",
                        elemento=m.id,
                        regiao=pol.buffer(limite),
                    )


REGRAS: list[Regra] = [area_livre, tomada_perto_do_box, box_com_ralo, pontos_de_agua]
