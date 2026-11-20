"""Acabamento, puxador e pés dos móveis: opções (nomes para a tela) e o que cada uma é.

Só visual (3D e render); não muda medidas nem checagens. A cor da variação do cômodo continua
valendo por cima do acabamento (ele dá a textura e a cor padrão).
"""

from __future__ import annotations

from dataclasses import dataclass

from interiores_core.modelo import Movel
from interiores_core.partes import partes_do_movel


@dataclass(frozen=True)
class Acabamento:
    nome: str
    cor: str
    """Cor padrão (hex), quando a variação não pinta o móvel."""
    textura: str | None
    """``madeira`` (com veios), ``madeira_lisa`` (MDF amadeirado, sem tábuas) ou nenhuma."""
    rugosidade: float


ACABAMENTOS: dict[str, Acabamento] = {
    "madeira_clara": Acabamento("Madeira clara", "#C8A27A", "madeira", 0.55),
    "madeira_escura": Acabamento("Madeira escura", "#5C3F2B", "madeira", 0.5),
    "amadeirado": Acabamento("MDF amadeirado", "#A9825E", "madeira_lisa", 0.45),
    "branco_fosco": Acabamento("Branco fosco", "#F2F0EC", None, 0.65),
    "laca_brilho": Acabamento("Laca com brilho", "#F7F7F5", None, 0.12),
    "preto_fosco": Acabamento("Preto fosco", "#2B2B2B", None, 0.6),
}
PUXADORES: dict[str, str] = {
    "barra": "Barra",
    "botao": "Botão",
    "perfil": "Perfil de alumínio",
    "cava": "Cava (sem puxador)",
}
PES: dict[str, str] = {
    "quadrado": "Quadrado",
    "palito": "Palito",
    "metalico": "Metálico fino",
    "rodape": "Sem pé (rodapé recuado)",
}


def opcoes_do_movel(m: Movel) -> tuple[str, ...]:
    """Quais escolhas fazem sentido neste móvel: acabamento sempre; puxador se tem portas ou
    gavetas; pés se o tipo tem pés."""
    partes = partes_do_movel(m)
    saida = ["acabamento"]
    if "puxadores" in partes:
        saida.append("puxador")
    if "pes" in partes:
        saida.append("pes")
    return tuple(saida)
