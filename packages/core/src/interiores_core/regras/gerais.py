"""Checagens que valem para todo cômodo (CLAUDE.md §6, "Gerais")."""

from __future__ import annotations

from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from interiores_core import geometria
from interiores_core.modelo import PontoInstalacao, TipoInstalacao
from interiores_core.regras.contexto import Contexto, Regra, lado_local
from interiores_core.validacao import Severidade

LIMITES = {"passagem_livre": 700}
"""Padrões em mm; o ``regras.toml`` do projeto pode sobrescrever."""

LADOS_DE_USO = {"cama": ("esquerda", "direita", "frente")}
"""Lados por onde se usa cada tipo de móvel; os demais usam só a frente."""

TOLERANCIA = 10.0
"""Folga numérica (mm) ao testar se uma área livre encosta num ponto."""

ENCOSTA = 50.0
"""Até quantos mm da face da parede um móvel tapa uma tomada/interruptor."""


def _componentes(geom: BaseGeometry) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


def passagem_livre(ctx: Contexto) -> None:
    """Passagem de pelo menos ``passagem_livre`` mm das portas até cada porta e móvel.

    A área por onde se passa é o piso livre "aberto" por um círculo do tamanho da
    passagem: some o que for mais estreito que o limite.
    """
    limite = ctx.limites["passagem_livre"]
    meia = limite / 2
    passavel = _componentes(ctx.livre.buffer(-meia).buffer(meia))

    def componente_em(alvo: BaseGeometry) -> Polygon | None:
        return next((c for c in passavel if c.distance(alvo) <= TOLERANCIA), None)

    principal: Polygon | None = None
    for porta in ctx.portas:
        parede = ctx.pavimento.parede(porta.parede)
        if parede is None:  # pragma: no cover - validação estrutural já acusa
            continue
        u, n = geometria.direcao(parede)
        lado = 1 if parede.lado_a == ctx.comodo.id else -1
        d = porta.distancia_inicio.valor + porta.largura.valor / 2
        meio_vao = Point(
            parede.inicio[0] + u[0] * d + n[0] * lado * parede.espessura.valor / 2,
            parede.inicio[1] + u[1] * d + n[1] * lado * parede.espessura.valor / 2,
        )
        comp = componente_em(meio_vao)
        if comp is None:
            ctx.add(
                Severidade.AVISO,
                "passagem_livre",
                f"em frente à porta '{porta.id}' não há passagem de {limite} mm",
                elemento=porta.id,
                regiao=meio_vao.buffer(meia),
            )
        elif principal is None:
            principal = comp
        elif not comp.equals(principal):
            ctx.add(
                Severidade.AVISO,
                "passagem_livre",
                f"não há passagem de {limite} mm entre a porta '{porta.id}' e as demais",
                elemento=porta.id,
                regiao=meio_vao.buffer(meia),
            )
    if principal is None:
        return
    for movel in ctx.moveis:
        lados = LADOS_DE_USO.get(movel.tipo, ("frente",))
        usos = [lado_local(movel, q) for q in lados]
        if not any(principal.distance(LineString(seg)) <= TOLERANCIA for seg, _ in usos):
            uso = "da frente" if lados == ("frente",) else "das laterais e dos pés"
            ctx.add(
                Severidade.AVISO,
                "passagem_livre",
                f"não há passagem de {limite} mm da porta até o lado de uso ({uso}) "
                f"de '{movel.nome or movel.id}'",
                elemento=movel.id,
                # área de uso que ficou sem passagem (frente; na cama, os pés)
                regiao=ctx.faixa(*usos[-1], limite).intersection(ctx.util),
            )


def porta_colide_movel(ctx: Contexto) -> None:
    """Folha de porta que abre para o cômodo não pode varrer um móvel."""
    for porta in ctx.portas:
        if porta.abre_para != ctx.comodo.id:
            continue
        giro = geometria.giro_porta(ctx.pavimento, porta)
        if giro is None:
            continue
        for movel in ctx.moveis:
            choque = giro.intersection(ctx.poligonos[movel.id])
            if choque.area > 1:
                ctx.add(
                    Severidade.ERRO,
                    "porta_colide_movel",
                    f"a porta '{porta.id}' bate em '{movel.nome or movel.id}' ao abrir",
                    elemento=porta.id,
                    regiao=choque,
                )


def instalacao_obstruida(ctx: Contexto) -> None:
    """Tomada/interruptor na parede com um móvel mais alto encostado na frente."""
    for inst in ctx.pavimento.instalacoes:
        if (
            not isinstance(inst, PontoInstalacao)
            or inst.tipo not in (TipoInstalacao.TOMADA, TipoInstalacao.INTERRUPTOR)
            or inst.parede not in ctx.comodo.paredes
            or inst.comodo not in (None, ctx.comodo.id)
        ):
            continue
        parede = ctx.pavimento.parede(inst.parede)
        if parede is None or ctx.comodo.id not in (parede.lado_a, parede.lado_b):
            continue
        _, n = geometria.direcao(parede)
        lado = 1 if parede.lado_a == ctx.comodo.id else -1
        meia = parede.espessura.valor / 2
        face = Point(inst.posicao[0] + n[0] * lado * meia, inst.posicao[1] + n[1] * lado * meia)
        for movel in ctx.moveis:
            perto = ctx.poligonos[movel.id].distance(face) <= ENCOSTA
            if perto and movel.altura.valor > inst.altura.valor:
                ctx.add(
                    Severidade.AVISO,
                    "instalacao_obstruida",
                    f"{inst.tipo.replace('_', ' ')} '{inst.id}' (h{inst.altura.valor}) fica "
                    f"atrás de '{movel.nome or movel.id}' (altura {movel.altura.valor})",
                    elemento=inst.id,
                    regiao=face.buffer(150),
                )


REGRAS: list[Regra] = [passagem_livre, porta_colide_movel, instalacao_obstruida]
