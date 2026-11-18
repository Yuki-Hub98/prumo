"""Validação estrutural do projeto (consistência entre paredes, aberturas e cômodos).

Erros de formato (campo faltando, medida com decimal, origem inválida) já são barrados
pelo pydantic ao carregar. Aqui ficam as regras que dependem de mais de um elemento.
As checagens de ergonomia (passagem, cama, guarda-roupa...) ficam em ``regras/`` e
``tipos/``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from enum import StrEnum
from itertools import pairwise
from typing import Any

from pydantic import BaseModel, ConfigDict
from shapely import LineString, Point

from interiores_core import catalogo, geometria
from interiores_core.modelo import (
    EXTERNO,
    Comodo,
    DadosComodo,
    Instalacao,
    Janela,
    Movel,
    Parede,
    Pavimento,
    PontoInstalacao,
    Porta,
    Projeto,
)


class Severidade(StrEnum):
    ERRO = "erro"
    """Bloqueia "pronto para marceneiro"."""
    AVISO = "aviso"
    INFO = "info"


class Problema(BaseModel):
    model_config = ConfigDict(frozen=True)

    severidade: Severidade
    codigo: str
    mensagem: str
    pavimento: str | None = None
    comodo: str | None = None
    elemento: str | None = None
    posicao: tuple[int, int] | None = None
    regiao: list[tuple[int, int]] | None = None
    """Contorno da área com problema (para desenhar na camada RESTRICAO)."""

    def __str__(self) -> str:
        onde = " · ".join(
            x
            for x in (
                self.pavimento,
                self.comodo,
                self.elemento,
                f"({self.posicao[0]}, {self.posicao[1]})" if self.posicao else None,
            )
            if x
        )
        return f"[{self.severidade}] {self.codigo}: {self.mensagem}" + (
            f" — {onde}" if onde else ""
        )


ORDEM_SEVERIDADE = {Severidade.ERRO: 0, Severidade.AVISO: 1, Severidade.INFO: 2}


def _meio(p: Parede) -> tuple[int, int]:
    return (round((p.inicio[0] + p.fim[0]) / 2), round((p.inicio[1] + p.fim[1]) / 2))


def _repetidos(ids: Iterable[str]) -> list[str]:
    return sorted(i for i, n in Counter(ids).items() if n > 1)


def _colineares(a: Parede, b: Parede) -> bool:
    (ax0, ay0), (ax1, ay1) = a.inicio, a.fim
    dx, dy = ax1 - ax0, ay1 - ay0
    return all((x - ax0) * dy - (y - ay0) * dx == 0 for x, y in (b.inicio, b.fim))


class _Validador:
    def __init__(self, projeto: Projeto) -> None:
        self.projeto = projeto
        self.problemas: list[Problema] = []
        self.ids_comodos = {c.id for pav in projeto.pavimentos for c in pav.comodos}

    def add(self, severidade: Severidade, codigo: str, mensagem: str, **onde: Any) -> None:
        self.problemas.append(
            Problema(severidade=severidade, codigo=codigo, mensagem=mensagem, **onde)
        )

    # ------------------------------------------------------------ projeto

    def projeto_inteiro(self) -> None:
        for rep in _repetidos(p.id for p in self.projeto.pavimentos):
            self.add(Severidade.ERRO, "id_duplicado", f"pavimento '{rep}' repetido")
        todos = [c.id for pav in self.projeto.pavimentos for c in pav.comodos]
        for rep in _repetidos(todos):
            self.add(
                Severidade.ERRO,
                "id_duplicado",
                f"cômodo '{rep}' repetido (ids de cômodo são únicos no projeto)",
                comodo=rep,
            )
        for pav in self.projeto.pavimentos:
            self.pavimento(pav)

    # ------------------------------------------------------------ pavimento

    def pavimento(self, pav: Pavimento) -> None:
        for nome, ids in (
            ("parede", [p.id for p in pav.paredes]),
            ("abertura", [a.id for a in pav.aberturas]),
            ("estrutura", [e.id for e in pav.estrutura]),
            ("instalação", [i.id for i in pav.instalacoes]),
        ):
            for rep in _repetidos(ids):
                self.add(
                    Severidade.ERRO,
                    "id_duplicado",
                    f"{nome} '{rep}' repetida",
                    pavimento=pav.id,
                    elemento=rep,
                )
        self.paredes(pav)
        for comodo in pav.comodos:
            self.comodo(pav, comodo)
        self.aberturas(pav)
        self.instalacoes(pav)
        if not pav.estrutura:
            self.add(
                Severidade.INFO,
                "sem_estrutura",
                "nenhum pilar ou viga informado — confirme se não há",
                pavimento=pav.id,
            )
        if pav.rodape is None:
            self.add(
                Severidade.INFO, "sem_rodape", "altura do rodapé não informada", pavimento=pav.id
            )

    def paredes(self, pav: Pavimento) -> None:
        validas = [p for p in pav.paredes if geometria.comprimento(p) > 0]
        for p in pav.paredes:
            if geometria.comprimento(p) == 0:
                self.add(
                    Severidade.ERRO,
                    "parede_nula",
                    "início e fim da parede coincidem",
                    pavimento=pav.id,
                    elemento=p.id,
                    posicao=p.inicio,
                )
            if p.lado_a == p.lado_b:
                self.add(
                    Severidade.ERRO,
                    "parede_lados_iguais",
                    f"lado_a e lado_b são o mesmo ('{p.lado_a}')",
                    pavimento=pav.id,
                    elemento=p.id,
                    posicao=_meio(p),
                )
            for lado in (p.lado_a, p.lado_b):
                if lado != EXTERNO and lado not in self.ids_comodos:
                    self.add(
                        Severidade.ERRO,
                        "lado_inexistente",
                        f"lado aponta para cômodo inexistente '{lado}'",
                        pavimento=pav.id,
                        elemento=p.id,
                        posicao=_meio(p),
                    )
        for i, a in enumerate(validas):
            for b in validas[i + 1 :]:
                if not _colineares(a, b):
                    continue
                comum = geometria.eixo(a).intersection(geometria.eixo(b))
                if comum.length > 0:
                    self.add(
                        Severidade.ERRO,
                        "paredes_sobrepostas",
                        f"paredes '{a.id}' e '{b.id}' se sobrepõem no mesmo eixo",
                        pavimento=pav.id,
                        elemento=f"{a.id},{b.id}",
                        posicao=_meio(a),
                    )
                elif not comum.is_empty and a.espessura.valor != b.espessura.valor:
                    self.add(
                        Severidade.ERRO,
                        "espessura_divergente",
                        f"paredes '{a.id}' ({a.espessura.valor} mm) e '{b.id}' "
                        f"({b.espessura.valor} mm) continuam no mesmo eixo com espessuras"
                        " diferentes",
                        pavimento=pav.id,
                        elemento=f"{a.id},{b.id}",
                        posicao=(round(comum.centroid.x), round(comum.centroid.y)),
                    )

    # ------------------------------------------------------------ cômodos

    def comodo(self, pav: Pavimento, comodo: Comodo) -> None:
        onde = {"pavimento": pav.id, "comodo": comodo.id}
        faltando = [pid for pid in comodo.paredes if pav.parede(pid) is None]
        for pid in faltando:
            self.add(
                Severidade.ERRO,
                "parede_inexistente",
                f"cômodo referencia parede inexistente '{pid}'",
                elemento=pid,
                **onde,
            )
        for rep in _repetidos(comodo.paredes):
            self.add(
                Severidade.ERRO,
                "parede_repetida",
                f"parede '{rep}' listada duas vezes",
                elemento=rep,
                **onde,
            )
        for p in pav.paredes:
            lista = p.id in comodo.paredes
            lado = comodo.id in (p.lado_a, p.lado_b)
            if lista and not lado:
                self.add(
                    Severidade.ERRO,
                    "lado_inconsistente",
                    f"cômodo lista a parede '{p.id}', mas ela não tem o cômodo em lado_a/lado_b",
                    elemento=p.id,
                    posicao=_meio(p),
                    **onde,
                )
            elif lado and not lista:
                self.add(
                    Severidade.ERRO,
                    "lado_inconsistente",
                    f"parede '{p.id}' diz delimitar o cômodo, mas ele não a lista",
                    elemento=p.id,
                    posicao=_meio(p),
                    **onde,
                )
        if faltando:
            return
        poligono = geometria.poligono_eixo(pav, comodo)
        if poligono is None:
            self.add(
                Severidade.ERRO,
                "comodo_nao_fechado",
                "as paredes do cômodo não formam um contorno fechado único",
                **onde,
            )
            return
        for pid in comodo.paredes:
            parede = pav.parede(pid)
            assert parede is not None
            for nome_lado, valor in (("a", parede.lado_a), ("b", parede.lado_b)):
                dentro = poligono.contains(geometria.ponto_ao_lado(parede, nome_lado))
                if valor == comodo.id and not dentro:
                    self.add(
                        Severidade.ERRO,
                        "lado_trocado",
                        f"parede '{parede.id}': o cômodo está do outro lado (troque lado_a/lado_b"
                        " ou inverta início/fim; lado_a = esquerda de quem anda do início ao fim)",
                        elemento=parede.id,
                        posicao=_meio(parede),
                        **onde,
                    )
        portas = [a for a in pav.aberturas if isinstance(a, Porta) and comodo.id in (a.de, a.para)]
        if not portas:
            self.add(Severidade.AVISO, "comodo_sem_porta", "cômodo sem porta (inacessível)", **onde)

    # ------------------------------------------------------------ aberturas

    def aberturas(self, pav: Pavimento) -> None:
        por_parede: dict[str, list[tuple[int, int, str]]] = {}
        for ab in pav.aberturas:
            onde = {"pavimento": pav.id, "elemento": ab.id}
            p = pav.parede(ab.parede)
            if p is None:
                self.add(
                    Severidade.ERRO,
                    "parede_inexistente",
                    f"abertura em parede inexistente '{ab.parede}'",
                    **onde,
                )
                continue
            ini = ab.distancia_inicio.valor
            fim = ini + ab.largura.valor
            if fim > geometria.comprimento(p):
                self.add(
                    Severidade.ERRO,
                    "abertura_fora_da_parede",
                    f"vão vai até {fim} mm, mas a parede '{p.id}' tem "
                    f"{round(geometria.comprimento(p))} mm",
                    posicao=_meio(p),
                    **onde,
                )
            por_parede.setdefault(p.id, []).append((ini, fim, ab.id))
            limite = (p.altura or pav.pe_direito).valor
            topo = ab.altura.valor + (ab.peitoril.valor if isinstance(ab, Janela) else 0)
            if topo > limite:
                self.add(
                    Severidade.ERRO,
                    "abertura_acima_do_teto",
                    f"topo do vão a {topo} mm, acima da altura da parede ({limite} mm)",
                    posicao=_meio(p),
                    **onde,
                )
            if isinstance(ab, Porta):
                self.porta(pav, ab, p)
        for pid, vaos in por_parede.items():
            vaos.sort()
            for (_, fim_a, id_a), (ini_b, _, id_b) in pairwise(vaos):
                if ini_b < fim_a:
                    self.add(
                        Severidade.ERRO,
                        "aberturas_sobrepostas",
                        f"aberturas '{id_a}' e '{id_b}' se sobrepõem na parede '{pid}'",
                        pavimento=pav.id,
                        elemento=f"{id_a},{id_b}",
                    )

    def porta(self, pav: Pavimento, porta: Porta, parede: Parede) -> None:
        onde = {"pavimento": pav.id, "elemento": porta.id, "posicao": _meio(parede)}
        if {porta.de, porta.para} != {parede.lado_a, parede.lado_b}:
            self.add(
                Severidade.ERRO,
                "porta_lados",
                f"porta liga '{porta.de}' → '{porta.para}', mas a parede '{parede.id}' separa "
                f"'{parede.lado_a}' e '{parede.lado_b}'",
                **onde,
            )
        if porta.folha == "giro":
            if porta.abre_para not in (porta.de, porta.para):
                self.add(
                    Severidade.ERRO,
                    "porta_sentido",
                    "porta de giro precisa de 'abre_para' igual a 'de' ou 'para'",
                    **onde,
                )
            if porta.dobradica is None:
                self.add(
                    Severidade.ERRO,
                    "porta_dobradica",
                    "porta de giro precisa de 'dobradica' (inicio|fim)",
                    **onde,
                )

    # ------------------------------------------------------------ instalações

    def instalacoes(self, pav: Pavimento) -> None:
        for inst in pav.instalacoes:
            onde: dict[str, Any] = {"pavimento": pav.id, "elemento": inst.id}
            if isinstance(inst, PontoInstalacao):
                onde["posicao"] = inst.posicao
                if inst.parede is not None and pav.parede(inst.parede) is None:
                    self.add(
                        Severidade.ERRO,
                        "parede_inexistente",
                        f"instalação em parede inexistente '{inst.parede}'",
                        **onde,
                    )
                self.lado_da_instalacao(pav, inst, onde)
            limite = self.pe_direito_em(pav, inst)
            if inst.altura.valor > limite:
                self.add(
                    Severidade.ERRO,
                    "instalacao_acima_do_teto",
                    f"altura {inst.altura.valor} mm acima do pé-direito ({limite} mm)",
                    **onde,
                )

    def lado_da_instalacao(
        self, pav: Pavimento, inst: PontoInstalacao, onde: dict[str, Any]
    ) -> None:
        """``comodo`` do ponto existe, é um dos lados da parede e não falta em parede interna."""
        parede = pav.parede(inst.parede) if inst.parede else None
        lados = {parede.lado_a, parede.lado_b} - {EXTERNO} if parede else set()
        if inst.comodo is not None:
            if inst.comodo not in self.ids_comodos:
                self.add(
                    Severidade.ERRO,
                    "instalacao_comodo_invalido",
                    f"cômodo '{inst.comodo}' não existe",
                    **onde,
                )
            elif parede is not None and inst.comodo not in lados:
                self.add(
                    Severidade.ERRO,
                    "instalacao_comodo_invalido",
                    f"cômodo '{inst.comodo}' não é um dos lados da parede '{parede.id}'",
                    **onde,
                )
        elif len(lados) == 2:
            self.add(
                Severidade.AVISO,
                "instalacao_lado_indefinido",
                f"ponto na parede '{parede.id if parede else ''}' entre "
                f"{' e '.join(sorted(lados))}: informe `comodo` para saber de que lado fica",
                **onde,
            )

    @staticmethod
    def pe_direito_em(pav: Pavimento, inst: Instalacao) -> int:
        """Maior pé-direito dos cômodos que a instalação toca (o do pavimento se nenhum)."""
        geom = (
            Point(inst.posicao) if isinstance(inst, PontoInstalacao) else LineString(inst.caminho)
        )
        alturas = [pav.pe_direito.valor]
        for comodo in pav.comodos:
            if comodo.pe_direito is None:
                continue
            poligono = geometria.poligono_eixo(pav, comodo)
            if poligono is not None and poligono.intersects(geom):
                alturas.append(comodo.pe_direito.valor)
        return max(alturas)

    # ------------------------------------------------------------ comodos/*.json

    def dados_comodos(self, dados: Mapping[str, DadosComodo]) -> None:
        for nome, d in dados.items():
            if d.comodo not in self.ids_comodos:
                self.add(
                    Severidade.ERRO,
                    "dados_de_comodo_inexistente",
                    f"'{nome}' descreve o cômodo '{d.comodo}', que não existe no projeto",
                    comodo=d.comodo,
                )
            for rep in _repetidos(m.id for m in d.moveis):
                self.add(
                    Severidade.ERRO,
                    "id_duplicado",
                    f"móvel '{rep}' repetido",
                    comodo=d.comodo,
                    elemento=rep,
                )
            for m in d.moveis:
                self.movel_no_catalogo(d.comodo, m)

    def movel_no_catalogo(self, comodo: str, m: Movel) -> None:
        onde: dict[str, Any] = {"comodo": comodo, "elemento": m.id, "posicao": m.centro}
        item = catalogo.item_do_tipo(m.tipo)
        if item is None:
            self.add(
                Severidade.INFO,
                "movel_fora_do_catalogo",
                f"tipo '{m.tipo}' não está no catálogo: desenhado como caixa, usa só a frente",
                **onde,
            )
            return
        if m.modelo is not None and item.modelo(m.modelo) is None:
            ids = ", ".join(x.id for x in item.modelos)
            self.add(
                Severidade.AVISO,
                "modelo_desconhecido",
                f"modelo '{m.modelo}' não existe para '{m.tipo}' ({ids})",
                **onde,
            )
        if item.simbolo is catalogo.Simbolo.TELA and m.polegadas is None:
            self.add(
                Severidade.INFO,
                "tela_sem_polegadas",
                "informe `polegadas` para checar a distância de quem assiste",
                **onde,
            )


def validar(
    projeto: Projeto, dados_comodos: Mapping[str, DadosComodo] | None = None
) -> list[Problema]:
    """Roda todas as validações estruturais e devolve os problemas ordenados por severidade."""
    v = _Validador(projeto)
    v.projeto_inteiro()
    if dados_comodos:
        v.dados_comodos(dados_comodos)
    return sorted(v.problemas, key=lambda p: ORDEM_SEVERIDADE[p.severidade])
