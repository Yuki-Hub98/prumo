"""Partes de um móvel que podem ter cor própria (portas, gavetas, travesseiros...).

O móvel tem uma cor geral (o **corpo**) e, por cima, cor por parte nas variações
(``cores.pecas``). Este módulo diz quais partes cada móvel tem e a que parte pertence
cada peça que o render monta (nomes das peças em ``interiores_render.cena``).
"""

from __future__ import annotations

import re

from interiores_core.catalogo import Simbolo, item_do_tipo
from interiores_core.modelo import Movel

CORPO = "corpo"
"""Tudo o que não é uma parte com cor própria: usa a cor geral do móvel."""

PARTES: dict[str, str] = {
    "portas": "Portas",
    "gavetas": "Gavetas",
    "puxadores": "Puxadores",
    "prateleiras": "Prateleiras",
    "cabeceira": "Cabeceira",
    "colchao": "Colchão",
    "roupa_de_cama": "Roupa de cama (edredom)",
    "travesseiros": "Travesseiros",
    "almofadas": "Almofadas",
    "encosto": "Encosto",
    "bracos": "Braços",
    "assento": "Assento",
    "tampo": "Tampo",
    "pes": "Pés",
    "moldura": "Moldura",
}
"""Id → nome para a tela, na ordem em que aparecem."""

POR_SIMBOLO: dict[Simbolo, tuple[str, ...]] = {
    Simbolo.CAMA: ("cabeceira", "colchao", "roupa_de_cama", "travesseiros"),
    Simbolo.PORTAS: ("portas", "puxadores"),
    Simbolo.GAVETAS: ("gavetas", "puxadores", "pes"),
    Simbolo.PRATELEIRAS: ("prateleiras",),
    Simbolo.ASSENTO: ("almofadas", "encosto", "bracos", "pes"),
    Simbolo.CADEIRA: ("assento", "encosto", "pes"),
    Simbolo.MESA: ("tampo", "pes"),
    Simbolo.TELA: ("moldura",),
    Simbolo.GENERICO: (),
}
PLANEJADO: tuple[str, ...] = ("portas", "puxadores")
"""Móvel planejado (com ``construcao``): caixa = corpo; portas e puxadores à parte."""

_REGRAS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(padrao), parte)
    for padrao, parte in (
        (r"^(folha|porta)\d+$", "portas"),
        (r"^gaveta\d+$", "gavetas"),
        (r"^puxador\d+$", "puxadores"),
        (r"^prateleira\d+$", "prateleiras"),
        (r"^cabeceira$", "cabeceira"),
        (r"^colchao$", "colchao"),
        (r"^(edredom|dobra)$", "roupa_de_cama"),
        (r"^travesseiro\d*$", "travesseiros"),
        (r"^(almofada|encosto)\d+$", "almofadas"),  # sofá: almofadas do assento e das costas
        (r"^encosto$", "encosto"),
        (r"^braco-[ed]$", "bracos"),
        (r"^assento$", "assento"),
        (r"^tampo$", "tampo"),
        (r"^pe\d+$", "pes"),
        (r"^moldura$", "moldura"),
    )
)


def parte_da_peca(peca: str) -> str:
    """Parte de uma peça do render (``porta0`` → ``portas``); o resto é ``corpo``."""
    for padrao, parte in _REGRAS:
        if padrao.match(peca):
            return parte
    return CORPO


def partes_do_movel(m: Movel) -> tuple[str, ...]:
    """Partes com cor própria que este móvel tem (sem o corpo)."""
    if m.construcao is not None:
        return PLANEJADO
    item = item_do_tipo(m.tipo)
    return POR_SIMBOLO[item.simbolo if item else Simbolo.GENERICO]
