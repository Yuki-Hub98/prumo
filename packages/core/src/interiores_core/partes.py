"""Partes de um móvel que podem ter cor própria (portas, gavetas, travesseiros...).

O móvel tem uma cor geral (o **corpo**) e, por cima, cor por parte nas variações
(``cores.pecas``). Este módulo diz quais partes cada móvel tem e a que parte pertence
cada peça que o render monta (nomes das peças em ``interiores_render.cena``).
"""

from __future__ import annotations

import itertools
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
    "bancada": "Bancada",
    "cuba": "Cuba",
    "torneira": "Torneira",
    "bocas": "Bocas e grelhas",
    "caixa": "Caixa acoplada",
    "vidros": "Vidros",
    "perfis": "Perfis",
    "estrutura": "Estrutura",
    "escada": "Escada",
    "base": "Base",
    "teclas": "Teclas",
    "mouse": "Mouse",
    "frente": "Painel da frente",
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
    Simbolo.PIA: ("bancada", "portas", "puxadores", "cuba", "torneira"),
    Simbolo.FOGAO: ("tampo", "bocas", "portas", "puxadores"),
    Simbolo.GELADEIRA: ("portas", "puxadores"),
    Simbolo.VASO: ("assento", "caixa"),
    Simbolo.BOX: ("vidros", "perfis"),
    Simbolo.BELICHE: ("estrutura", "escada", "colchao", "roupa_de_cama"),
    Simbolo.CADEIRA_GIRATORIA: ("assento", "encosto", "base"),
    Simbolo.MAQUINA: ("portas",),
    Simbolo.MONITOR: ("moldura", "base"),
    Simbolo.NOTEBOOK: ("moldura", "teclas"),
    Simbolo.GABINETE: ("frente",),
    Simbolo.TECLADO: ("teclas", "mouse"),
    Simbolo.BANCADA: ("tampo", "pes"),
}
PLANEJADO: tuple[str, ...] = ("portas", "gavetas", "puxadores", "prateleiras")
"""Móvel planejado (com ``construcao``): caixa = corpo; portas, frentes de gaveta,
puxadores e prateleiras (as que ficam à vista nos nichos sem porta) à parte."""

_REGRAS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(padrao), parte)
    for padrao, parte in (
        (r"^(folha|porta)\d+$", "portas"),
        (r"^gaveta\d+$", "gavetas"),
        (r"^puxador\d+$", "puxadores"),
        (r"^prateleira\d+$", "prateleiras"),
        (r"^cabeceira$", "cabeceira"),
        (r"^colchao\d*$", "colchao"),
        (r"^(edredom|dobra)\d*$", "roupa_de_cama"),
        (r"^(poste|grade|estrado)\d*$", "estrutura"),
        (r"^(degrau|banzo)\d*$", "escada"),
        (r"^(pata|coluna|rodizio|suporte)\d*$", "base"),
        (r"^travesseiro\d*$", "travesseiros"),
        (r"^(almofada|encosto)\d+$", "almofadas"),  # sofá: almofadas do assento e das costas
        (r"^encosto(-l)?$", "encosto"),  # sofá em L: costas e lateral
        (r"^braco-[ed]$", "bracos"),
        (r"^assento$", "assento"),
        (r"^tampo(-l)?$", "tampo"),
        (r"^(pe|perna|painel)\d+$", "pes"),
        (r"^(moldura|tampa)$", "moldura"),
        (r"^teclas\d*$", "teclas"),
        (r"^mouse$", "mouse"),
        (r"^frente$", "frente"),
        (r"^bancada$", "bancada"),
        (r"^cuba$", "cuba"),
        (r"^torneira\d*$", "torneira"),
        (r"^boca\d+$", "bocas"),
        (r"^caixa$", "caixa"),
        (r"^vidro\d+$", "vidros"),
        (r"^perfil\d*$", "perfis"),
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
    if m.bancada is not None:  # tampo, pernas/painéis e o que os módulos tiverem
        return ("tampo", "pes", *_partes_dos_modulos(m))
    item = item_do_tipo(m.tipo)
    simbolo = item.simbolo if item else Simbolo.GENERICO
    if simbolo is Simbolo.FOGAO and eh_cooktop(m):
        return ("tampo", "bocas")  # sem forno: sem porta nem puxador
    if simbolo is Simbolo.VASO and m.altura.valor < ALTURA_MIN_CAIXA:
        return ("assento",)  # suspenso: caixa embutida na parede
    partes = POR_SIMBOLO[simbolo]
    if m.pes == "rodape":  # sem pé: o rodapé recuado é do corpo
        partes = tuple(p for p in partes if p != "pes")
    return partes


ALTURA_MIN_CAIXA = 500
"""Vaso mais baixo que isto (mm) é suspenso: caixa embutida, sem caixa acoplada."""

ALTURA_MAX_COOKTOP = 200
"""Fogão mais baixo que isto (mm) é cooktop: só o tampo com as bocas, na bancada."""


def eh_cooktop(m: Movel) -> bool:
    return m.altura.valor < ALTURA_MAX_COOKTOP


def _partes_dos_modulos(m: Movel) -> tuple[str, ...]:
    """Partes que aparecem nos módulos da bancada (na ordem de ``PLANEJADO``)."""
    assert m.bancada is not None
    tem: set[str] = set()
    for mod in m.bancada.modulos:
        for vao in mod.construcao.vaos:
            tipos = [e.tipo for e in vao.espacos]
            fechado = mod.portas == "abrir" and vao.porta
            if fechado:
                tem |= {"portas", "puxadores"}
            if "gaveta" in tipos and not fechado:
                tem |= {"gavetas", "puxadores"}
            entre = [a != "gaveta" or b != "gaveta" for a, b in itertools.pairwise(tipos)]
            if not fechado and any(entre):
                tem.add("prateleiras")
    return tuple(p for p in PLANEJADO if p in tem)
