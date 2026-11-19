"""Rotas HTTP. Cada rota só traduz o pedido para o serviço; nada de regra aqui.

Toda edição exige ``?versao=`` (a versão que a tela estava vendo): se alguém
gravou antes, a resposta é 409 e a tela recarrega em vez de atropelar.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from interiores_api.esquemas import (
    AlterarComodo,
    AlterarInstalacao,
    AlterarParede,
    Campos,
    DividirParede,
    ItemHistorico,
    MedidaEstimada,
    MoverVertice,
    NovaAbertura,
    NovaInstalacao,
    NovoComodo,
    NovoProjeto,
    ProjetoCompleto,
    ResultadoEdicao,
    ResumoProjeto,
)
from interiores_api.servicos import Servico
from interiores_banco.conexao import sessao as abrir_sessao
from interiores_core import edicao
from interiores_core.modelo import Parede
from interiores_core.validacao import Problema


def servico(request: Request) -> Iterator[Servico]:
    """Uma transação por pedido: commit se deu certo, rollback se deu erro."""
    with abrir_sessao(request.app.state.engine) as s:
        yield Servico(s, request.app.state.config)


Svc = Annotated[Servico, Depends(servico)]
Versao = Annotated[int, Query(ge=0, description="Versão do projeto que a tela estava vendo.")]

projetos = APIRouter(prefix="/projetos", tags=["projetos"])
planta = APIRouter(prefix="/projetos/{codigo}/pavimentos/{pavimento}", tags=["planta"])


# ---------------------------------------------------------------- projetos


@projetos.get("")
def listar(svc: Svc) -> list[ResumoProjeto]:
    return svc.listar()


@projetos.post("", status_code=status.HTTP_201_CREATED)
def criar(svc: Svc, novo: NovoProjeto) -> ProjetoCompleto:
    """Projeto novo, vazio (um pavimento), para desenhar do zero."""
    return svc.criar(novo)


@projetos.get("/{codigo}")
def ler(svc: Svc, codigo: str) -> ProjetoCompleto:
    return svc.ler(codigo)


@projetos.get("/{codigo}/problemas")
def problemas(svc: Svc, codigo: str) -> list[Problema]:
    """Erros, avisos e infos (validação + checagens), por severidade."""
    return svc.problemas(codigo)


@projetos.get("/{codigo}/estimadas")
def estimadas(svc: Svc, codigo: str) -> list[MedidaEstimada]:
    """Lista "falta medir": enquanto não zerar, os desenhos saem PRELIMINAR."""
    return svc.estimadas(codigo)


@projetos.get("/{codigo}/historico")
def historico(svc: Svc, codigo: str, desde: int = 0) -> list[ItemHistorico]:
    return svc.historico(codigo, desde)


@projetos.get("/{codigo}/versoes/{versao}")
def versao(svc: Svc, codigo: str, versao: int) -> ProjetoCompleto:
    return svc.versao(codigo, versao)


# ---------------------------------------------------------------- planta


@planta.patch("")
def alterar_pavimento(
    svc: Svc, codigo: str, pavimento: str, versao: Versao, campos: Campos
) -> ResultadoEdicao:
    """Nome, cota do piso, pé-direito, rodapé."""
    return svc.editar(
        codigo, versao, "alterar_pavimento",
        lambda p: edicao.alterar_pavimento(p, pavimento, campos),
    )  # fmt: skip


@planta.post("/paredes")
def adicionar_parede(
    svc: Svc, codigo: str, pavimento: str, versao: Versao, parede: Parede
) -> ResultadoEdicao:
    return svc.editar(
        codigo, versao, "adicionar_parede",
        lambda p: edicao.adicionar_parede(p, pavimento, parede),
    )  # fmt: skip


@planta.patch("/paredes/{id_}")
def alterar_parede(
    svc: Svc, codigo: str, pavimento: str, id_: str, versao: Versao, pedido: AlterarParede
) -> ResultadoEdicao:
    """Mudar uma ponta arrasta as paredes que se encontram nela (``arrastar_vizinhas``)."""
    return svc.editar(
        codigo, versao, "alterar_parede",
        lambda p: edicao.alterar_parede(
            p, pavimento, id_, pedido.campos, pedido.arrastar_vizinhas
        ),
    )  # fmt: skip


@planta.post("/paredes/{id_}/dividir")
def dividir_parede(
    svc: Svc, codigo: str, pavimento: str, id_: str, versao: Versao, pedido: DividirParede
) -> ResultadoEdicao:
    return svc.editar(
        codigo, versao, "dividir_parede",
        lambda p: edicao.dividir_parede(p, pavimento, id_, pedido.distancia, pedido.novo_id),
    )  # fmt: skip


@planta.delete("/paredes/{id_}")
def remover_parede(
    svc: Svc, codigo: str, pavimento: str, id_: str, versao: Versao, cascata: bool = False
) -> ResultadoEdicao:
    return svc.editar(
        codigo, versao, "remover_parede",
        lambda p: edicao.remover_parede(p, pavimento, id_, cascata),
    )  # fmt: skip


@planta.post("/vertices/mover")
def mover_vertice(
    svc: Svc, codigo: str, pavimento: str, versao: Versao, pedido: MoverVertice
) -> ResultadoEdicao:
    """Arrastar um canto: toda ponta de parede nele vai junto."""
    return svc.editar(
        codigo, versao, "mover_vertice",
        lambda p: edicao.mover_vertice(p, pavimento, pedido.de, pedido.para),
    )  # fmt: skip


@planta.post("/aberturas")
def adicionar_abertura(
    svc: Svc, codigo: str, pavimento: str, versao: Versao, abertura: NovaAbertura
) -> ResultadoEdicao:
    """Porta ou janela (campo ``tipo``)."""
    return svc.editar(
        codigo, versao, "adicionar_abertura",
        lambda p: edicao.adicionar_abertura(p, pavimento, abertura),
    )  # fmt: skip


@planta.patch("/aberturas/{id_}")
def alterar_abertura(
    svc: Svc, codigo: str, pavimento: str, id_: str, versao: Versao, campos: Campos
) -> ResultadoEdicao:
    return svc.editar(
        codigo, versao, "alterar_abertura",
        lambda p: edicao.alterar_abertura(p, pavimento, id_, campos),
    )  # fmt: skip


@planta.delete("/aberturas/{id_}")
def remover_abertura(
    svc: Svc, codigo: str, pavimento: str, id_: str, versao: Versao
) -> ResultadoEdicao:
    return svc.editar(
        codigo, versao, "remover_abertura",
        lambda p: edicao.remover_abertura(p, pavimento, id_),
    )  # fmt: skip


@planta.post("/comodos")
def adicionar_comodo(
    svc: Svc, codigo: str, pavimento: str, versao: Versao, pedido: NovoComodo
) -> ResultadoEdicao:
    """O cômodo é posto no lado certo de cada parede pela geometria."""
    return svc.editar(
        codigo, versao, "adicionar_comodo",
        lambda p: edicao.adicionar_comodo(p, pavimento, pedido.comodo, pedido.ajustar_lados),
    )  # fmt: skip


@planta.patch("/comodos/{id_}")
def alterar_comodo(
    svc: Svc, codigo: str, pavimento: str, id_: str, versao: Versao, pedido: AlterarComodo
) -> ResultadoEdicao:
    return svc.editar(
        codigo, versao, "alterar_comodo",
        lambda p: edicao.alterar_comodo(p, pavimento, id_, pedido.campos, pedido.ajustar_lados),
    )  # fmt: skip


@planta.delete("/comodos/{id_}")
def remover_comodo(
    svc: Svc, codigo: str, pavimento: str, id_: str, versao: Versao
) -> ResultadoEdicao:
    """Remove também o mobiliário e as variações do cômodo."""
    return svc.editar(
        codigo, versao, "remover_comodo",
        lambda p: edicao.remover_comodo(p, pavimento, id_),
        remover_comodo=id_,
    )  # fmt: skip


@planta.post("/instalacoes")
def adicionar_instalacao(
    svc: Svc, codigo: str, pavimento: str, versao: Versao, pedido: NovaInstalacao
) -> ResultadoEdicao:
    """Tomada, interruptor, luz, água, esgoto, ralo, gás ou trecho de tubulação."""
    return svc.editar(
        codigo, versao, "adicionar_instalacao",
        lambda p: edicao.adicionar_instalacao(p, pavimento, pedido.instalacao, pedido.distancia),
    )  # fmt: skip


@planta.patch("/instalacoes/{id_}")
def alterar_instalacao(
    svc: Svc, codigo: str, pavimento: str, id_: str, versao: Versao, pedido: AlterarInstalacao
) -> ResultadoEdicao:
    return svc.editar(
        codigo, versao, "alterar_instalacao",
        lambda p: edicao.alterar_instalacao(p, pavimento, id_, pedido.campos, pedido.distancia),
    )  # fmt: skip


@planta.delete("/instalacoes/{id_}")
def remover_instalacao(
    svc: Svc, codigo: str, pavimento: str, id_: str, versao: Versao
) -> ResultadoEdicao:
    return svc.editar(
        codigo, versao, "remover_instalacao",
        lambda p: edicao.remover_instalacao(p, pavimento, id_),
    )  # fmt: skip
