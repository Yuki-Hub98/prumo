"""Conversão entre o conteúdo do projeto (modelos do core) e as linhas do banco.

O conteúdo é o que existe em ``projetos/<p>/``: ``projeto.json``, ``comodos/*.json``,
``variacoes/<comodo>/*.json`` e ``regras.toml``. Medidas viram linhas de
``medida`` (identificadas pelo caminho, como no carimbo:
``pavimentos[terreo].paredes[p1].espessura``); o resto vira coluna. Campo que não
tem coluna nem é medida faz :func:`para_linhas` falhar, para o mapeamento nunca
perder dado em silêncio quando o modelo crescer.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from interiores_banco import tabelas as t
from interiores_core.carregar import ProjetoCarregado
from interiores_core.modelo import DadosComodo, Projeto, Variacao

Dados = dict[str, Any]


@dataclass(frozen=True)
class Conteudo:
    """Tudo que forma um projeto, já validado pelo core."""

    projeto: Projeto
    comodos: dict[str, DadosComodo] = field(default_factory=dict)
    variacoes: dict[str, dict[str, Variacao]] = field(default_factory=dict)
    regras_toml: str | None = None

    @classmethod
    def de_carregado(cls, c: ProjetoCarregado) -> Conteudo:
        arq = c.pasta / "regras.toml"
        regras = arq.read_text(encoding="utf-8") if arq.is_file() else None
        return cls(c.projeto, dict(c.dados_comodos), dict(c.variacoes), regras)

    def como_dict(self) -> Dados:
        """Forma canônica (para snapshot, hash e comparação)."""
        return {
            "projeto": _dump(self.projeto),
            "comodos": {k: _dump(v) for k, v in sorted(self.comodos.items())},
            "variacoes": {
                c: {n: _dump(v) for n, v in sorted(vs.items())}
                for c, vs in sorted(self.variacoes.items())
            },
            "regras_toml": self.regras_toml,
        }

    @classmethod
    def de_dict(cls, d: Mapping[str, Any]) -> Conteudo:
        return cls(
            Projeto.model_validate(d["projeto"]),
            {k: DadosComodo.model_validate(v) for k, v in d.get("comodos", {}).items()},
            {
                c: {n: Variacao.model_validate(v) for n, v in vs.items()}
                for c, vs in d.get("variacoes", {}).items()
            },
            d.get("regras_toml"),
        )

    @property
    def hash(self) -> str:
        texto = json.dumps(self.como_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(texto.encode()).hexdigest()


def _dump(m: Any) -> Dados:
    return m.model_dump(mode="json", exclude_none=True)  # type: ignore[no-any-return]


# ---------------------------------------------------------------- separar campos


def _eh_medida(v: Any) -> bool:
    return isinstance(v, dict) and "valor" in v and "origem" in v


class _Separador:
    """Tira de um dict as colunas e as medidas; reclama do que sobrar."""

    def __init__(self, projeto: t.Projeto) -> None:
        self.projeto = projeto

    def separar(
        self,
        d: Mapping[str, Any],
        colunas: Iterable[str],
        caminho: str,
        entidade: str,
        pavimento: str | None = None,
        comodo: str | None = None,
        extra: bool = False,
    ) -> tuple[Dados, Dados]:
        cols: Dados = {}
        resto: Dados = {}
        nomes = set(colunas)
        for k, v in d.items():
            if k in nomes:
                cols[k] = v
            elif _eh_medida(v):
                self.projeto.medidas.append(
                    t.Medida(
                        caminho=f"{caminho}.{k}",
                        pavimento=pavimento,
                        comodo=comodo,
                        entidade=entidade,
                        entidade_codigo=d.get("id"),
                        campo=k,
                        valor=v["valor"],
                        origem=v["origem"],
                        obs=v.get("obs"),
                        data=date.fromisoformat(v["data"]) if v.get("data") else None,
                    )
                )
            else:
                resto[k] = v
        if resto and not extra:
            raise ValueError(
                f"{caminho}: campo(s) sem coluna no banco: {', '.join(sorted(resto))} "
                "(atualize interiores_banco.tabelas/mapear e crie uma migração)"
            )
        return cols, resto


# ---------------------------------------------------------------- conteúdo → linhas


def para_linhas(conteudo: Conteudo, linha: t.Projeto) -> None:
    """Substitui pavimentos, entidades e medidas de ``linha`` pelo ``conteudo``."""
    p = _dump(conteudo.projeto)
    linha.pavimentos.clear()
    linha.medidas.clear()
    sep = _Separador(linha)
    linha.codigo = p["projeto"]
    linha.schema_version = p["schema_version"]
    linha.imovel_tipo = p["imovel"]["tipo"]
    linha.endereco_apelido = p["imovel"].get("endereco_apelido")
    linha.regras_toml = conteudo.regras_toml

    for i, pav in enumerate(p["pavimentos"]):
        cam = f"pavimentos[{pav['id']}]"
        ref = {"pavimento": pav["id"]}
        cols, _ = sep.separar(
            {k: v for k, v in pav.items() if not isinstance(v, list)},
            {"id", "nome"},
            cam,
            "pavimento",
            **ref,
        )
        lp = t.Pavimento(codigo=pav["id"], ordem=i, nome=cols.get("nome"))
        linha.pavimentos.append(lp)
        for j, w in enumerate(pav.get("paredes", [])):
            c, _ = sep.separar(
                w,
                {"id", "inicio", "fim", "lado_a", "lado_b"},
                f"{cam}.paredes[{w['id']}]",
                "parede",
                **ref,
            )
            lp.paredes.append(
                t.Parede(
                    codigo=c["id"],
                    ordem=j,
                    inicio_x=c["inicio"][0],
                    inicio_y=c["inicio"][1],
                    fim_x=c["fim"][0],
                    fim_y=c["fim"][1],
                    lado_a=c["lado_a"],
                    lado_b=c["lado_b"],
                )
            )
        for j, a in enumerate(pav.get("aberturas", [])):
            c, _ = sep.separar(
                a,
                {"id", "tipo", "parede", "de", "para", "folha", "abre_para", "dobradica"},
                f"{cam}.aberturas[{a['id']}]",
                "abertura",
                **ref,
            )
            lp.aberturas.append(t.Abertura(codigo=c.pop("id"), ordem=j, **c))
        for j, e in enumerate(pav.get("estrutura", [])):
            c, geo = sep.separar(
                e, {"id", "tipo"}, f"{cam}.estrutura[{e['id']}]", "estrutura", extra=True, **ref
            )
            lp.estrutura.append(t.Estrutura(codigo=c["id"], ordem=j, tipo=c["tipo"], geometria=geo))
        for j, inst in enumerate(pav.get("instalacoes", [])):
            c, _ = sep.separar(
                inst,
                {
                    "id",
                    "forma",
                    "tipo",
                    "posicao",
                    "caminho",
                    "parede",
                    "comodo",
                    "embutido",
                    "obs",
                },
                f"{cam}.instalacoes[{inst['id']}]",
                "instalacao",
                **ref,
            )
            pos = c.pop("posicao", None)
            lp.instalacoes.append(
                t.Instalacao(
                    codigo=c.pop("id"),
                    ordem=j,
                    posicao_x=pos[0] if pos else None,
                    posicao_y=pos[1] if pos else None,
                    **c,
                )
            )
        for j, cm in enumerate(pav.get("comodos", [])):
            c, _ = sep.separar(
                cm,
                {"id", "nome", "tipo", "paredes", "piso", "teto"},
                f"{cam}.comodos[{cm['id']}]",
                "comodo",
                **ref,
            )
            lc = t.Comodo(codigo=c.pop("id"), ordem=j, **c)
            lp.comodos.append(lc)
            _moveis_e_variacoes(conteudo, lc, sep, pav["id"])

    sobrando = set(conteudo.comodos) - {c.codigo for pv in linha.pavimentos for c in pv.comodos}
    if sobrando:
        raise ValueError(f"dados de cômodo inexistente no projeto: {', '.join(sorted(sobrando))}")


def _moveis_e_variacoes(conteudo: Conteudo, lc: t.Comodo, sep: _Separador, pav: str) -> None:
    dados = conteudo.comodos.get(lc.codigo)
    if dados is not None:
        lc.dados_schema_version = dados.schema_version
        for k, m in enumerate(_dump(dados)["moveis"]):
            c, extra = sep.separar(
                m,
                {"id", "tipo", "modelo", "nome", "centro", "rotacao"},
                f"comodos/{lc.codigo}.moveis[{m['id']}]",
                "movel",
                pavimento=pav,
                comodo=lc.codigo,
                extra=True,
            )
            lc.moveis.append(
                t.Movel(
                    codigo=c["id"],
                    ordem=k,
                    tipo=c["tipo"],
                    modelo=c.get("modelo"),
                    nome=c.get("nome"),
                    centro_x=c["centro"][0],
                    centro_y=c["centro"][1],
                    rotacao=c.get("rotacao", 0),
                    extra=extra,
                )
            )
    for nome, var in sorted(conteudo.variacoes.get(lc.codigo, {}).items()):
        lc.variacoes.append(t.Variacao(codigo=nome, dados=_dump(var)))


# ---------------------------------------------------------------- linhas → conteúdo


def _medida(m: t.Medida) -> Dados:
    d: Dados = {"valor": m.valor, "origem": m.origem}
    if m.obs is not None:
        d["obs"] = m.obs
    if m.data is not None:
        d["data"] = m.data.isoformat()
    return d


def _sem_nulos(d: Mapping[str, Any]) -> Dados:
    return {k: v for k, v in d.items() if v is not None}


def de_linhas(linha: t.Projeto) -> Conteudo:
    """Reconstrói o conteúdo (validado pelo core) a partir das linhas do banco."""
    medidas: dict[str, dict[str, Dados]] = {}
    for m in linha.medidas:
        dono, campo = m.caminho.rsplit(".", 1)
        medidas.setdefault(dono, {})[campo] = _medida(m)

    def com(caminho: str, d: Dados) -> Dados:
        return {**_sem_nulos(d), **medidas.get(caminho, {})}

    pavimentos = []
    comodos: dict[str, Dados] = {}
    variacoes: dict[str, dict[str, Variacao]] = {}
    for lp in linha.pavimentos:
        cam = f"pavimentos[{lp.codigo}]"
        pav = com(cam, {"id": lp.codigo, "nome": lp.nome})
        pav["paredes"] = [
            com(
                f"{cam}.paredes[{w.codigo}]",
                {
                    "id": w.codigo,
                    "inicio": [w.inicio_x, w.inicio_y],
                    "fim": [w.fim_x, w.fim_y],
                    "lado_a": w.lado_a,
                    "lado_b": w.lado_b,
                },
            )
            for w in lp.paredes
        ]
        pav["aberturas"] = [
            com(
                f"{cam}.aberturas[{a.codigo}]",
                {
                    "id": a.codigo,
                    "tipo": a.tipo,
                    "parede": a.parede,
                    "de": a.de,
                    "para": a.para,
                    "folha": a.folha,
                    "abre_para": a.abre_para,
                    "dobradica": a.dobradica,
                },
            )
            for a in lp.aberturas
        ]
        pav["estrutura"] = [
            com(f"{cam}.estrutura[{e.codigo}]", {"id": e.codigo, "tipo": e.tipo, **e.geometria})
            for e in lp.estrutura
        ]
        pav["instalacoes"] = [
            com(
                f"{cam}.instalacoes[{i.codigo}]",
                {
                    "id": i.codigo,
                    "forma": i.forma,
                    "tipo": i.tipo,
                    "posicao": [i.posicao_x, i.posicao_y] if i.posicao_x is not None else None,
                    "caminho": i.caminho,
                    "parede": i.parede,
                    "comodo": i.comodo,
                    "embutido": i.embutido,
                    "obs": i.obs,
                },
            )
            for i in lp.instalacoes
        ]
        pav["comodos"] = []
        for c in lp.comodos:
            pav["comodos"].append(
                com(
                    f"{cam}.comodos[{c.codigo}]",
                    {
                        "id": c.codigo,
                        "nome": c.nome,
                        "tipo": c.tipo,
                        "paredes": list(c.paredes),
                        "piso": c.piso,
                        "teto": c.teto,
                    },
                )
            )
            if c.dados_schema_version is not None:
                comodos[c.codigo] = {
                    "schema_version": c.dados_schema_version,
                    "comodo": c.codigo,
                    "moveis": [
                        com(
                            f"comodos/{c.codigo}.moveis[{m.codigo}]",
                            {
                                "id": m.codigo,
                                "tipo": m.tipo,
                                "modelo": m.modelo,
                                "nome": m.nome,
                                "centro": [m.centro_x, m.centro_y],
                                "rotacao": m.rotacao,
                                **m.extra,
                            },
                        )
                        for m in c.moveis
                    ],
                }
            if c.variacoes:
                variacoes[c.codigo] = {
                    v.codigo: Variacao.model_validate(v.dados) for v in c.variacoes
                }
        pavimentos.append(pav)

    imovel = _sem_nulos({"tipo": linha.imovel_tipo, "endereco_apelido": linha.endereco_apelido})
    projeto = Projeto.model_validate(
        {
            "schema_version": linha.schema_version,
            "projeto": linha.codigo,
            "imovel": imovel,
            "pavimentos": pavimentos,
        }
    )
    return Conteudo(
        projeto,
        {k: DadosComodo.model_validate(v) for k, v in comodos.items()},
        variacoes,
        linha.regras_toml,
    )
