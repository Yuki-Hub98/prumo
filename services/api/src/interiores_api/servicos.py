"""Camada de serviço (pré-filtro entre as rotas e o core).

Aqui fica a orquestração: carregar o projeto do banco, chamar a função de edição
do core, gravar a versão nova com histórico, reexportar o JSON e registrar o
log. **Regra de negócio não entra aqui**: quem decide se a edição é válida é o
``interiores_core.edicao``; aqui só se confere o que é do pedido (projeto
existe, versão em que o pedido foi feito, formato) e se traduz o resultado.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from interiores_api.config import Config
from interiores_api.esquemas import (
    ItemHistorico,
    MedidaEstimada,
    Mudanca,
    NovoProjeto,
    Preferencias,
    ProjetoCompleto,
    ResultadoEdicao,
    ResumoProjeto,
)
from interiores_banco import arquivos, repositorio
from interiores_banco import tabelas as t
from interiores_banco.mapear import Conteudo
from interiores_core.edicao import Alteracao, Edicao, renomear_projeto
from interiores_core.edicao_moveis import EdicaoMoveis
from interiores_core.modelo import DadosComodo, Projeto
from interiores_core.regras import checar
from interiores_core.tela import PavimentoTela, pavimento_para_tela
from interiores_core.validacao import ORDEM_SEVERIDADE, Problema, validar

log = structlog.get_logger("interiores.api")

Operacao = Callable[[Projeto], Edicao]
OperacaoMoveis = Callable[[Projeto, DadosComodo | None, dict[str, object]], EdicaoMoveis]


def _completo(conteudo: Conteudo, versao: int) -> ProjetoCompleto:
    return ProjetoCompleto(
        versao=versao,
        projeto=conteudo.projeto,
        comodos=conteudo.comodos,
        variacoes=conteudo.variacoes,
    )


def _mudancas(alteracoes: list[Alteracao]) -> list[Mudanca]:
    return [Mudanca(caminho=a.caminho, antes=a.antes, depois=a.depois) for a in alteracoes]


@dataclass
class Servico:
    sessao: Session
    config: Config

    # ------------------------------------------------------------ leitura

    def listar(self) -> list[ResumoProjeto]:
        linhas = self.sessao.scalars(select(t.Projeto).order_by(t.Projeto.codigo))
        return [
            ResumoProjeto(
                codigo=p.codigo, versao=p.versao, imovel=p.imovel_tipo, apelido=p.endereco_apelido
            )
            for p in linhas
        ]

    def ler(self, codigo: str) -> ProjetoCompleto:
        conteudo, versao = repositorio.ler(self.sessao, codigo)
        return _completo(conteudo, versao)

    def versao(self, codigo: str, versao: int) -> ProjetoCompleto:
        return _completo(repositorio.snapshot(self.sessao, codigo, versao), versao)

    def geometria(self, codigo: str, pavimento: str) -> PavimentoTela:
        c, _ = repositorio.ler(self.sessao, codigo)
        pav = next((p for p in c.projeto.pavimentos if p.id == pavimento), None)
        if pav is None:
            raise KeyError(f"pavimento '{pavimento}' não existe")
        return pavimento_para_tela(pav, c.comodos)

    def preferencias(self) -> Preferencias:
        linhas = self.sessao.scalars(select(t.Preferencia))
        return Preferencias.model_validate({p.chave: p.valor for p in linhas})

    def salvar_preferencias(self, novas: Preferencias) -> Preferencias:
        for chave, valor in novas.model_dump(mode="json", exclude_unset=True).items():
            self.sessao.merge(t.Preferencia(chave=chave, valor=valor))
        self.sessao.flush()
        return self.preferencias()

    def problemas(self, codigo: str) -> list[Problema]:
        """Validação estrutural + checagens de uso (passagem, cama, portas...)."""
        c, _ = repositorio.ler(self.sessao, codigo)
        regras = tomllib.loads(c.regras_toml) if c.regras_toml else {}
        todos = validar(c.projeto, c.comodos) + checar(c.projeto, c.comodos, regras)
        return sorted(todos, key=lambda p: ORDEM_SEVERIDADE[p.severidade])

    def _id(self, codigo: str) -> int:
        id_ = self.sessao.scalar(select(t.Projeto.id).where(t.Projeto.codigo == codigo))
        if id_ is None:
            raise repositorio.ProjetoInexistenteError(f"projeto '{codigo}' não está no banco")
        return id_

    def estimadas(self, codigo: str) -> list[MedidaEstimada]:
        """A lista "falta medir": toda medida ainda com origem estimada."""
        linhas = self.sessao.scalars(
            select(t.Medida)
            .where(t.Medida.projeto_id == self._id(codigo), t.Medida.origem == "estimada")
            .order_by(t.Medida.caminho)
        )
        return [
            MedidaEstimada(
                caminho=m.caminho,
                pavimento=m.pavimento,
                comodo=m.comodo,
                entidade=m.entidade,
                entidade_codigo=m.entidade_codigo,
                campo=m.campo,
                valor=m.valor,
                obs=m.obs,
            )
            for m in linhas
        ]

    def historico(self, codigo: str, desde: int = 0) -> list[ItemHistorico]:
        linhas = self.sessao.scalars(
            select(t.Historico)
            .where(t.Historico.projeto_id == self._id(codigo), t.Historico.versao > desde)
            .order_by(t.Historico.versao, t.Historico.id)
        )
        return [
            ItemHistorico(
                versao=h.versao,
                quando=h.quando.isoformat(),
                fonte=h.fonte,
                operacao=h.operacao,
                caminho=h.caminho,
                antes=h.antes,
                depois=h.depois,
            )
            for h in linhas
        ]

    # ------------------------------------------------------------ escrita

    def _gravar(
        self,
        conteudo: Conteudo,
        operacao: str,
        versao: int | None,
        alteracoes: list[Alteracao] | None = None,
    ) -> int:
        codigo = conteudo.projeto.projeto
        gravado = repositorio.gravar(
            self.sessao,
            conteudo,
            fonte="api",
            operacao=operacao,
            versao_esperada=versao,
            alteracoes=alteracoes,
        )
        if self.config.exportar and gravado.alteracoes:
            arquivos.exportar(self.sessao, codigo, self.config.pasta_projetos / codigo)
        log.info(
            "projeto gravado",
            projeto=codigo,
            operacao=operacao,
            versao=gravado.versao,
            alteracoes=len(gravado.alteracoes),
        )
        return gravado.versao

    def criar(self, novo: NovoProjeto) -> ProjetoCompleto:
        if novo.codigo in {p.codigo for p in self.listar()}:
            raise ValueError(f"já existe um projeto '{novo.codigo}'")
        projeto = Projeto.model_validate(
            {
                "schema_version": 1,
                "projeto": novo.codigo,
                "imovel": {"tipo": novo.imovel, "endereco_apelido": novo.apelido},
                "pavimentos": [novo.pavimento.model_dump(mode="json", exclude_none=True)],
            }
        )
        conteudo = Conteudo(projeto)
        versao = self._gravar(conteudo, "criar_projeto", versao=0)
        return _completo(conteudo, versao)

    def editar(
        self,
        codigo: str,
        versao: int,
        nome: str,
        operacao: Operacao,
        remover_comodos: list[str] | None = None,
    ) -> ResultadoEdicao:
        """Aplica uma edição do core em cima da ``versao`` que o pedido viu.

        ``remover_comodos`` tira também o mobiliário e as variações desses cômodos,
        que não fazem parte do ``Projeto`` (orquestração, não regra).
        """
        atual, na_base = repositorio.ler(self.sessao, codigo)
        if versao != na_base:
            raise repositorio.ConflitoDeVersaoError(codigo, versao, na_base)
        ed = operacao(atual.projeto)
        comodos, variacoes = dict(atual.comodos), dict(atual.variacoes)
        for c in remover_comodos or []:
            comodos.pop(c, None)
            variacoes.pop(c, None)
        novo = Conteudo(ed.projeto, comodos, variacoes, atual.regras_toml)
        # removendo cômodo o mobiliário também muda: a diferença é recalculada inteira
        alteracoes = None if remover_comodos else repositorio.do_projeto(ed.alteracoes)
        nova_versao = self._gravar(novo, nome, versao, alteracoes)
        return ResultadoEdicao(
            versao=nova_versao,
            alteracoes=_mudancas(repositorio.do_projeto(ed.alteracoes)),
            novos=ed.novos,
            problemas=ed.problemas,
        )

    def editar_moveis(
        self, codigo: str, versao: int, comodo: str, nome: str, operacao: OperacaoMoveis
    ) -> ResultadoEdicao:
        """Edição do mobiliário de ``comodo`` (``comodos/<id>.json``) sobre a ``versao``."""
        atual, na_base = repositorio.ler(self.sessao, codigo)
        if versao != na_base:
            raise repositorio.ConflitoDeVersaoError(codigo, versao, na_base)
        regras = tomllib.loads(atual.regras_toml) if atual.regras_toml else {}
        ed = operacao(atual.projeto, atual.comodos.get(comodo), regras)
        comodos = {**atual.comodos, comodo: ed.dados}
        novo = Conteudo(atual.projeto, comodos, atual.variacoes, atual.regras_toml)
        nova_versao = self._gravar(novo, nome, versao, ed.alteracoes)
        return ResultadoEdicao(
            versao=nova_versao,
            alteracoes=_mudancas(ed.alteracoes),
            novos=ed.novos,
            problemas=ed.problemas,
        )

    # ------------------------------------------------------------ projeto inteiro

    def renomear(self, codigo: str, versao: int, novo: str) -> ResultadoEdicao:
        """Troca o código; a pasta ``projetos/<codigo>`` (com as referências) vai junto."""
        atual, na_base = repositorio.ler(self.sessao, codigo)
        if versao != na_base:
            raise repositorio.ConflitoDeVersaoError(codigo, versao, na_base)
        ed = renomear_projeto(atual.projeto, novo)
        conteudo = Conteudo(ed.projeto, atual.comodos, atual.variacoes, atual.regras_toml)
        alteracoes = repositorio.do_projeto(ed.alteracoes)
        gravado = repositorio.renomear(self.sessao, codigo, conteudo, versao, alteracoes)
        velha, nova = self.config.pasta_projetos / codigo, self.config.pasta_projetos / novo
        if self.config.exportar:
            if velha.is_dir() and not nova.exists():
                velha.rename(nova)
            arquivos.exportar(self.sessao, novo, nova)
        log.info("projeto renomeado", de=codigo, para=novo, versao=gravado.versao)
        return ResultadoEdicao(
            versao=gravado.versao, alteracoes=_mudancas(alteracoes), novos=ed.novos,
            problemas=ed.problemas,
        )  # fmt: skip

    def apagar(self, codigo: str, versao: int, confirmar: str) -> str | None:
        """Apaga do banco. A pasta não é apagada: vai para ``projetos/_apagados/``
        (pode ter fotos e croquis que não estão no banco). Devolve o novo caminho."""
        if confirmar != codigo:
            raise ValueError(f"para apagar, confirme repetindo o código: confirmar={codigo}")
        repositorio.apagar(self.sessao, codigo, versao)
        pasta = self.config.pasta_projetos / codigo
        destino = None
        if pasta.is_dir():
            carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
            destino = self.config.pasta_projetos / "_apagados" / f"{codigo}-{carimbo}"
            destino.parent.mkdir(parents=True, exist_ok=True)
            pasta.rename(destino)
        log.info("projeto apagado", projeto=codigo, pasta_movida_para=str(destino))
        return str(destino) if destino else None
