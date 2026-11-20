"""Gravar e ler projetos no banco, com versão, histórico e snapshot.

Cada gravação:

1. confere a versão esperada (concorrência otimista: quem editou em cima de uma
   versão velha recebe :class:`ConflitoDeVersaoError`);
2. substitui as linhas das entidades pelo conteúdo novo;
3. sobe ``versao``, grava o ``snapshot`` e uma linha de ``historico`` por alteração
   (antes → depois, pelo caminho com ids).

Versões acima da atual são passos de rascunho desfeitos (guardados para o refazer,
ver :mod:`interiores_banco.rascunho`); uma gravação nova apaga esses passos.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from interiores_banco import tabelas as t
from interiores_banco.mapear import Conteudo, de_linhas, para_linhas
from interiores_core.edicao import Alteracao, diferencas


class ProjetoInexistenteError(LookupError):
    pass


class ConflitoDeVersaoError(RuntimeError):
    """O projeto mudou desde a versão em que a edição foi feita."""

    def __init__(self, codigo: str, esperada: int, atual: int) -> None:
        super().__init__(
            f"projeto '{codigo}' está na versão {atual}, a edição partiu da {esperada}"
        )
        self.esperada, self.atual = esperada, atual


@dataclass(frozen=True)
class Gravado:
    versao: int
    alteracoes: list[Alteracao]
    """Vazia quando o conteúdo não mudou (nada é gravado)."""


def _carregar(sessao: Session, codigo: str, travar: bool = False) -> t.Projeto | None:
    consulta = (
        select(t.Projeto)
        .where(t.Projeto.codigo == codigo)
        .options(
            selectinload(t.Projeto.medidas),
            selectinload(t.Projeto.pavimentos).selectinload(t.Pavimento.paredes),
            selectinload(t.Projeto.pavimentos).selectinload(t.Pavimento.aberturas),
            selectinload(t.Projeto.pavimentos).selectinload(t.Pavimento.estrutura),
            selectinload(t.Projeto.pavimentos).selectinload(t.Pavimento.instalacoes),
            selectinload(t.Projeto.pavimentos)
            .selectinload(t.Pavimento.comodos)
            .selectinload(t.Comodo.moveis),
            selectinload(t.Projeto.pavimentos)
            .selectinload(t.Pavimento.comodos)
            .selectinload(t.Comodo.variacoes),
        )
    )
    if travar:  # gravação: segura a linha até o commit
        consulta = consulta.with_for_update(of=t.Projeto)
    return sessao.scalars(consulta).first()


def linha_para_gravar(sessao: Session, codigo: str) -> t.Projeto | None:
    """A linha do projeto travada até o commit (para operações que gravam)."""
    return _carregar(sessao, codigo, travar=True)


def do_projeto(alteracoes: Iterable[Alteracao]) -> list[Alteracao]:
    """Põe no caminho o prefixo ``projeto.`` das alterações feitas no ``Projeto``
    (ex.: de :class:`interiores_core.edicao.Edicao`), para casar com o caminho das
    diferenças calculadas sobre o conteúdo inteiro (``projeto``, ``comodos``...)."""
    return [Alteracao(f"projeto.{a.caminho}", a.antes, a.depois) for a in alteracoes]


def codigos(sessao: Session) -> list[str]:
    return list(sessao.scalars(select(t.Projeto.codigo).order_by(t.Projeto.codigo)))


def ler(sessao: Session, codigo: str) -> tuple[Conteudo, int]:
    """Conteúdo atual e versão. Levanta :class:`ProjetoInexistenteError`."""
    linha = _carregar(sessao, codigo)
    if linha is None:
        raise ProjetoInexistenteError(f"projeto '{codigo}' não está no banco")
    return de_linhas(linha), linha.versao


def gravar(
    sessao: Session,
    conteudo: Conteudo,
    fonte: str,
    operacao: str | None = None,
    versao_esperada: int | None = None,
    alteracoes: Iterable[Alteracao] | None = None,
    rascunho: bool = False,
) -> Gravado:
    """Grava o conteúdo como nova versão (ou cria o projeto). Não faz commit.

    ``rascunho``: a versão é um passo de rascunho (abre o rascunho se não houver).

    ``alteracoes`` evita recalcular a diferença (caminhos relativos ao conteúdo
    inteiro; para as de uma ``Edicao`` use :func:`do_projeto`); sem elas, a
    diferença é calculada contra a versão atual.
    """
    codigo = conteudo.projeto.projeto
    linha = _carregar(sessao, codigo, travar=True)
    hash_novo = conteudo.hash
    if linha is None:
        if versao_esperada not in (None, 0):
            raise ConflitoDeVersaoError(codigo, versao_esperada, 0)
        linha = t.Projeto(versao=0, hash_conteudo="")
        anterior: dict[str, object] = {}
    else:
        if versao_esperada is not None and versao_esperada != linha.versao:
            raise ConflitoDeVersaoError(codigo, versao_esperada, linha.versao)
        if linha.hash_conteudo == hash_novo:
            return Gravado(linha.versao, [])
        anterior = de_linhas(linha).como_dict()
    lista = (
        list(alteracoes)
        if alteracoes is not None
        else list(diferencas(anterior, conteudo.como_dict()))
    )
    if linha.versao:
        apagar_acima(sessao, linha.id, linha.versao)  # passos desfeitos: sem refazer agora
        if rascunho and linha.rascunho_desde is None:
            linha.rascunho_desde = linha.versao
    substituir(sessao, linha, conteudo)
    linha.versao += 1
    sessao.flush()
    sessao.add(
        t.Snapshot(
            projeto_id=linha.id,
            versao=linha.versao,
            hash_conteudo=hash_novo,
            conteudo=conteudo.como_dict(),
        )
    )
    for a in lista:
        sessao.add(
            t.Historico(
                projeto_id=linha.id,
                versao=linha.versao,
                fonte=fonte,
                operacao=operacao,
                caminho=a.caminho or "(projeto)",
                antes=a.antes,
                depois=a.depois,
            )
        )
    sessao.flush()
    return Gravado(linha.versao, lista)


def substituir(sessao: Session, linha: t.Projeto, conteudo: Conteudo) -> None:
    """Troca as linhas das entidades pelo ``conteudo`` (sem mexer na versão)."""
    if linha.versao:
        # apaga as linhas atuais antes de inserir as novas (senão as restrições de
        # unicidade, como medida.caminho, colidem: o flush insere antes de apagar)
        linha.pavimentos.clear()
        linha.medidas.clear()
        sessao.flush()
    para_linhas(conteudo, linha)
    sessao.add(linha)
    linha.hash_conteudo = conteudo.hash
    sessao.flush()


def apagar_acima(sessao: Session, projeto_id: int, versao: int) -> None:
    """Apaga snapshot e histórico das versões acima de ``versao`` (passos desfeitos)."""
    sessao.execute(
        delete(t.Snapshot).where(t.Snapshot.projeto_id == projeto_id, t.Snapshot.versao > versao)
    )
    sessao.execute(
        delete(t.Historico).where(t.Historico.projeto_id == projeto_id, t.Historico.versao > versao)
    )
    sessao.flush()


def marcar_exportado(sessao: Session, codigo: str, versao: int, hash_arquivos: str) -> None:
    """Registra que ``projetos/<codigo>/`` está igual à ``versao`` do banco."""
    linha = sessao.scalars(select(t.Projeto).where(t.Projeto.codigo == codigo)).one()
    linha.versao_exportada, linha.hash_exportado = versao, hash_arquivos
    sessao.flush()


def snapshot(sessao: Session, codigo: str, versao: int) -> Conteudo:
    """Conteúdo de uma versão antiga (para comparar ou restaurar)."""
    s = sessao.scalars(
        select(t.Snapshot)
        .join(t.Projeto)
        .where(t.Projeto.codigo == codigo, t.Snapshot.versao == versao)
    ).first()
    if s is None:
        raise ProjetoInexistenteError(f"projeto '{codigo}' não tem a versão {versao}")
    return Conteudo.de_dict(s.conteudo)


@dataclass(frozen=True)
class ResumoVersao:
    versao: int
    quando: datetime
    operacao: str | None
    alteracoes: int
    caminhos: list[str]
    """Até 5 caminhos alterados, para a tela resumir o que mudou."""


def versoes(sessao: Session, codigo: str) -> list[ResumoVersao]:
    """Todas as versões do projeto até a atual, da mais nova para a mais velha (sem os
    passos de rascunho desfeitos, que ficam acima da atual)."""
    linha = sessao.execute(
        select(t.Projeto.id, t.Projeto.versao).where(t.Projeto.codigo == codigo)
    ).first()
    if linha is None:
        raise ProjetoInexistenteError(f"projeto '{codigo}' não está no banco")
    projeto_id, atual = linha
    quando = dict(
        sessao.execute(
            select(t.Snapshot.versao, t.Snapshot.quando).where(
                t.Snapshot.projeto_id == projeto_id, t.Snapshot.versao <= atual
            )
        ).all()
    )
    por_versao: dict[int, tuple[str | None, list[str]]] = {}
    for versao, op, caminho in sessao.execute(
        select(t.Historico.versao, t.Historico.operacao, t.Historico.caminho)
        .where(t.Historico.projeto_id == projeto_id, t.Historico.versao <= atual)
        .order_by(t.Historico.versao, t.Historico.id)
    ):
        _, caminhos = por_versao.setdefault(versao, (op, []))
        caminhos.append(caminho)
    return [
        ResumoVersao(
            versao=v,
            quando=q,
            operacao=por_versao.get(v, (None, []))[0],
            alteracoes=len(por_versao.get(v, (None, []))[1]),
            caminhos=por_versao.get(v, (None, []))[1][:5],
        )
        for v, q in sorted(quando.items(), reverse=True)
    ]


def operacoes(sessao: Session, codigo: str) -> dict[int, str | None]:
    """Operação de cada versão (``{versao: operacao}``), para desfazer/refazer."""
    return {r.versao: r.operacao for r in versoes(sessao, codigo)}


def apagar(sessao: Session, codigo: str, versao_esperada: int) -> None:
    """Apaga o projeto e tudo dele (entidades, medidas, histórico, snapshots)."""
    linha = _carregar(sessao, codigo, travar=True)
    if linha is None:
        raise ProjetoInexistenteError(f"projeto '{codigo}' não está no banco")
    if linha.versao != versao_esperada:
        raise ConflitoDeVersaoError(codigo, versao_esperada, linha.versao)
    sessao.delete(linha)
    sessao.flush()


def renomear(
    sessao: Session,
    de: str,
    conteudo: Conteudo,
    versao_esperada: int,
    alteracoes: Iterable[Alteracao] | None = None,
    fonte: str = "api",
) -> Gravado:
    """Troca o código do projeto ``de`` para o de ``conteudo`` (nova versão).

    Histórico e snapshots continuam ligados ao mesmo projeto.
    """
    para = conteudo.projeto.projeto
    if _carregar(sessao, para) is not None:
        raise ValueError(f"já existe um projeto '{para}'")
    linha = _carregar(sessao, de, travar=True)
    if linha is None:
        raise ProjetoInexistenteError(f"projeto '{de}' não está no banco")
    if linha.versao != versao_esperada:
        raise ConflitoDeVersaoError(de, versao_esperada, linha.versao)
    linha.codigo = para
    sessao.flush()
    return gravar(
        sessao,
        conteudo,
        fonte=fonte,
        operacao="renomear_projeto",
        versao_esperada=versao_esperada,
        alteracoes=alteracoes,
    )
