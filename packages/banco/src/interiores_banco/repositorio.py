"""Gravar e ler projetos no banco, com versão, histórico e snapshot.

Cada gravação:

1. confere a versão esperada (concorrência otimista: quem editou em cima de uma
   versão velha recebe :class:`ConflitoDeVersaoError`);
2. substitui as linhas das entidades pelo conteúdo novo;
3. sobe ``versao``, grava o ``snapshot`` e uma linha de ``historico`` por alteração
   (antes → depois, pelo caminho com ids).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
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
) -> Gravado:
    """Grava o conteúdo como nova versão (ou cria o projeto). Não faz commit.

    ``alteracoes`` (ex.: de :class:`interiores_core.edicao.Edicao`) evita recalcular
    a diferença; sem elas, a diferença é calculada contra a versão atual.
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
        # apaga as linhas atuais antes de inserir as novas (senão as restrições de
        # unicidade, como medida.caminho, colidem: o flush insere antes de apagar)
        linha.pavimentos.clear()
        linha.medidas.clear()
        sessao.flush()
    para_linhas(conteudo, linha)
    sessao.add(linha)
    linha.versao += 1
    linha.hash_conteudo = hash_novo
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
