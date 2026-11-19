"""Desfazer, refazer e voltar para uma versão, sobre o histórico de versões.

Voltar nunca apaga nada: o conteúdo do ``snapshot`` da versão alvo é gravado como
**versão nova**, com a operação ``desfazer:N``, ``refazer:N`` ou ``reverter:N`` (N =
versão cujo conteúdo foi restaurado). Assim o próprio desfazer pode ser refeito e o
histórico conta tudo o que aconteceu.

As funções daqui só olham as operações de cada versão (``{versao: operacao}``):

- **desfazer** volta ao estado anterior à última edição. Se a versão atual já é um
  desfazer/refazer (conteúdo igual ao da versão N), desfazer de novo é desfazer N;
- **refazer** só existe logo depois de desfazer(es): volta ao estado de antes do
  desfazer mais recente ainda não refeito. Qualquer outra edição zera o refazer;
- **reverter** (voltar para uma versão escolhida no histórico) conta como edição
  comum: desfazê-lo volta para antes dele.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

Tipo = Literal["desfazer", "refazer", "reverter"]
TIPOS: tuple[Tipo, ...] = ("desfazer", "refazer", "reverter")


def operacao(tipo: Tipo, para: int) -> str:
    """Nome gravado no histórico, ex.: ``desfazer:9``."""
    return f"{tipo}:{para}"


def ler_operacao(op: str | None) -> tuple[Tipo, int] | None:
    """``("desfazer", 9)`` para ``desfazer:9``; ``None`` para as outras operações."""
    if not op or ":" not in op:
        return None
    tipo, _, numero = op.partition(":")
    if tipo not in TIPOS or not numero.isdigit():
        return None
    return tipo, int(numero)


def alvo_desfazer(ops: Mapping[int, str | None], versao: int) -> int | None:
    """Versão cujo conteúdo o desfazer restaura (``None``: nada a desfazer)."""
    while True:
        lida = ler_operacao(ops.get(versao))
        if lida is not None and lida[0] in ("desfazer", "refazer") and lida[1] < versao:
            versao = lida[1]  # mesmo conteúdo da versão N: desfazer é desfazer N
            continue
        return versao - 1 if versao > 1 else None


def alvo_refazer(ops: Mapping[int, str | None], versao: int) -> int | None:
    """Versão cujo conteúdo o refazer restaura (``None``: nada a refazer)."""
    pendentes = 0  # refazeres já feitos, que "gastam" os desfazeres mais antigos
    while versao >= 1:
        lida = ler_operacao(ops.get(versao))
        if lida is None or lida[0] == "reverter":
            return None
        if lida[0] == "refazer":
            pendentes += 1
        elif pendentes:
            pendentes -= 1
        else:
            return versao - 1  # o estado logo antes deste desfazer
        versao -= 1
    return None
