"""Edição do mobiliário em ``comodos/<comodo>.json`` (usada pela CLI e, depois, pela API).

Toda edição valida o resultado com o modelo antes de gravar e mantém a
formatação do arquivo (``indent=2``, UTF-8, quebra de linha no fim).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from interiores_core.geometria import na_parede
from interiores_core.modelo import DadosComodo, Projeto


def _arquivo(pasta: Path, comodo: str) -> Path:
    return pasta / "comodos" / f"{comodo}.json"


def _projeto(pasta: Path) -> Projeto:
    return Projeto.model_validate_json((pasta / "projeto.json").read_text(encoding="utf-8"))


def _ler(pasta: Path, comodo: str) -> dict[str, Any]:
    if _projeto(pasta).pavimento_do_comodo(comodo) is None:
        raise KeyError(f"cômodo '{comodo}' não existe no projeto")
    arq = _arquivo(pasta, comodo)
    if not arq.exists():
        return {"schema_version": 1, "comodo": comodo, "moveis": []}
    dados: dict[str, Any] = json.loads(arq.read_text(encoding="utf-8"))
    return dados


def _gravar(pasta: Path, comodo: str, dados: dict[str, Any]) -> DadosComodo:
    validado = DadosComodo.model_validate(dados)  # levanta ValidationError antes de gravar
    arq = _arquivo(pasta, comodo)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return validado


def _indice(dados: dict[str, Any], id_: str) -> int:
    for i, m in enumerate(dados["moveis"]):
        if m.get("id") == id_:
            return i
    raise KeyError(f"móvel '{id_}' não existe neste cômodo")


def id_livre(pasta: Path | str, comodo: str, base: str) -> str:
    """``base`` (em minúsculas, com hífen) se estiver livre; senão ``base-2``, ``base-3``..."""
    base = re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-") or "movel"
    usados = {m.get("id") for m in _ler(Path(pasta), comodo)["moveis"]}
    if base not in usados:
        return base
    n = 2
    while f"{base}-{n}" in usados:
        n += 1
    return f"{base}-{n}"


def encostar(
    pasta: Path | str, comodo: str, movel: dict[str, Any], parede: str, distancia: int
) -> dict[str, Any]:
    """Põe ``movel`` (dict) com as costas na parede, virado para o cômodo.

    Ajusta ``centro`` e ``rotacao`` a partir da largura e da profundidade do próprio
    móvel. Ver :func:`interiores_core.geometria.na_parede`.
    """
    projeto = _projeto(Path(pasta))
    pav = projeto.pavimento_do_comodo(comodo)
    if pav is None:
        raise KeyError(f"cômodo '{comodo}' não existe no projeto")
    centro, rotacao = na_parede(
        pav,
        comodo,
        parede,
        distancia,
        movel["largura"]["valor"],
        movel["profundidade"]["valor"],
    )
    movel["centro"], movel["rotacao"] = list(centro), rotacao
    return movel


def adicionar_movel(pasta: Path | str, comodo: str, movel: dict[str, Any]) -> DadosComodo:
    """Acrescenta um móvel (ex.: de :func:`interiores_core.catalogo.novo_movel`)."""
    pasta = Path(pasta)
    dados = _ler(pasta, comodo)
    if any(m.get("id") == movel.get("id") for m in dados["moveis"]):
        raise ValueError(f"já existe um móvel '{movel.get('id')}' neste cômodo")
    dados["moveis"].append(movel)
    return _gravar(pasta, comodo, dados)


def mover_movel(
    pasta: Path | str,
    comodo: str,
    id_: str,
    centro: tuple[int, int] | None = None,
    rotacao: int | None = None,
    parede: str | None = None,
    distancia: int = 0,
) -> DadosComodo:
    """Muda a posição e/ou a rotação de um móvel, ou o encosta numa parede."""
    pasta = Path(pasta)
    dados = _ler(pasta, comodo)
    movel = dados["moveis"][_indice(dados, id_)]
    if parede is not None:
        encostar(pasta, comodo, movel, parede, distancia)
    if centro is not None:
        movel["centro"] = list(centro)
    if rotacao is not None:
        movel["rotacao"] = rotacao
    return _gravar(pasta, comodo, dados)


def remover_movel(pasta: Path | str, comodo: str, id_: str) -> DadosComodo:
    pasta = Path(pasta)
    dados = _ler(pasta, comodo)
    del dados["moveis"][_indice(dados, id_)]
    return _gravar(pasta, comodo, dados)
