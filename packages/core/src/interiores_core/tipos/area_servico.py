"""Regras da área de serviço (CLAUDE.md §6, "Por tipo de cômodo").

- **máquina e tanque com água e esgoto**: ponto de água fria e de esgoto a menos de
  ``ponto_max`` de cada um (erro);
- **falta máquina ou tanque**: o cômodo existe mas ainda não tem lugar para eles (info, para
  lembrar de reservar o espaço).
"""

from __future__ import annotations

from interiores_core.regras.contexto import Contexto, Regra, de_tipo
from interiores_core.validacao import Severidade

LIMITES = {"ponto_max": 300}
"""Padrões em mm; o ``regras.toml`` do projeto pode sobrescrever (seção ``[area_servico]``)."""

NOMES = {"maquina_lavar": "máquina de lavar", "tanque": "tanque"}


def pontos_de_agua(ctx: Contexto) -> None:
    """Máquina e tanque: água fria e esgoto a menos de ``ponto_max``."""
    limite = ctx.limites["ponto_max"]
    for tipo, nome in NOMES.items():
        for m in de_tipo(ctx.moveis, tipo):
            pol = ctx.poligonos[m.id]
            for inst, rotulo in (("agua_fria", "água fria"), ("esgoto", "esgoto")):
                if not any(pol.distance(p) <= limite for p in ctx.instalacoes(inst)):
                    ctx.add(
                        Severidade.ERRO,
                        f"{tipo}_sem_{inst}",
                        f"{nome} '{m.nome or m.id}' sem ponto de {rotulo} a menos de {limite} mm",
                        elemento=m.id,
                        regiao=pol.buffer(limite),
                    )


def espaco_para_maquina_e_tanque(ctx: Contexto) -> None:
    """Área de serviço sem máquina ou sem tanque: lembra de reservar o espaço."""
    faltando = [nome for tipo, nome in NOMES.items() if not de_tipo(ctx.moveis, tipo)]
    if faltando:
        ctx.add(
            Severidade.INFO,
            "area_servico_incompleta",
            f"área de serviço sem {' nem '.join(faltando)}: reserve o espaço (e os pontos de "
            "água e esgoto)",
        )


REGRAS: list[Regra] = [pontos_de_agua, espaco_para_maquina_e_tanque]
