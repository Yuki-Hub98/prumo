"""Checagens das escadas do pavimento (limites em ``gerais.LIMITES``, sobrescritos pelo
``[geral]`` do ``regras.toml``)."""

from __future__ import annotations

from collections.abc import Mapping

from shapely.ops import unary_union

from interiores_core import escadas, geometria
from interiores_core.modelo import Escada, Pavimento, Projeto
from interiores_core.validacao import Problema, Severidade

SOBRA = 1000.0
"""Área (mm²) de escada dentro de parede tolerada (encostar não conta)."""


def _cm(mm: float) -> str:
    return f"{mm / 10:.1f}".replace(".", ",") + " cm"


def checar(projeto: Projeto, pav: Pavimento, limites: Mapping[str, int]) -> list[Problema]:
    problemas: list[Problema] = []
    paredes = unary_union([geometria.corpo(p) for p in pav.paredes if geometria.comprimento(p) > 0])
    acima = sorted(
        (p for p in projeto.pavimentos if p.cota_piso.valor > pav.cota_piso.valor),
        key=lambda p: p.cota_piso.valor,
    )
    contorno_pav = geometria.contorno_pavimento(pav)
    for e in pav.estrutura:
        if not isinstance(e, Escada):
            continue
        calc = escadas.calcular(pav, e)

        def add(sev: Severidade, codigo: str, msg: str, e: Escada = e) -> None:
            problemas.append(
                Problema(
                    severidade=sev,
                    codigo=codigo,
                    mensagem=f"escada '{e.id}': {msg}",
                    pavimento=pav.id,
                    elemento=e.id,
                    posicao=e.inicio,
                )
            )

        if not limites["escada_espelho_min"] <= calc.espelho <= limites["escada_espelho_max"]:
            add(
                Severidade.AVISO,
                "escada_espelho",
                f"espelho de {_cm(calc.espelho)} (confortável: {_cm(limites['escada_espelho_min'])}"
                f" a {_cm(limites['escada_espelho_max'])})",
            )
        if calc.piso < limites["escada_piso_min"]:
            add(
                Severidade.AVISO,
                "escada_piso",
                f"piso de {_cm(calc.piso)} (mínimo {_cm(limites['escada_piso_min'])})",
            )
        if not limites["escada_blondel_min"] <= calc.blondel <= limites["escada_blondel_max"]:
            faixa = f"{_cm(limites['escada_blondel_min'])} a {_cm(limites['escada_blondel_max'])}"
            add(
                Severidade.AVISO,
                "escada_blondel",
                f"2 × espelho + piso = {_cm(calc.blondel)} (passo confortável: {faixa})",
            )
        if e.largura.valor < limites["escada_largura_min"]:
            minimo = _cm(limites["escada_largura_min"])
            add(
                Severidade.AVISO,
                "escada_estreita",
                f"largura de {_cm(e.largura.valor)} (mínimo {minimo})",
            )
        if calc.contorno.intersection(paredes).area > SOBRA:
            add(Severidade.ERRO, "escada_na_parede", "atravessa uma parede")
        if contorno_pav is not None and not contorno_pav.buffer(1).contains(calc.contorno):
            add(Severidade.AVISO, "escada_fora", "sai para fora do pavimento")
        if acima:
            falta = acima[0].cota_piso.valor - pav.cota_piso.valor
            if abs(falta - calc.desnivel) > 10:
                add(
                    Severidade.AVISO,
                    "escada_desnivel",
                    f"vence {_cm(calc.desnivel)}, mas o andar '{acima[0].id}' está "
                    f"{_cm(falta)} acima",
                )
        pedido = e.degraus_primeiro_lance
        if e.forma in ("L", "U") and pedido and calc.lances[0] != pedido:
            add(
                Severidade.AVISO,
                "escada_lance",
                f"{pedido} pisos no 1º lance não cabem: ficaram {calc.lances[0]}",
            )
        if calc.giro and calc.giro > 0:
            por_volta = 360 / (calc.giro / len(calc.degraus)) * calc.espelho
            if calc.giro > 360 and por_volta < limites["escada_altura_livre"]:
                add(
                    Severidade.AVISO,
                    "escada_cabeca",
                    f"dá mais de uma volta e só tem {_cm(por_volta)} entre uma volta e a de "
                    f"cima (mínimo {_cm(limites['escada_altura_livre'])})",
                )
    return problemas
