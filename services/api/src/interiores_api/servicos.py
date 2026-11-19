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
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from interiores_api.config import Config
from interiores_api.esquemas import (
    InfoRender,
    ItemHistorico,
    MedidaEstimada,
    Mudanca,
    NovoProjeto,
    PedidoRender,
    Preferencias,
    ProjetoCompleto,
    ResultadoEdicao,
    ResumoProjeto,
    ResumoVersao,
    Versoes,
    Vista,
)
from interiores_api.fila import Fila
from interiores_banco import arquivos, renders, repositorio
from interiores_banco import tabelas as t
from interiores_banco import versoes as volta
from interiores_banco.mapear import Conteudo
from interiores_core.carregar import ProjetoCarregado
from interiores_core.edicao import Alteracao, Edicao, renomear_projeto
from interiores_core.edicao_moveis import EdicaoMoveis
from interiores_core.edicao_variacoes import validar_variacao
from interiores_core.modelo import DadosComodo, Projeto, Variacao
from interiores_core.regras import checar
from interiores_core.tela import PavimentoTela, pavimento_para_tela
from interiores_core.validacao import ORDEM_SEVERIDADE, Problema, validar
from interiores_render.cena import vistas_do_comodo
from interiores_render.gerar import IMAGENS_POR_RENDER, QUALIDADES

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


def _info(r: t.Render) -> InfoRender:
    agora = datetime.now(UTC)
    decorrido = ((r.fim or agora) - r.inicio).total_seconds() if r.inicio is not None else None
    restante: float | None = None
    if r.status == "na_fila":
        restante = r.estimativa_s
    elif r.status == "rodando" and decorrido is not None:
        if r.progresso >= 0.05:  # ritmo real do Blender
            restante = decorrido * (1 - r.progresso) / r.progresso
        elif r.estimativa_s is not None:
            restante = max(r.estimativa_s - decorrido, 0.0)
    elif r.status == "pronto":
        restante = 0.0
    nomes = [n for n in (r.arquivos or []) if n.endswith(".png")] if r.status == "pronto" else []
    return InfoRender(
        id=r.id,
        comodo=r.comodo,
        variacao=r.variacao,
        qualidade=r.qualidade,
        vistas=list(r.vistas),
        status=r.status,
        progresso=r.progresso,
        imagem_atual=r.imagem_atual,
        imagens=r.imagens,
        estimativa_s=r.estimativa_s,
        restante_s=round(restante, 1) if restante is not None else None,
        decorrido_s=round(decorrido, 1) if decorrido is not None else None,
        duracao_s=r.duracao_s,
        em_cache=r.em_cache,
        versao_projeto=r.versao_projeto,
        criado_em=r.criado_em.isoformat(),
        erro=r.erro,
        imagens_url=[f"/renders/{r.id}/imagens/{n}" for n in nomes],
    )


@dataclass
class Servico:
    sessao: Session
    config: Config
    fila: Fila | None = None

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

    def versoes(self, codigo: str) -> Versoes:
        """Lista de versões e para onde o desfazer e o refazer levariam agora."""
        lista = repositorio.versoes(self.sessao, codigo)
        ops = {v.versao: v.operacao for v in lista}
        atual = lista[0].versao
        resumos = []
        for v in lista:
            lida = volta.ler_operacao(v.operacao)
            resumos.append(
                ResumoVersao(
                    versao=v.versao,
                    quando=v.quando.isoformat(),
                    operacao=v.operacao,
                    tipo=lida[0] if lida else None,
                    para=lida[1] if lida else None,
                    alteracoes=v.alteracoes,
                    caminhos=v.caminhos,
                )
            )
        return Versoes(
            atual=atual,
            desfazer=volta.alvo_desfazer(ops, atual),
            refazer=volta.alvo_refazer(ops, atual),
            versoes=resumos,
        )

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

    # ------------------------------------------------------------ variações

    def variacoes(self, codigo: str, comodo: str) -> dict[str, Variacao]:
        c, _ = repositorio.ler(self.sessao, codigo)
        if c.projeto.pavimento_do_comodo(comodo) is None:
            raise KeyError(f"cômodo '{comodo}' não existe no projeto")
        return dict(sorted(c.variacoes.get(comodo, {}).items()))

    def salvar_variacao(
        self, codigo: str, versao: int, comodo: str, nome: str, dados: dict[str, object] | None
    ) -> ResultadoEdicao:
        """Cria/substitui (``dados``) ou apaga (``None``) a variação ``nome`` do cômodo."""
        atual, na_base = repositorio.ler(self.sessao, codigo)
        if versao != na_base:
            raise repositorio.ConflitoDeVersaoError(codigo, versao, na_base)
        do_comodo = dict(atual.variacoes.get(comodo, {}))
        if dados is None:
            if nome not in do_comodo:
                raise KeyError(f"variação '{nome}' não existe em '{comodo}'")
            del do_comodo[nome]
        else:
            do_comodo[nome] = validar_variacao(atual.projeto, comodo, nome, dados)
        variacoes = {k: v for k, v in atual.variacoes.items() if k != comodo}
        if do_comodo:
            variacoes[comodo] = do_comodo
        novo = Conteudo(atual.projeto, atual.comodos, variacoes, atual.regras_toml)
        operacao = "remover_variacao" if dados is None else "salvar_variacao"
        nova_versao = self._gravar(novo, operacao, versao)
        hist = self.historico(codigo, versao)
        return ResultadoEdicao(
            versao=nova_versao,
            alteracoes=[Mudanca(caminho=h.caminho, antes=h.antes, depois=h.depois) for h in hist],
            novos=[],
            problemas=[],
        )

    # ------------------------------------------------------------ render (fila)

    def pedir_render(self, codigo: str, comodo: str, pedido: PedidoRender) -> InfoRender:
        """Põe o render na fila (ou devolve o mesmo pedido, se já estiver na fila)."""
        c, _ = repositorio.ler(self.sessao, codigo)
        if c.projeto.pavimento_do_comodo(comodo) is None:
            raise KeyError(f"cômodo '{comodo}' não existe no projeto")
        if pedido.variacao != "base" and pedido.variacao not in c.variacoes.get(comodo, {}):
            raise KeyError(f"variação '{pedido.variacao}' não existe em '{comodo}'")
        disponiveis = {v.nome for v in self._vistas(c, comodo)}
        fora = [v for v in pedido.vistas if v not in disponiveis]
        if fora:
            raise ValueError(
                f"vista(s) {', '.join(fora)} não existem em '{comodo}' "
                f"({', '.join(sorted(disponiveis))})"
            )
        if self.fila is None:
            raise RuntimeError("fila de render não configurada")
        vistas = list(dict.fromkeys(pedido.vistas))  # sem repetidas, na ordem pedida
        r, novo = renders.pedir(
            self.sessao, codigo, comodo, pedido.variacao, pedido.qualidade,
            QUALIDADES[pedido.qualidade], vistas,
        )  # fmt: skip
        if novo:
            self.sessao.commit()  # o worker precisa enxergar o pedido
            self.fila.enfileirar(r.id)
            log.info("render na fila", render=r.id, projeto=codigo, comodo=comodo)
        return _info(r)

    def estimativas(self, imagens: int = IMAGENS_POR_RENDER) -> dict[str, float]:
        """Segundos estimados por qualidade, pelo histórico desta máquina."""
        return {
            q: renders.estimar_s(self.sessao, *tamanho, imagens)
            for q, tamanho in QUALIDADES.items()
        }

    @staticmethod
    def _vistas(c: Conteudo, comodo: str) -> list[Vista]:
        carregado = ProjetoCarregado(
            pasta=Path(), projeto=c.projeto, dados_comodos=c.comodos, variacoes=c.variacoes
        )
        return [Vista(**v) for v in vistas_do_comodo(carregado, comodo)]

    def vistas(self, codigo: str, comodo: str) -> list[Vista]:
        """Câmeras que fazem sentido no cômodo (porta, cama, cantos...)."""
        c, _ = repositorio.ler(self.sessao, codigo)
        if c.projeto.pavimento_do_comodo(comodo) is None:
            raise KeyError(f"cômodo '{comodo}' não existe no projeto")
        return self._vistas(c, comodo)

    def renders(self, codigo: str, comodo: str | None) -> list[InfoRender]:
        self._id(codigo)
        return [_info(r) for r in renders.listar(self.sessao, codigo, comodo)]

    def render(self, id_: int) -> InfoRender:
        return _info(renders.obter(self.sessao, id_))

    def imagem_render(self, id_: int, nome: str) -> Path:
        """Arquivo de imagem de um render pronto (só os nomes conhecidos)."""
        r = renders.obter(self.sessao, id_)
        validos = [n for n in (r.arquivos or []) if n.endswith(".png")]
        if nome not in validos or r.status != "pronto" or r.pasta is None:
            raise KeyError(f"imagem '{nome}' não existe no render {id_}")
        arq = Path(r.pasta) / nome
        if not arq.is_file():
            raise KeyError(f"imagem '{nome}' do render {id_} não está mais em disco")
        return arq

    # ------------------------------------------------------------ projeto inteiro

    def voltar(
        self, codigo: str, versao: int, tipo: volta.Tipo, para: int | None = None
    ) -> ResultadoEdicao:
        """Desfaz, refaz ou volta para a versão ``para`` gravando o conteúdo dela como
        versão nova (nada é apagado). O código do projeto atual é mantido."""
        atual, na_base = repositorio.ler(self.sessao, codigo)
        if versao != na_base:
            raise repositorio.ConflitoDeVersaoError(codigo, versao, na_base)
        if tipo == "reverter":
            if para is None or para == na_base:
                raise ValueError("escolha uma versão diferente da atual para voltar")
        else:
            ops = repositorio.operacoes(self.sessao, codigo)
            alvo = volta.alvo_desfazer if tipo == "desfazer" else volta.alvo_refazer
            para = alvo(ops, na_base)
            if para is None:
                raise ValueError(f"nada para {tipo}")
        antigo = repositorio.snapshot(self.sessao, codigo, para)
        projeto = antigo.projeto.model_copy(update={"projeto": codigo})  # sobrevive a renomear
        novo = Conteudo(projeto, antigo.comodos, antigo.variacoes, antigo.regras_toml)
        if novo.hash == atual.hash:
            raise ValueError(f"a versão {para} é igual à atual: nada para {tipo}")
        nova_versao = self._gravar(novo, volta.operacao(tipo, para), versao)
        hist = self.historico(codigo, versao)
        probs = sorted(
            validar(novo.projeto, novo.comodos), key=lambda p: ORDEM_SEVERIDADE[p.severidade]
        )
        return ResultadoEdicao(
            versao=nova_versao,
            alteracoes=[Mudanca(caminho=h.caminho, antes=h.antes, depois=h.depois) for h in hist],
            novos=[],
            problemas=probs,
        )

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
