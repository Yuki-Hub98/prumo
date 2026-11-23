"""Edição do mobiliário de um cômodo (``comodos/<id>.json``), em funções puras.

Mesmo padrão de :mod:`interiores_core.edicao`: recebem o projeto e os dados do
cômodo, devolvem uma :class:`EdicaoMoveis` com os dados novos, as alterações
(antes → depois, com o caminho ``comodos.<id>.moveis[<móvel>]...``) e os problemas
do cômodo (validação + checagens de uso: passagem, lateral da cama, frente do
guarda-roupa, giro de porta, tomada atrás de móvel, distância sofá-TV...).

Quem grava é o chamador (API: banco + exportação; CLI: :mod:`interiores_core.editar`).
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from interiores_core import bancada, catalogo, geometria, planejado
from interiores_core.edicao import (
    Alteracao,
    EdicaoInvalidaError,
    diferencas,
    registrar_anterior,
)
from interiores_core.medidas import Medida
from interiores_core.modelo import DadosComodo, Movel, Projeto
from interiores_core.modelos_proprios import movel_do_modelo
from interiores_core.regras import checar
from interiores_core.validacao import Problema, Severidade, validar

Dados = dict[str, Any]

CAMPOS_MEDIDA = {"largura", "profundidade", "altura", "elevacao", "largura_porta", "raio", "braco"}
CAMPOS_MOVEL = CAMPOS_MEDIDA | {
    "nome", "modelo", "portas", "polegadas", "forma", "lado_l", "acabamento", "puxador", "pes",
}  # fmt: skip
"""Campos editáveis com :func:`alterar_movel` (posição e giro: :func:`mover_movel`)."""


@dataclass(frozen=True)
class EdicaoMoveis:
    dados: DadosComodo
    alteracoes: list[Alteracao]
    problemas: list[Problema]
    """Problemas do cômodo depois da edição (validação + checagens de uso)."""
    novos: list[Problema] = field(default_factory=list)


def _chave(p: Problema) -> tuple[str, str | None, str | None]:
    return (p.codigo, p.comodo, p.elemento)


def _problemas(
    projeto: Projeto, comodo: str, dados: DadosComodo, regras: Mapping[str, object]
) -> list[Problema]:
    todos = validar(projeto, {comodo: dados}) + checar(projeto, {comodo: dados}, regras, comodo)
    return [p for p in todos if p.comodo == comodo]


def _aplicar(
    projeto: Projeto,
    comodo: str,
    dados: DadosComodo | None,
    regras: Mapping[str, object] | None,
    mudar: Any,
) -> EdicaoMoveis:
    if projeto.pavimento_do_comodo(comodo) is None:
        raise KeyError(f"cômodo '{comodo}' não existe no projeto")
    regras = regras or {}
    base = dados or DadosComodo(schema_version=1, comodo=comodo)
    antes = base.model_dump(mode="json", exclude_none=True)
    depois = copy.deepcopy(antes)
    mudar(depois)
    try:
        novo = DadosComodo.model_validate(depois)
    except ValidationError as e:
        raise EdicaoInvalidaError(f"dados inválidos: {e}") from e
    ja_havia = {_chave(p) for p in _problemas(projeto, comodo, base, regras)}
    problemas = _problemas(projeto, comodo, novo, regras)
    novos = [p for p in problemas if _chave(p) not in ja_havia]
    repetidos = [p for p in novos if p.severidade is Severidade.ERRO and p.codigo == "id_duplicado"]
    if repetidos:
        raise EdicaoInvalidaError("; ".join(str(p) for p in repetidos))
    alteracoes = [
        Alteracao(f"comodos.{comodo}.{a.caminho}", a.antes, a.depois)
        for a in diferencas(antes, depois)
    ]
    return EdicaoMoveis(novo, alteracoes, problemas, novos)


def _indice(dados: Dados, id_: str) -> int:
    for i, m in enumerate(dados["moveis"]):
        if m["id"] == id_:
            return i
    raise KeyError(f"móvel '{id_}' não existe neste cômodo")


def _posicionar(
    projeto: Projeto,
    comodo: str,
    movel: Dados,
    centro: tuple[int, int] | None,
    rotacao: int | None,
    parede: str | None,
    distancia: int,
) -> None:
    if parede is not None:
        if centro is not None or rotacao is not None:
            raise EdicaoInvalidaError(
                "preso na parede, a posição e o giro são calculados: não mande centro/rotação"
            )
        pav = projeto.pavimento_do_comodo(comodo)
        assert pav is not None
        try:
            c, r = geometria.na_parede(
                pav, comodo, parede, distancia,
                movel["largura"]["valor"], movel["profundidade"]["valor"],
            )  # fmt: skip
        except ValueError as e:
            raise EdicaoInvalidaError(str(e)) from e
        movel["centro"], movel["rotacao"] = list(c), r
        return
    if centro is not None:
        movel["centro"] = list(centro)
    if rotacao is not None:
        movel["rotacao"] = rotacao


def id_livre(dados: DadosComodo | None, base: str) -> str:
    """``base`` se livre; senão ``base-2``, ``base-3``..."""
    usados = {m.id for m in dados.moveis} if dados else set()
    if base not in usados:
        return base
    n = 2
    while f"{base}-{n}" in usados:
        n += 1
    return f"{base}-{n}"


def adicionar_movel(
    projeto: Projeto,
    comodo: str,
    dados: DadosComodo | None,
    tipo: str,
    *,
    modelo: str | None = None,
    id_: str | None = None,
    nome: str | None = None,
    centro: tuple[int, int] | None = None,
    rotacao: int | None = None,
    parede: str | None = None,
    distancia: int = 0,
    medidas: Mapping[str, Medida | Mapping[str, Any]] | None = None,
    regras: Mapping[str, object] | None = None,
    base: Mapping[str, Any] | None = None,
) -> EdicaoMoveis:
    """Põe um móvel do catálogo no cômodo, pelo centro (e giro) ou preso numa parede.

    As medidas vêm do modelo do catálogo como ``estimada``; as de ``medidas``
    (largura, profundidade, altura, elevacao, largura_porta) as substituem, cada
    uma com a sua origem. ``base``: um modelo próprio (``modelos_proprios``) no lugar do
    catálogo — o móvel sai igual a ele, com as medidas e as origens que ele tinha.
    """
    if (centro is None) == (parede is None):
        raise EdicaoInvalidaError("informe a posição: centro (x, y) ou parede")
    medidas = dict(medidas or {})
    fora = set(medidas) - CAMPOS_MEDIDA
    if fora:
        raise EdicaoInvalidaError(f"medida(s) desconhecida(s): {', '.join(sorted(fora))}")
    if base is not None:
        tipo = str(base.get("tipo", tipo))
    novo_id = id_ or id_livre(dados, tipo.replace("_", "-"))
    try:
        if base is not None:
            movel = movel_do_modelo(base, novo_id, centro or (0, 0), rotacao or 0, nome)
        else:
            movel = catalogo.novo_movel(tipo, novo_id, centro or (0, 0), modelo, rotacao or 0, nome)
    except KeyError as e:  # tipo/modelo fora do catálogo: pedido inválido, não "não encontrado"
        raise EdicaoInvalidaError(str(e.args[0])) from e
    except ValidationError as e:  # modelo próprio que não vale mais (schema mudou)
        raise EdicaoInvalidaError(f"modelo inválido: {e.errors()[0]['msg']}") from e
    for campo, m in medidas.items():
        valor = m.model_dump(mode="json", exclude_none=True) if isinstance(m, Medida) else dict(m)
        movel[campo] = registrar_anterior(movel.get(campo), valor)
    if parede is not None:
        _posicionar(projeto, comodo, movel, None, None, parede, distancia)

    def mudar(d: Dados) -> None:
        d["moveis"].append(movel)

    return _aplicar(projeto, comodo, dados, regras, mudar)


def mover_movel(
    projeto: Projeto,
    comodo: str,
    dados: DadosComodo | None,
    id_: str,
    *,
    centro: tuple[int, int] | None = None,
    rotacao: int | None = None,
    parede: str | None = None,
    distancia: int = 0,
    regras: Mapping[str, object] | None = None,
) -> EdicaoMoveis:
    """Arrastar (``centro``), girar (``rotacao``) ou prender numa parede."""

    def mudar(d: Dados) -> None:
        movel = d["moveis"][_indice(d, id_)]
        _posicionar(projeto, comodo, movel, centro, rotacao, parede, distancia)

    return _aplicar(projeto, comodo, dados, regras, mudar)


def alterar_movel(
    projeto: Projeto,
    comodo: str,
    dados: DadosComodo | None,
    id_: str,
    campos: Mapping[str, Any],
    regras: Mapping[str, object] | None = None,
) -> EdicaoMoveis:
    """Medidas (com origem), nome, modelo, portas, polegadas. ``None`` apaga o campo."""
    fora = set(campos) - CAMPOS_MOVEL
    if fora:
        raise EdicaoInvalidaError(
            f"campo(s) não editável(is) aqui: {', '.join(sorted(fora))} (posição e giro: mover)"
        )

    def mudar(d: Dados) -> None:
        movel = d["moveis"][_indice(d, id_)]
        for k, v in campos.items():
            valor = v.model_dump(mode="json", exclude_none=True) if isinstance(v, Medida) else v
            if valor is None:
                movel.pop(k, None)
            elif k in CAMPOS_MEDIDA:
                movel[k] = registrar_anterior(movel.get(k), dict(valor))
            else:
                movel[k] = valor

    return _aplicar(projeto, comodo, dados, regras, mudar)


TAMANHO_MINIMO = 100
"""mm: menor largura/profundidade que o arrastar aceita."""

_LADOS: dict[str, tuple[str, int, int]] = {
    # lado arrastado → (medida que muda, eixo local x/y, sentido)
    "esquerda": ("largura", 0, -1),
    "direita": ("largura", 0, 1),
    "costas": ("profundidade", 1, -1),
    "frente": ("profundidade", 1, 1),
}


def redimensionar_movel(
    projeto: Projeto,
    comodo: str,
    dados: DadosComodo | None,
    id_: str,
    lado: str,
    tamanho: int,
    regras: Mapping[str, object] | None = None,
) -> EdicaoMoveis:
    """Arrastar um lado do móvel na planta: muda a largura (esquerda/direita) ou a
    profundidade (frente/costas) para ``tamanho`` mm com o lado **oposto parado** (o centro
    anda metade da diferença). A medida nova entra como ``projeto`` ("Quero assim"):
    arrastar é decidir o tamanho (decisão do usuário, 2026-11-20)."""
    if lado not in _LADOS:
        raise EdicaoInvalidaError(f"lado '{lado}' inválido ({', '.join(_LADOS)})")
    if tamanho < TAMANHO_MINIMO:
        raise EdicaoInvalidaError(f"tamanho mínimo é {TAMANHO_MINIMO} mm")
    campo, eixo, sentido = _LADOS[lado]

    def mudar(d: Dados) -> None:
        bruto = d["moveis"][_indice(d, id_)]
        atual = Movel.model_validate(bruto)
        antes = getattr(atual, campo).valor
        anda = (tamanho - antes) / 2 * sentido
        local = (anda, 0.0) if eixo == 0 else (0.0, anda)
        cx, cy = geometria.girar_movel(atual, *local)
        bruto["centro"] = [round(cx), round(cy)]
        nova = {"valor": int(tamanho), "origem": "projeto", "obs": "arrastado na planta"}
        bruto[campo] = registrar_anterior(bruto.get(campo), nova)

    return _aplicar(projeto, comodo, dados, regras, mudar)


def remover_movel(
    projeto: Projeto,
    comodo: str,
    dados: DadosComodo | None,
    id_: str,
    regras: Mapping[str, object] | None = None,
) -> EdicaoMoveis:
    def mudar(d: Dados) -> None:
        del d["moveis"][_indice(d, id_)]

    return _aplicar(projeto, comodo, dados, regras, mudar)


def definir_construcao(
    projeto: Projeto,
    comodo: str,
    dados: DadosComodo | None,
    id_: str,
    construcao: Mapping[str, Any] | None,
    regras: Mapping[str, object] | None = None,
) -> EdicaoMoveis:
    """Monta o móvel por dentro (planejado) ou tira a construção (``None``).

    Confere se a construção cabe no móvel (vãos, gavetas, alturas): o que não fecha é
    recusado com a mensagem do cálculo (ex.: "os vãos somam mais que a largura").
    """

    def mudar(d: Dados) -> None:
        movel = d["moveis"][_indice(d, id_)]
        if construcao is None:
            movel.pop("construcao", None)
            return
        movel["construcao"] = dict(construcao)
        try:
            planejado.calcular(Movel.model_validate(movel))
        except ValidationError as e:
            raise EdicaoInvalidaError(f"construção inválida: {e}") from e
        except planejado.ConstrucaoInvalidaError as e:
            raise EdicaoInvalidaError(str(e)) from e

    return _aplicar(projeto, comodo, dados, regras, mudar)


def definir_bancada(
    projeto: Projeto,
    comodo: str,
    dados: DadosComodo | None,
    id_: str,
    dados_bancada: Mapping[str, Any] | None,
    regras: Mapping[str, object] | None = None,
) -> EdicaoMoveis:
    """Monta a bancada (tampo, pernas, módulos) ou tira (``None``: volta a ser só a forma).

    Recusa o que não fecha (módulo fora do tampo, sobreposto, construção que não cabe),
    com a mensagem do cálculo.
    """

    def mudar(d: Dados) -> None:
        movel = d["moveis"][_indice(d, id_)]
        if dados_bancada is None:
            movel.pop("bancada", None)
            return
        movel["bancada"] = dict(dados_bancada)
        movel.pop("construcao", None)
        if movel.get("forma") not in (None, "L"):
            movel.pop("forma", None)
        try:
            bancada.calcular(Movel.model_validate(movel))
        except ValidationError as e:
            raise EdicaoInvalidaError(f"bancada inválida: {e}") from e
        except planejado.ConstrucaoInvalidaError as e:
            raise EdicaoInvalidaError(str(e)) from e

    return _aplicar(projeto, comodo, dados, regras, mudar)


def sugerir_construcao(
    projeto: Projeto,
    comodo: str,
    dados: DadosComodo | None,
    id_: str,
    regras: Mapping[str, object] | None = None,
) -> EdicaoMoveis:
    """Monta o móvel com o interior padrão do tipo (para a pessoa ajustar a partir daí)."""
    base = dados or DadosComodo(schema_version=1, comodo=comodo)
    movel = next((m for m in base.moveis if m.id == id_), None)
    if movel is None:
        raise KeyError(f"móvel '{id_}' não existe em '{comodo}'")
    try:
        sugerida = planejado.construcao_sugerida(movel)
    except KeyError as e:
        raise EdicaoInvalidaError(str(e.args[0])) from e
    return definir_construcao(projeto, comodo, dados, id_, sugerida, regras)
