"""Checagens de uso dos cômodos: regras gerais + regras do tipo (``core/tipos``).

Os limites são padrões configuráveis: o ``regras.toml`` do projeto sobrescreve,
na seção ``[geral]`` (vale para todo cômodo) ou ``[<tipo>]`` (só aquele tipo).
"""

from __future__ import annotations

from collections.abc import Mapping

from shapely import Polygon
from shapely.geometry.base import BaseGeometry

from interiores_core import geometria
from interiores_core.modelo import DadosComodo, Projeto, TipoComodo
from interiores_core.regras import escadas, gerais
from interiores_core.regras.contexto import Contexto
from interiores_core.tipos import modulo_do_tipo
from interiores_core.validacao import ORDEM_SEVERIDADE, Problema, Severidade

SECAO_GERAL = "geral"
VERSAO_REGRAS = "regras v2"
"""Suba quando o resultado de alguma checagem mudar: invalida o cache das saídas."""


def limites_do_tipo(
    tipo: str, regras: Mapping[str, object] | None = None
) -> tuple[dict[str, int], list[Problema]]:
    """Limites efetivos de um tipo: padrões gerais e do tipo, sobrescritos pelo toml.

    Ordem: geral (padrão) ← ``[geral]`` ← tipo (padrão) ← ``[<tipo>]``.
    """
    modulo = modulo_do_tipo(tipo)
    padrao_tipo = dict(modulo.LIMITES) if modulo else {}
    limites = dict(gerais.LIMITES)
    problemas: list[Problema] = []
    regras = regras or {}
    for secao, padrao in ((SECAO_GERAL, {}), (tipo, padrao_tipo)):
        limites.update(padrao)
        valores = regras.get(secao)
        if not isinstance(valores, dict):
            continue
        conhecidas = {**gerais.LIMITES, **padrao}
        for chave, valor in valores.items():
            if chave not in conhecidas:
                continue  # acusado em validar_regras
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
                problemas.append(
                    Problema(
                        severidade=Severidade.ERRO,
                        codigo="regra_invalida",
                        mensagem=f"regras.toml [{secao}] {chave} = {valor!r}: use mm inteiros",
                    )
                )
                continue
            limites[chave] = valor
    return limites, problemas


def validar_regras(regras: Mapping[str, object]) -> list[Problema]:
    """Seções e chaves do ``regras.toml`` que não correspondem a nenhuma regra."""
    problemas = []
    for secao, valores in regras.items():
        if secao != SECAO_GERAL and secao not in set(TipoComodo):
            problemas.append(
                Problema(
                    severidade=Severidade.AVISO,
                    codigo="regra_desconhecida",
                    mensagem=f"regras.toml: seção [{secao}] não é 'geral' nem tipo de cômodo",
                )
            )
            continue
        if not isinstance(valores, dict):
            continue
        modulo = modulo_do_tipo(secao) if secao != SECAO_GERAL else None
        conhecidas = {**gerais.LIMITES, **(modulo.LIMITES if modulo else {})}
        for chave in valores:
            if chave not in conhecidas:
                problemas.append(
                    Problema(
                        severidade=Severidade.AVISO,
                        codigo="regra_desconhecida",
                        mensagem=f"regras.toml [{secao}] {chave}: limite desconhecido "
                        f"(conhecidos: {', '.join(sorted(conhecidas))})",
                    )
                )
    return problemas


def _maior_poligono(geom: BaseGeometry) -> Polygon | None:
    if isinstance(geom, Polygon):
        return None if geom.is_empty else geom
    partes = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    return max(partes, key=lambda g: g.area, default=None)


def checar(
    projeto: Projeto,
    dados_comodos: Mapping[str, DadosComodo] | None = None,
    regras: Mapping[str, object] | None = None,
    comodo: str | None = None,
) -> list[Problema]:
    """Roda as checagens de uso em todos os cômodos (ou só em ``comodo``).

    Cômodos que não fecham são pulados: a validação estrutural já acusa.
    """
    dados_comodos = dados_comodos or {}
    regras = regras or {}
    problemas = validar_regras(regras) if comodo is None else []
    vistos: set[str] = set()
    for pav in projeto.pavimentos:
        for c in pav.comodos:
            if comodo is not None and c.id != comodo:
                continue
            util = geometria.poligono_util(pav, c)
            if util is None:
                continue
            alvo = _maior_poligono(util)
            if alvo is None:
                continue
            limites, invalidos = limites_do_tipo(c.tipo, regras)
            for p in invalidos:
                if p.mensagem not in vistos:
                    vistos.add(p.mensagem)
                    problemas.append(p)
            moveis = dados_comodos[c.id].moveis if c.id in dados_comodos else []
            ctx = Contexto(pav, c, alvo, list(moveis), limites)
            modulo = modulo_do_tipo(c.tipo)
            for regra in [*gerais.REGRAS, *(modulo.REGRAS if modulo else [])]:
                regra(ctx)
            problemas += ctx.problemas
        if comodo is None:  # escadas: do pavimento, não de um cômodo
            limites, _ = limites_do_tipo("geral", regras)
            problemas += escadas.checar(projeto, pav, limites)
    return sorted(problemas, key=lambda p: ORDEM_SEVERIDADE[p.severidade])
