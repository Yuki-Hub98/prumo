"""Edição da planta: paredes, aberturas (portas e janelas), cômodos, instalações
(tomadas, interruptores, luz, água, esgoto, ralo, gás) e pavimento.

Funções **puras**: recebem um :class:`Projeto`, devolvem uma :class:`Edicao` com o
projeto novo, a lista de alterações (antes → depois, para o histórico) e os
problemas da validação. Quem grava é o chamador: a API grava no banco e exporta o
JSON; a CLI usa :func:`gravar_projeto`.

Regra: uma edição nunca introduz referência quebrada (parede inexistente, id
repetido, lado de parede incoerente com o cômodo, porta sem sentido...). Nesses
casos levanta :class:`EdicaoInvalidaError` e nada muda. Problemas geométricos (cômodo
ainda não fechado, abertura passando do fim da parede...) não bloqueiam: voltam em
``Edicao.problemas`` para quem está desenhando ver e corrigir.
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from interiores_core import geometria
from interiores_core.medidas import Origem
from interiores_core.modelo import (
    EXTERNO,
    Comodo,
    Janela,
    Parede,
    Pavimento,
    PontoInstalacao,
    Porta,
    Projeto,
    TipoComodo,
    TrechoInstalacao,
)
from interiores_core.validacao import Problema, Severidade, validar

Dados = dict[str, Any]
Ponto = tuple[int, int]

BLOQUEIAM = frozenset(
    {
        "id_duplicado",
        "parede_inexistente",
        "lado_inexistente",
        "lado_inconsistente",
        "parede_nula",
        "porta_sentido",
        "porta_dobradica",
        "instalacao_comodo_invalido",
    }
)
"""Códigos de erro que uma edição não pode introduzir (referências quebradas).

``parede_lados_iguais`` fica de fora: parede recém-desenhada, antes de existir o
cômodo, tem ``externo`` dos dois lados — aparece como problema, não bloqueia."""


class EdicaoInvalidaError(ValueError):
    """A edição deixaria o projeto inconsistente; nada foi alterado."""


@dataclass(frozen=True)
class Alteracao:
    """Uma mudança no projeto. ``antes`` ``None`` = criado; ``depois`` ``None`` = removido."""

    caminho: str
    antes: Any
    depois: Any

    def __str__(self) -> str:
        return f"{self.caminho}: {_curto(self.antes)} → {_curto(self.depois)}"


@dataclass(frozen=True)
class Edicao:
    """Resultado de uma edição."""

    projeto: Projeto
    alteracoes: list[Alteracao]
    problemas: list[Problema]
    """Todos os problemas estruturais do projeto depois da edição."""
    novos: list[Problema] = field(default_factory=list)
    """Só os que a edição introduziu."""


# ---------------------------------------------------------------- núcleo


def _curto(valor: Any) -> str:
    if isinstance(valor, dict) and "valor" in valor and "origem" in valor:
        return f"{valor['valor']} ({valor['origem']})"
    if valor is None:
        return "—"
    return json.dumps(valor, ensure_ascii=False)


def _chave(p: Problema) -> tuple[str, str | None, str | None, str | None]:
    return (p.codigo, p.pavimento, p.comodo, p.elemento)


def _aplicar(projeto: Projeto, mudar: Callable[[Dados], None]) -> Edicao:
    """Aplica ``mudar`` numa cópia em dict, revalida e confere as referências."""
    antes = projeto.model_dump(mode="json", exclude_none=True)
    depois = copy.deepcopy(antes)
    mudar(depois)
    try:
        novo = Projeto.model_validate(depois)
    except ValidationError as e:
        raise EdicaoInvalidaError(f"dados inválidos: {e}") from e
    ja_havia = {_chave(p) for p in validar(projeto)}
    problemas = validar(novo)
    novos = [p for p in problemas if _chave(p) not in ja_havia]
    quebrados = [p for p in novos if p.severidade is Severidade.ERRO and p.codigo in BLOQUEIAM]
    if quebrados:
        raise EdicaoInvalidaError("; ".join(str(p) for p in quebrados))
    return Edicao(novo, list(diferencas(antes, depois)), problemas, novos)


def diferencas(antes: Any, depois: Any, caminho: str = "") -> Iterator[Alteracao]:
    """Compara dois dumps do projeto. Itens de lista com ``id`` são casados pelo id.

    Medidas, pontos e listas de ids são folhas (comparadas inteiras), para o
    histórico registrar ``paredes[p1].espessura: 150 (estimada) → 140 (trena)``.
    """
    if antes == depois:
        return
    if isinstance(antes, dict) and isinstance(depois, dict) and not _folha(antes):
        for k in [*antes, *(k for k in depois if k not in antes)]:
            sub = f"{caminho}.{k}" if caminho else k
            yield from diferencas(antes.get(k), depois.get(k), sub)
        return
    if _lista_com_id(antes) and _lista_com_id(depois):
        a = {i["id"]: i for i in antes}
        d = {i["id"]: i for i in depois}
        for id_ in [*a, *(i for i in d if i not in a)]:
            yield from diferencas(a.get(id_), d.get(id_), f"{caminho}[{id_}]")
        return
    yield Alteracao(caminho, antes, depois)


def _folha(d: Mapping[str, Any]) -> bool:
    return "valor" in d and "origem" in d


def _lista_com_id(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(i, dict) and "id" in i for i in v)


def _pav(dados: Dados, pavimento: str) -> Dados:
    for p in dados["pavimentos"]:
        if p["id"] == pavimento:
            return p  # type: ignore[no-any-return]
    raise KeyError(f"pavimento '{pavimento}' não existe")


def _item(lista: list[Dados], id_: str, nome: str) -> Dados:
    for i in lista:
        if i["id"] == id_:
            return i
    raise KeyError(f"{nome} '{id_}' não existe")


def _dump(valor: Any) -> Any:
    if isinstance(valor, BaseModel):
        return valor.model_dump(mode="json", exclude_none=True)
    if isinstance(valor, tuple):
        return list(valor)
    return copy.deepcopy(valor)


def registrar_anterior(antiga: Mapping[str, Any] | None, nova: Dados) -> Dados:
    """Medida que deixa de ser estimada guarda a anterior em ``obs`` (CLAUDE.md §4)."""
    if antiga and antiga.get("origem") == Origem.ESTIMADA and nova.get("origem") != Origem.ESTIMADA:
        nota = f"antes: {antiga['valor']} mm ({antiga['origem']})"
        nova["obs"] = f"{nova['obs']}; {nota}" if nova.get("obs") else nota
    return nova


def _mesclar(alvo: Dados, campos: Mapping[str, Any], permitidos: set[str]) -> None:
    fora = set(campos) - permitidos
    if fora:
        raise EdicaoInvalidaError(f"campo(s) não editável(is) aqui: {', '.join(sorted(fora))}")
    for k, v in campos.items():
        valor = _dump(v)
        if valor is None:
            alvo.pop(k, None)
        elif isinstance(valor, dict) and _folha(valor):
            alvo[k] = registrar_anterior(alvo.get(k), valor)
        else:
            alvo[k] = valor


def _ids_comodos(dados: Dados) -> set[str]:
    return {c["id"] for p in dados["pavimentos"] for c in p["comodos"]}


def _modelo_parede(d: Dados) -> Parede:
    return Parede.model_validate(d)


# ---------------------------------------------------------------- paredes

CAMPOS_PAREDE = {"inicio", "fim", "espessura", "lado_a", "lado_b", "altura"}


def adicionar_parede(
    projeto: Projeto, pavimento: str, parede: Parede | Mapping[str, Any]
) -> Edicao:
    """Acrescenta uma parede. Lados: ids de cômodos existentes ou ``"externo"``."""

    def mudar(d: Dados) -> None:
        _pav(d, pavimento)["paredes"].append(_dump(parede))

    return _aplicar(projeto, mudar)


def _projetar(parede: Dados, ponto: Ponto) -> float:
    """Distância ao longo do eixo (do início) da projeção de ``ponto``."""
    (x0, y0), (x1, y1) = parede["inicio"], parede["fim"]
    tam = math.hypot(x1 - x0, y1 - y0) or 1.0
    return float((ponto[0] - x0) * (x1 - x0) + (ponto[1] - y0) * (y1 - y0)) / tam


def _no_eixo(parede: Dados, distancia: float) -> list[int]:
    (x0, y0), (x1, y1) = parede["inicio"], parede["fim"]
    tam = math.hypot(x1 - x0, y1 - y0) or 1.0
    t = max(0.0, min(distancia, tam)) / tam
    return [round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t)]


def _mover_pontas(pav: Dados, movimentos: Mapping[tuple[int, int], Ponto], so: str | None) -> None:
    """Move pontas de parede (todas, ou só da parede ``so``) e arrasta os pontos
    de instalação presos a cada parede mexida, mantendo a distância do início."""
    for p in pav["paredes"]:
        if so is not None and p["id"] != so:
            continue
        ini, fim = tuple(p["inicio"]), tuple(p["fim"])
        if ini not in movimentos and fim not in movimentos:
            continue
        presos = [
            (i, _projetar(p, i["posicao"]))
            for i in pav["instalacoes"]
            if i.get("forma") == "ponto" and i.get("parede") == p["id"]
        ]
        p["inicio"] = list(movimentos.get(ini, ini))
        p["fim"] = list(movimentos.get(fim, fim))
        for inst, dist in presos:
            inst["posicao"] = _no_eixo(p, dist)


def alterar_parede(
    projeto: Projeto,
    pavimento: str,
    id_: str,
    campos: Mapping[str, Any],
    arrastar_vizinhas: bool = True,
) -> Edicao:
    """Muda campos da parede (``inicio``, ``fim``, ``espessura``, lados, ``altura``).

    Mudando uma ponta, as paredes que se encontravam nela vão junto
    (``arrastar_vizinhas``), para os cômodos continuarem fechados. Portas e
    janelas acompanham sozinhas (a posição é relativa ao início); pontos de
    instalação presos à parede mantêm a distância do início.
    """

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        p = _item(pav["paredes"], id_, "parede")
        movimentos: dict[tuple[int, int], Ponto] = {}
        for ponta in ("inicio", "fim"):
            if ponta in campos and tuple(campos[ponta]) != tuple(p[ponta]):
                movimentos[tuple(p[ponta])] = tuple(campos[ponta])
        if movimentos:
            _mover_pontas(pav, movimentos, None if arrastar_vizinhas else id_)
        _mesclar(p, {k: v for k, v in campos.items() if k not in ("inicio", "fim")}, CAMPOS_PAREDE)

    return _aplicar(projeto, mudar)


def mover_vertice(projeto: Projeto, pavimento: str, de: Ponto, para: Ponto) -> Edicao:
    """Move um canto: toda ponta de parede em ``de`` vai para ``para``."""

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        if not any(tuple(de) in (tuple(p["inicio"]), tuple(p["fim"])) for p in pav["paredes"]):
            raise KeyError(f"nenhuma parede tem ponta em {tuple(de)}")
        _mover_pontas(pav, {tuple(de): tuple(para)}, None)  # type: ignore[dict-item]

    return _aplicar(projeto, mudar)


def id_livre(usados: set[str], prefixo: str) -> str:
    """Primeiro ``<prefixo><n>`` livre, de 1 em diante (ex.: ``p`` → ``p8``)."""
    n = 1
    while f"{prefixo}{n}" in usados:
        n += 1
    return f"{prefixo}{n}"


def dividir_parede(
    projeto: Projeto, pavimento: str, id_: str, distancia: int, novo_id: str | None = None
) -> Edicao:
    """Corta a parede em dois a ``distancia`` mm do início (ex.: para encontrar uma
    parede nova no meio dela). A primeira parte mantém o id; a segunda ganha
    ``novo_id``. Aberturas, cômodos e instalações passam para a parte certa.
    """

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        p = _item(pav["paredes"], id_, "parede")
        tam = geometria.comprimento(_modelo_parede(p))
        if not 0 < distancia < tam:
            raise EdicaoInvalidaError(
                f"corte a {distancia} mm fora da parede '{id_}' ({tam:.0f} mm)"
            )
        nid = novo_id or id_livre({q["id"] for q in pav["paredes"]}, "p")
        corte = _no_eixo(p, distancia)
        segunda = {**copy.deepcopy(p), "id": nid, "inicio": corte}
        for a in pav["aberturas"]:
            if a["parede"] != id_:
                continue
            ini, larg = a["distancia_inicio"]["valor"], a["largura"]["valor"]
            if ini < distancia < ini + larg:
                raise EdicaoInvalidaError(f"o corte passa pelo vão de '{a['id']}'")
            if ini >= distancia:
                a["parede"] = nid
                a["distancia_inicio"] = {**a["distancia_inicio"], "valor": ini - distancia}
        for i in pav["instalacoes"]:
            if i.get("parede") == id_ and _projetar(p, i["posicao"]) > distancia:
                i["parede"] = nid
        for c in pav["comodos"]:
            if id_ in c["paredes"]:
                c["paredes"].insert(c["paredes"].index(id_) + 1, nid)
        p["fim"] = corte
        pav["paredes"].insert(pav["paredes"].index(p) + 1, segunda)

    return _aplicar(projeto, mudar)


def remover_parede(projeto: Projeto, pavimento: str, id_: str, cascata: bool = False) -> Edicao:
    """Remove a parede. Se ela tiver aberturas, cômodos ou instalações presas, só
    remove com ``cascata=True`` (apaga as aberturas, tira a parede dos cômodos e
    solta as instalações)."""

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        _item(pav["paredes"], id_, "parede")
        aberturas = [a["id"] for a in pav["aberturas"] if a["parede"] == id_]
        comodos = [c["id"] for c in pav["comodos"] if id_ in c["paredes"]]
        instalacoes = [i for i in pav["instalacoes"] if i.get("parede") == id_]
        if not cascata and (aberturas or comodos or instalacoes):
            partes = [
                f"aberturas {aberturas}" if aberturas else "",
                f"cômodos {comodos}" if comodos else "",
                f"instalações {[i['id'] for i in instalacoes]}" if instalacoes else "",
            ]
            raise EdicaoInvalidaError(
                f"parede '{id_}' está em uso ({', '.join(x for x in partes if x)}); "
                "use cascata para remover junto"
            )
        pav["paredes"] = [p for p in pav["paredes"] if p["id"] != id_]
        pav["aberturas"] = [a for a in pav["aberturas"] if a["parede"] != id_]
        for c in pav["comodos"]:
            c["paredes"] = [x for x in c["paredes"] if x != id_]
        for i in instalacoes:
            i.pop("parede", None)

    return _aplicar(projeto, mudar)


# ---------------------------------------------------------------- aberturas

CAMPOS_PORTA = {
    "parede", "distancia_inicio", "largura", "altura", "de", "para", "folha", "abre_para",
    "dobradica", "estilo", "modelo",
}  # fmt: skip
CAMPOS_JANELA = {
    "parede", "distancia_inicio", "largura", "altura", "peitoril", "abertura", "folhas", "modelo",
}  # fmt: skip


def adicionar_abertura(
    projeto: Projeto, pavimento: str, abertura: Porta | Janela | Mapping[str, Any]
) -> Edicao:
    """Acrescenta uma porta ou janela numa parede existente."""

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        dados = _dump(abertura)
        _item(pav["paredes"], dados["parede"], "parede")
        pav["aberturas"].append(dados)

    return _aplicar(projeto, mudar)


def alterar_abertura(
    projeto: Projeto, pavimento: str, id_: str, campos: Mapping[str, Any]
) -> Edicao:
    """Muda campos da porta/janela (posição, tamanho, sentido...). ``None`` apaga o campo."""

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        a = _item(pav["aberturas"], id_, "abertura")
        if "parede" in campos:
            _item(pav["paredes"], campos["parede"], "parede")
        _mesclar(a, campos, CAMPOS_PORTA if a["tipo"] == "porta" else CAMPOS_JANELA)

    return _aplicar(projeto, mudar)


def remover_abertura(projeto: Projeto, pavimento: str, id_: str) -> Edicao:
    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        _item(pav["aberturas"], id_, "abertura")
        pav["aberturas"] = [a for a in pav["aberturas"] if a["id"] != id_]

    return _aplicar(projeto, mudar)


# ---------------------------------------------------------------- cômodos

CAMPOS_COMODO = {"nome", "tipo", "paredes", "piso", "teto", "pe_direito"}


def _ajustar_lados(pav: Dados, comodo_id: str, antigas: list[str], novas: list[str]) -> None:
    """Põe o cômodo no lado certo de cada parede nova (pela geometria) e devolve
    ``externo`` no lado das paredes que ele deixou de usar."""
    for pid in antigas:
        if pid in novas:
            continue
        p = next((q for q in pav["paredes"] if q["id"] == pid), None)
        if p is None:
            continue
        for lado in ("lado_a", "lado_b"):
            if p[lado] == comodo_id:
                p[lado] = EXTERNO
    linhas = [q for q in pav["paredes"] if q["id"] in novas]
    if len(linhas) != len(set(novas)):
        return  # parede inexistente: a validação aponta
    paredes = [_modelo_parede(q) for q in linhas]
    temp = Comodo(id=comodo_id, nome="", tipo=TipoComodo.OUTRO, paredes=novas)
    poligono = geometria.poligono_eixo(_pav_modelo(pav, paredes), temp)
    if poligono is None:
        return  # ainda não fecha: lados ficam como estão, a validação aponta
    for q, parede in zip(linhas, paredes, strict=True):
        dentro_a = poligono.contains(geometria.ponto_ao_lado(parede, "a"))
        lado = "lado_a" if dentro_a else "lado_b"
        outro = "lado_b" if dentro_a else "lado_a"
        if q[outro] == comodo_id:
            q[outro] = EXTERNO
        if q[lado] not in (EXTERNO, comodo_id):
            raise EdicaoInvalidaError(
                f"parede '{q['id']}' já separa '{q['lado_a']}' e '{q['lado_b']}'; "
                f"o lado de '{comodo_id}' está ocupado por '{q[lado]}'"
            )
        q[lado] = comodo_id


def _pav_modelo(pav: Dados, paredes: list[Parede]) -> Pavimento:
    """Pavimento só com as paredes dadas (o resto pode estar no meio da edição)."""
    return Pavimento.model_validate(
        {"id": pav["id"], "cota_piso": pav["cota_piso"], "pe_direito": pav["pe_direito"]}
    ).model_copy(update={"paredes": paredes})


def adicionar_comodo(
    projeto: Projeto, pavimento: str, comodo: Comodo | Mapping[str, Any], ajustar_lados: bool = True
) -> Edicao:
    """Acrescenta um cômodo delimitado por paredes existentes.

    Com ``ajustar_lados``, o cômodo é posto no lado certo de cada parede (o de
    dentro do polígono). Uma parede só aceita o cômodo se aquele lado estiver
    ``externo``: parede é uma só entre dois cômodos.
    """

    def mudar(d: Dados) -> None:
        dados = _dump(comodo)
        if dados["id"] in _ids_comodos(d):
            raise EdicaoInvalidaError(f"já existe um cômodo '{dados['id']}'")
        pav = _pav(d, pavimento)
        pav["comodos"].append(dados)
        if ajustar_lados:
            _ajustar_lados(pav, dados["id"], [], dados["paredes"])

    return _aplicar(projeto, mudar)


def alterar_comodo(
    projeto: Projeto,
    pavimento: str,
    id_: str,
    campos: Mapping[str, Any],
    ajustar_lados: bool = True,
) -> Edicao:
    """Muda nome, tipo, acabamentos, pé-direito ou a lista de paredes do cômodo."""

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        c = _item(pav["comodos"], id_, "cômodo")
        antigas = list(c["paredes"])
        _mesclar(c, campos, CAMPOS_COMODO)
        if ajustar_lados and "paredes" in campos:
            _ajustar_lados(pav, id_, antigas, c["paredes"])

    return _aplicar(projeto, mudar)


def remover_comodo(projeto: Projeto, pavimento: str, id_: str) -> Edicao:
    """Remove o cômodo. Paredes ficam (com o lado dele virando ``externo``), portas
    que davam nele passam a dar para ``externo`` e instalações dele ficam sem
    cômodo. O mobiliário (``comodos/<id>.json``) é do chamador."""

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        _item(pav["comodos"], id_, "cômodo")
        pav["comodos"] = [c for c in pav["comodos"] if c["id"] != id_]
        for p in pav["paredes"]:
            for lado in ("lado_a", "lado_b"):
                if p[lado] == id_:
                    p[lado] = EXTERNO
        for a in pav["aberturas"]:
            for k in ("de", "para", "abre_para"):
                if a.get(k) == id_:
                    a[k] = EXTERNO
        for i in pav["instalacoes"]:
            if i.get("comodo") == id_:
                del i["comodo"]

    return _aplicar(projeto, mudar)


# ---------------------------------------------------------------- instalações

CAMPOS_PONTO = {"tipo", "posicao", "altura", "parede", "comodo", "obs"}
CAMPOS_TRECHO = {"tipo", "caminho", "altura", "embutido", "obs"}


def _assentar(pav: Dados, inst: Dados, distancia: int | None) -> None:
    """Ponto preso a uma parede fica sobre o eixo dela: a ``distancia`` mm do início,
    se dada, ou na projeção da ``posicao`` informada (limitada às pontas)."""
    if inst.get("forma") != "ponto" or not inst.get("parede"):
        if distancia is not None:
            raise EdicaoInvalidaError("distância só vale para ponto preso a uma parede")
        return
    parede = _item(pav["paredes"], inst["parede"], "parede")
    if distancia is None:
        if "posicao" not in inst:
            raise EdicaoInvalidaError("informe a posição ou a distância do início da parede")
        distancia = round(_projetar(parede, inst["posicao"]))
    inst["posicao"] = _no_eixo(parede, distancia)


def adicionar_instalacao(
    projeto: Projeto,
    pavimento: str,
    instalacao: PontoInstalacao | TrechoInstalacao | Mapping[str, Any],
    distancia: int | None = None,
) -> Edicao:
    """Acrescenta um ponto (tomada, interruptor, luz, água, esgoto, ralo, gás) ou um
    trecho de tubulação/eletroduto.

    Ponto com ``parede``: use ``distancia`` (mm do início da parede) ou ``posicao``,
    que é levada para o eixo da parede. Ponto sem parede (luz no teto, ralo,
    esgoto no piso) fica onde a ``posicao`` mandar.
    """

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        dados = _dump(instalacao)
        _assentar(pav, dados, distancia)
        pav["instalacoes"].append(dados)

    return _aplicar(projeto, mudar)


def alterar_instalacao(
    projeto: Projeto,
    pavimento: str,
    id_: str,
    campos: Mapping[str, Any],
    distancia: int | None = None,
) -> Edicao:
    """Muda tipo, posição, altura, parede, cômodo ou observação do ponto (ou o
    caminho do trecho). ``None`` apaga o campo (ex.: ``parede: None`` solta o ponto)."""

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        inst = _item(pav["instalacoes"], id_, "instalação")
        _mesclar(inst, campos, CAMPOS_PONTO if inst["forma"] == "ponto" else CAMPOS_TRECHO)
        if distancia is not None or {"posicao", "parede"} & set(campos):
            _assentar(pav, inst, distancia)

    return _aplicar(projeto, mudar)


def remover_instalacao(projeto: Projeto, pavimento: str, id_: str) -> Edicao:
    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        _item(pav["instalacoes"], id_, "instalação")
        pav["instalacoes"] = [i for i in pav["instalacoes"] if i["id"] != id_]

    return _aplicar(projeto, mudar)


# ---------------------------------------------------------------- pavimento

CAMPOS_PAVIMENTO = {"nome", "cota_piso", "pe_direito", "rodape"}


def alterar_pavimento(projeto: Projeto, pavimento: str, campos: Mapping[str, Any]) -> Edicao:
    """Muda nome, cota do piso, pé-direito ou rodapé do pavimento."""

    def mudar(d: Dados) -> None:
        _mesclar(_pav(d, pavimento), campos, CAMPOS_PAVIMENTO)

    return _aplicar(projeto, mudar)


def adicionar_pavimento(
    projeto: Projeto, pavimento: Pavimento | Mapping[str, Any], depois_de: str | None = None
) -> Edicao:
    """Acrescenta um pavimento (ex.: superior de um sobrado), no fim ou após ``depois_de``."""

    def mudar(d: Dados) -> None:
        dados = _dump(pavimento)
        if any(p["id"] == dados.get("id") for p in d["pavimentos"]):
            raise EdicaoInvalidaError(f"já existe um pavimento '{dados.get('id')}'")
        pos = len(d["pavimentos"])
        if depois_de is not None:
            pos = d["pavimentos"].index(_pav(d, depois_de)) + 1
        d["pavimentos"].insert(pos, dados)

    return _aplicar(projeto, mudar)


def remover_pavimento(projeto: Projeto, pavimento: str, cascata: bool = False) -> Edicao:
    """Remove o pavimento. Com paredes, aberturas, estrutura, instalações ou cômodos,
    só com ``cascata=True`` (vai tudo junto). O último pavimento não sai.
    O mobiliário dos cômodos removidos é do chamador."""

    def mudar(d: Dados) -> None:
        pav = _pav(d, pavimento)
        if len(d["pavimentos"]) == 1:
            raise EdicaoInvalidaError("o projeto precisa de pelo menos um pavimento")
        cheio = {
            k: len(pav.get(k, []))
            for k in ("paredes", "aberturas", "estrutura", "instalacoes", "comodos")
            if pav.get(k)
        }
        if cheio and not cascata:
            itens = ", ".join(f"{n} {k}" for k, n in cheio.items())
            raise EdicaoInvalidaError(
                f"pavimento '{pavimento}' não está vazio ({itens}); use cascata para remover junto"
            )
        d["pavimentos"].remove(pav)

    return _aplicar(projeto, mudar)


def comodos_do_pavimento(projeto: Projeto, pavimento: str) -> list[str]:
    """Ids dos cômodos de um pavimento (para o chamador limpar o mobiliário)."""
    pav = next((p for p in projeto.pavimentos if p.id == pavimento), None)
    if pav is None:
        raise KeyError(f"pavimento '{pavimento}' não existe")
    return [c.id for c in pav.comodos]


# ---------------------------------------------------------------- imóvel / projeto

CAMPOS_IMOVEL = {"tipo", "endereco_apelido"}


def alterar_imovel(projeto: Projeto, campos: Mapping[str, Any]) -> Edicao:
    """Tipo do imóvel (casa | apartamento) e apelido."""

    def mudar(d: Dados) -> None:
        _mesclar(d["imovel"], campos, CAMPOS_IMOVEL)

    return _aplicar(projeto, mudar)


def renomear_projeto(projeto: Projeto, codigo: str) -> Edicao:
    """Troca o código do projeto (o nome da pasta em ``projetos/``)."""

    def mudar(d: Dados) -> None:
        d["projeto"] = codigo

    return _aplicar(projeto, mudar)


# ---------------------------------------------------------------- arquivo


def ler_projeto(pasta: Path | str) -> Projeto:
    texto = (Path(pasta) / "projeto.json").read_text(encoding="utf-8")
    return Projeto.model_validate_json(texto)


def gravar_projeto(pasta: Path | str, projeto: Projeto) -> Path:
    """Grava ``projeto.json`` com a formatação do repositório (indent 2, UTF-8)."""
    arq = Path(pasta) / "projeto.json"
    dados = projeto.model_dump(mode="json", exclude_none=True)
    arq.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return arq


__all__ = [
    "Alteracao",
    "Edicao",
    "EdicaoInvalidaError",
    "adicionar_abertura",
    "adicionar_comodo",
    "adicionar_instalacao",
    "adicionar_parede",
    "adicionar_pavimento",
    "alterar_abertura",
    "alterar_comodo",
    "alterar_imovel",
    "alterar_instalacao",
    "alterar_parede",
    "alterar_pavimento",
    "comodos_do_pavimento",
    "diferencas",
    "dividir_parede",
    "gravar_projeto",
    "id_livre",
    "ler_projeto",
    "mover_vertice",
    "registrar_anterior",
    "remover_abertura",
    "remover_comodo",
    "remover_instalacao",
    "remover_parede",
    "remover_pavimento",
    "renomear_projeto",
]
