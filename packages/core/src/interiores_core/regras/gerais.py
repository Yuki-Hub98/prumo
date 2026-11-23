"""Checagens que valem para todo cômodo (CLAUDE.md §6, "Gerais")."""

from __future__ import annotations

from shapely import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from interiores_core import catalogo, geometria, planejado
from interiores_core.modelo import Movel, PontoInstalacao, TipoInstalacao
from interiores_core.regras.contexto import Contexto, Regra, lado_local
from interiores_core.validacao import Severidade

LIMITES = {
    "passagem_livre": 700,
    "distancia_tela_pct": 150,
    "prateleira_vao_max": 900,
    "cabideiro_altura_min": 1000,
    "cabideiro_profundidade_min": 550,
    "gaveta_largura_min": 300,
}
"""Padrões; o ``regras.toml`` do projeto pode sobrescrever.

- ``passagem_livre``: mm;
- ``distancia_tela_pct``: distância mínima da tela até quem assiste, em % da
  diagonal (150 = 1,5 × a diagonal);
- móveis planejados (mm): vão máximo de prateleira sem apoio no meio (referência
  para MDF 18 mm com carga leve), altura
  mínima do espaço de cabideiro, profundidade mínima do móvel com cabideiro
  (cabide ~450 + folga) e largura mínima de vão com gaveta.
"""

TOLERANCIA = 10.0
"""Folga numérica (mm) ao testar se uma área livre encosta num ponto."""

SOBRA = 100.0
"""Área (mm²) de sobreposição tolerada (arredondamento de medidas)."""

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
        lados = catalogo.lados_de_uso(movel.tipo)
        if not lados or not movel.ocupa_piso:
            continue  # não precisa de acesso (TV na parede, armário aéreo)
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
            if not movel.ocupa_piso:
                continue
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
            base = movel.elevacao.valor if movel.elevacao else 0
            if perto and base <= inst.altura.valor < base + movel.altura.valor:
                ctx.add(
                    Severidade.AVISO,
                    "instalacao_obstruida",
                    f"{inst.tipo.replace('_', ' ')} '{inst.id}' (h{inst.altura.valor}) fica "
                    f"atrás de '{movel.nome or movel.id}' (de {base} a {base + movel.altura.valor} "
                    "do piso)",
                    elemento=inst.id,
                    regiao=face.buffer(150),
                )


def distancia_tela(ctx: Contexto) -> None:
    """TV perto demais de quem assiste: mínimo ``distancia_tela_pct`` % da diagonal.

    Quem assiste: móveis-assento do catálogo (sofá, poltrona, cama) à frente da
    tela. A distância vai do meio da tela até o ponto mais próximo do assento.
    """
    fator = ctx.limites["distancia_tela_pct"] / 100
    assentos = [m for m in ctx.moveis if (i := catalogo.item_do_tipo(m.tipo)) and i.assento]
    for tv in ctx.moveis:
        item = catalogo.item_do_tipo(tv.tipo)
        if item is None or item.simbolo is not catalogo.Simbolo.TELA or tv.polegadas is None:
            continue
        (a, b), (dx, dy) = lado_local(tv, "frente")
        meio = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        minimo = fator * tv.polegadas * 25.4
        for assento in assentos:
            alvo = ctx.poligonos[assento.id]
            c = alvo.centroid
            if (c.x - meio.x) * dx + (c.y - meio.y) * dy <= 0:
                continue  # atrás da tela
            dist = meio.distance(alvo)
            if dist < minimo:
                perto, _ = nearest_points(alvo, meio)
                ctx.add(
                    Severidade.AVISO,
                    "distancia_tela",
                    f"'{tv.nome or tv.id}' ({tv.polegadas}\") a {dist:.0f} mm de "
                    f"'{assento.nome or assento.id}'; mínimo {minimo:.0f} "
                    f"({fator:g} × a diagonal)",
                    elemento=tv.id,
                    regiao=LineString([meio, perto]).buffer(40),
                )


def _faixa_altura(m: Movel) -> tuple[int, int]:
    base = m.elevacao.valor if m.elevacao else 0
    return base, base + m.altura.valor


TAMPO_MESA = 40
"""mm: espessura do tampo considerada; abaixo dela, o vão da mesa fica livre."""


def _cabe_embaixo(mesa: Movel, outro: Movel) -> bool:
    """``outro`` fica no vão de uma mesa (pés à vista, sem construção): o tampo é que ocupa
    o espaço; embaixo dele cabe o gabinete, o puff, o gaveteiro..."""
    item = catalogo.item_do_tipo(mesa.tipo)
    if item is None or item.simbolo is not catalogo.Simbolo.MESA or mesa.construcao:
        return False
    return _faixa_altura(outro)[1] <= _faixa_altura(mesa)[1] - TAMPO_MESA


def moveis_no_lugar(ctx: Contexto) -> None:
    """Móvel entrando na parede/fora do cômodo, ou dois móveis no mesmo lugar.

    Dois móveis colidem se se sobrepõem na planta **e** nas faixas de altura; o vão
    debaixo do tampo de uma mesa é livre para o que couber nele.
    """
    for movel in ctx.moveis:
        fora = ctx.poligonos[movel.id].intersection(ctx.fora)
        if fora.area > SOBRA:
            ctx.add(
                Severidade.ERRO,
                "movel_fora_do_comodo",
                f"'{movel.nome or movel.id}' entra {fora.area / 1e4:.0f} cm² na parede "
                "ou fora do cômodo",
                elemento=movel.id,
                regiao=fora,
            )
    for i, a in enumerate(ctx.moveis):
        for b in ctx.moveis[i + 1 :]:
            (a0, a1), (b0, b1) = _faixa_altura(a), _faixa_altura(b)
            if a1 <= b0 or b1 <= a0:
                continue  # um acima do outro (ex.: TV na parede sobre o rack)
            if _cabe_embaixo(a, b) or _cabe_embaixo(b, a):
                continue  # debaixo da mesa (ex.: gabinete sob a escrivaninha)
            junto = ctx.poligonos[a.id].intersection(ctx.poligonos[b.id])
            if junto.area > SOBRA:
                ctx.add(
                    Severidade.AVISO,
                    "moveis_sobrepostos",
                    f"'{a.nome or a.id}' e '{b.nome or b.id}' ocupam o mesmo lugar",
                    elemento=a.id,
                    regiao=junto,
                )


def planejados(ctx: Contexto) -> None:
    """Construção dos móveis planejados: cabe no móvel e respeita os limites de uso."""
    for movel in ctx.moveis:
        if movel.construcao is None:
            continue
        nome = movel.nome or movel.id
        regiao = ctx.poligonos[movel.id]
        try:
            calc = planejado.calcular(movel)
        except planejado.ConstrucaoInvalidaError as e:
            ctx.add(Severidade.ERRO, "construcao_invalida", f"'{nome}': {e}", movel.id, regiao)
            continue
        lim = ctx.limites
        for i, (vao, w) in enumerate(zip(movel.construcao.vaos, calc.larguras_vaos, strict=True)):
            tipos = [esp.tipo for esp in vao.espacos]
            onde = f"'{nome}', vão {i + 1} ({w:.0f} mm)"
            if (
                w > lim["prateleira_vao_max"]
                and len(tipos) > 1
                and tipos != ["gaveta"] * len(tipos)
            ):
                ctx.add(
                    Severidade.AVISO,
                    "prateleira_longa",
                    f"{onde}: prateleira sem apoio acima de {lim['prateleira_vao_max']} mm "
                    "tende a envergar; divida o vão",
                    movel.id,
                    regiao,
                )
            if "gaveta" in tipos and w < lim["gaveta_largura_min"]:
                ctx.add(
                    Severidade.AVISO,
                    "gaveta_estreita",
                    f"{onde}: gaveta com menos de {lim['gaveta_largura_min']} mm de vão",
                    movel.id,
                    regiao,
                )
            for esp, h in zip(vao.espacos, calc.alturas[i], strict=True):
                if esp.tipo == "cabideiro" and h < lim["cabideiro_altura_min"]:
                    ctx.add(
                        Severidade.AVISO,
                        "cabideiro_baixo",
                        f"{onde}: cabideiro com {h:.0f} mm de altura; mínimo "
                        f"{lim['cabideiro_altura_min']} para camisas",
                        movel.id,
                        regiao,
                    )
        com_cabide = any(e.tipo == "cabideiro" for v in movel.construcao.vaos for e in v.espacos)
        if com_cabide and movel.profundidade.valor < lim["cabideiro_profundidade_min"]:
            ctx.add(
                Severidade.AVISO,
                "cabideiro_raso",
                f"'{nome}': {movel.profundidade.valor} mm de profundidade não comporta "
                f"cabide (mínimo {lim['cabideiro_profundidade_min']})",
                movel.id,
                regiao,
            )


REGRAS: list[Regra] = [
    moveis_no_lugar,
    planejados,
    passagem_livre,
    porta_colide_movel,
    instalacao_obstruida,
    distancia_tela,
]
