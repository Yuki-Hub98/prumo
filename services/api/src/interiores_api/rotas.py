"""Rotas HTTP. Cada rota só traduz o pedido para o serviço; nada de regra aqui.

Toda edição exige ``?versao=`` (a versão que a tela estava vendo): se alguém
gravou antes, a resposta é 409 e a tela recarrega em vez de atropelar.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse, Response

from interiores_api.esquemas import (
    AdicionarPavimento,
    AlterarComodo,
    AlterarInstalacao,
    AlterarParede,
    Apagado,
    Campos,
    Cena3D,
    DefinirConstrucao,
    DividirParede,
    InfoRender,
    ItemHistorico,
    MedidaEstimada,
    ModeloProprioResumo,
    MoverMovel,
    MoverVertice,
    NovaAbertura,
    NovaInstalacao,
    NovaVariacao,
    NovoComodo,
    NovoModeloProprio,
    NovoMovel,
    NovoProjeto,
    PedidoRender,
    PedidoRenderPavimento,
    Preferencias,
    ProjetoCompleto,
    Renomear,
    ResultadoEdicao,
    ResumoProjeto,
    Tinta,
    Versoes,
    Vista,
)
from interiores_api.servicos import Servico
from interiores_banco.conexao import sessao as abrir_sessao
from interiores_core import catalogo, catalogo_aberturas, edicao
from interiores_core import edicao_moveis as em
from interiores_core.modelo import Parede, Variacao
from interiores_core.tela import PavimentoTela, PlanejadoTela
from interiores_core.validacao import Problema


def servico(request: Request) -> Iterator[Servico]:
    """Uma transação por pedido: commit se deu certo, rollback se deu erro."""
    with abrir_sessao(request.app.state.engine) as s:
        yield Servico(s, request.app.state.config, request.app.state.fila)


Svc = Annotated[Servico, Depends(servico)]
Versao = Annotated[int, Query(ge=0, description="Versão do projeto que a tela estava vendo.")]

projetos = APIRouter(prefix="/projetos", tags=["projetos"])
planta = APIRouter(prefix="/projetos/{codigo}/pavimentos/{pavimento}", tags=["planta"])
moveis = APIRouter(prefix="/projetos/{codigo}/comodos/{comodo}/moveis", tags=["móveis"])
variacoes = APIRouter(prefix="/projetos/{codigo}/comodos/{comodo}/variacoes", tags=["cores"])
geral = APIRouter(tags=["catálogo"])


@geral.get("/preferencias", tags=["preferências"])
def ver_preferencias(svc: Svc) -> Preferencias:
    return svc.preferencias()


@geral.patch("/preferencias", tags=["preferências"])
def salvar_preferencias(svc: Svc, novas: Preferencias) -> Preferencias:
    """Ex.: ``{"unidade": "m"}``. Só o que vier no pedido muda."""
    return svc.salvar_preferencias(novas)


@geral.get("/catalogo")
def ver_catalogo() -> dict[str, object]:
    """Tipos de móvel, modelos com medidas padrão, lados de uso e símbolo na planta."""
    return catalogo.exportar()


@geral.get("/modelos-proprios")
def listar_modelos_proprios(svc: Svc) -> list[ModeloProprioResumo]:
    """Móveis guardados como modelo próprio (valem para todos os projetos)."""
    return svc.modelos_proprios()


@geral.post("/modelos-proprios", status_code=201)
def criar_modelo_proprio(svc: Svc, pedido: NovoModeloProprio) -> ModeloProprioResumo:
    """Guarda um móvel de um projeto (como está agora) como modelo próprio."""
    return svc.criar_modelo_proprio(pedido)


@geral.delete("/modelos-proprios/{codigo_modelo}", status_code=204)
def apagar_modelo_proprio(svc: Svc, codigo_modelo: str) -> None:
    svc.apagar_modelo_proprio(codigo_modelo)


@geral.get("/catalogo/aberturas")
def ver_catalogo_aberturas() -> catalogo_aberturas.CatalogoAberturas:
    """Portas e janelas prontas: tipos e tamanhos comerciais (para escolher ao criar)."""
    return catalogo_aberturas.exportar()


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


@projetos.get("/{codigo}/versoes")
def versoes(svc: Svc, codigo: str) -> Versoes:
    """Versões (da mais nova) e para onde o desfazer/refazer levariam agora."""
    return svc.versoes(codigo)


@projetos.post("/{codigo}/desfazer")
def desfazer(svc: Svc, codigo: str, versao: Versao) -> ResultadoEdicao:
    """Volta ao estado de antes da última edição (grava como versão nova)."""
    return svc.voltar(codigo, versao, "desfazer")


@projetos.post("/{codigo}/refazer")
def refazer(svc: Svc, codigo: str, versao: Versao) -> ResultadoEdicao:
    """Refaz o último desfazer (só logo depois de desfazer)."""
    return svc.voltar(codigo, versao, "refazer")


@projetos.post("/{codigo}/rascunho/salvar")
def salvar_rascunho(svc: Svc, codigo: str, versao: Versao) -> ResultadoEdicao:
    """Salva o rascunho: cada mudança vira uma versão e ``projetos/<p>`` é reexportado."""
    return svc.salvar_rascunho(codigo, versao)


@projetos.post("/{codigo}/rascunho/descartar")
def descartar_rascunho(svc: Svc, codigo: str, versao: Versao) -> ResultadoEdicao:
    """Joga fora as mudanças não salvas: volta para a versão salva."""
    return svc.descartar_rascunho(codigo, versao)


@projetos.post("/{codigo}/versoes/{para}/restaurar")
def restaurar(svc: Svc, codigo: str, para: int, versao: Versao) -> ResultadoEdicao:
    """Volta o projeto para o conteúdo da versão ``para`` (grava como versão nova)."""
    return svc.voltar(codigo, versao, "reverter", para)


@projetos.get("/{codigo}/versoes/{versao}")
def versao(svc: Svc, codigo: str, versao: int) -> ProjetoCompleto:
    return svc.versao(codigo, versao)


@projetos.patch("/{codigo}/imovel")
def alterar_imovel(svc: Svc, codigo: str, versao: Versao, campos: Campos) -> ResultadoEdicao:
    """Tipo do imóvel (casa | apartamento) e apelido (``endereco_apelido``)."""
    return svc.editar(codigo, versao, "alterar_imovel", lambda p: edicao.alterar_imovel(p, campos))


@projetos.post("/{codigo}/renomear")
def renomear(svc: Svc, codigo: str, versao: Versao, pedido: Renomear) -> ResultadoEdicao:
    """Troca o código do projeto (e o nome da pasta em projetos/)."""
    return svc.renomear(codigo, versao, pedido.codigo)


@projetos.delete("/{codigo}")
def apagar(
    svc: Svc,
    codigo: str,
    versao: Versao,
    confirmar: Annotated[str, Query(description="Repita o código do projeto para confirmar.")],
) -> Apagado:
    """Apaga do banco (com histórico). A pasta vai para projetos/_apagados/."""
    return Apagado(codigo=codigo, pasta_movida_para=svc.apagar(codigo, versao, confirmar))


@projetos.post("/{codigo}/pavimentos")
def adicionar_pavimento(
    svc: Svc, codigo: str, versao: Versao, pedido: AdicionarPavimento
) -> ResultadoEdicao:
    """Novo pavimento (ex.: superior), vazio."""
    dados = pedido.pavimento.model_dump(mode="json", exclude_none=True)
    return svc.editar(
        codigo, versao, "adicionar_pavimento",
        lambda p: edicao.adicionar_pavimento(p, dados, pedido.depois_de),
    )  # fmt: skip


@projetos.delete("/{codigo}/pavimentos/{pavimento}")
def remover_pavimento(
    svc: Svc, codigo: str, pavimento: str, versao: Versao, cascata: bool = False
) -> ResultadoEdicao:
    """Com paredes ou cômodos, só com ``cascata=true`` (vai tudo, inclusive os móveis)."""
    comodos = edicao.comodos_do_pavimento(svc.ler(codigo).projeto, pavimento)
    return svc.editar(
        codigo, versao, "remover_pavimento",
        lambda p: edicao.remover_pavimento(p, pavimento, cascata),
        remover_comodos=comodos,
    )  # fmt: skip


# ---------------------------------------------------------------- planta


@planta.get("/geometria")
def geometria(svc: Svc, codigo: str, pavimento: str) -> PavimentoTela:
    """Tudo do pavimento em polígonos prontos para desenhar (mm, y para cima)."""
    return svc.geometria(codigo, pavimento)


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
        remover_comodos=[id_],
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


# ---------------------------------------------------------------- móveis


@moveis.post("")
def adicionar_movel(
    svc: Svc, codigo: str, comodo: str, versao: Versao, pedido: NovoMovel
) -> ResultadoEdicao:
    """Do catálogo (ou de um modelo próprio); pelo centro ou preso numa parede."""
    base = svc.modelo_proprio(pedido.modelo_proprio).dados if pedido.modelo_proprio else None
    return svc.editar_moveis(
        codigo, versao, comodo, "adicionar_movel",
        lambda p, d, r: em.adicionar_movel(
            p, comodo, d, pedido.tipo, modelo=pedido.modelo, id_=pedido.id, nome=pedido.nome,
            centro=pedido.centro, rotacao=pedido.rotacao, parede=pedido.parede,
            distancia=pedido.distancia, medidas=pedido.medidas, regras=r, base=base,
        ),
    )  # fmt: skip


@moveis.post("/{id_}/mover")
def mover_movel(
    svc: Svc, codigo: str, comodo: str, id_: str, versao: Versao, pedido: MoverMovel
) -> ResultadoEdicao:
    return svc.editar_moveis(
        codigo, versao, comodo, "mover_movel",
        lambda p, d, r: em.mover_movel(
            p, comodo, d, id_, centro=pedido.centro, rotacao=pedido.rotacao,
            parede=pedido.parede, distancia=pedido.distancia, regras=r,
        ),
    )  # fmt: skip


@moveis.patch("/{id_}")
def alterar_movel(
    svc: Svc, codigo: str, comodo: str, id_: str, versao: Versao, campos: Campos
) -> ResultadoEdicao:
    """Medidas (com origem), nome, modelo, portas, polegadas."""
    return svc.editar_moveis(
        codigo, versao, comodo, "alterar_movel",
        lambda p, d, r: em.alterar_movel(p, comodo, d, id_, campos, r),
    )  # fmt: skip


@moveis.put("/{id_}/construcao")
def definir_construcao(
    svc: Svc, codigo: str, comodo: str, id_: str, versao: Versao, pedido: DefinirConstrucao
) -> ResultadoEdicao:
    """Monta o móvel por dentro (vãos, gavetas, nichos, cabideiros, portas) ou tira (null)."""
    construcao = (
        pedido.construcao.model_dump(mode="json", exclude_none=True) if pedido.construcao else None
    )
    return svc.editar_moveis(
        codigo, versao, comodo, "definir_construcao",
        lambda p, d, r: em.definir_construcao(p, comodo, d, id_, construcao, r),
    )  # fmt: skip


@moveis.post("/{id_}/construcao/sugerir")
def sugerir_construcao(
    svc: Svc, codigo: str, comodo: str, id_: str, versao: Versao
) -> ResultadoEdicao:
    """Monta o móvel com o interior padrão do tipo, para ajustar a partir daí."""
    return svc.editar_moveis(
        codigo, versao, comodo, "sugerir_construcao",
        lambda p, d, r: em.sugerir_construcao(p, comodo, d, id_, r),
    )  # fmt: skip


@moveis.get("/{id_}/planejado")
def ver_planejado(svc: Svc, codigo: str, comodo: str, id_: str) -> PlanejadoTela:
    """Vista de frente calculada do móvel planejado (para o editor desenhar)."""
    return svc.planejado(codigo, comodo, id_)


@moveis.delete("/{id_}")
def remover_movel(svc: Svc, codigo: str, comodo: str, id_: str, versao: Versao) -> ResultadoEdicao:
    return svc.editar_moveis(
        codigo, versao, comodo, "remover_movel",
        lambda p, d, r: em.remover_movel(p, comodo, d, id_, r),
    )  # fmt: skip


# ---------------------------------------------------------------- cores (variações)


@variacoes.get("")
def listar_variacoes(svc: Svc, codigo: str, comodo: str) -> dict[str, Variacao]:
    """Variações de cor do cômodo, por nome (``base`` = cores padrão, não listada)."""
    return svc.variacoes(codigo, comodo)


@variacoes.put("/{nome}")
def salvar_variacao(
    svc: Svc, codigo: str, comodo: str, nome: str, versao: Versao, pedido: NovaVariacao
) -> ResultadoEdicao:
    """Cria ou substitui a variação inteira (a tela manda a paleta completa)."""
    dados = pedido.model_dump(mode="json", exclude_none=True)
    return svc.salvar_variacao(codigo, versao, comodo, nome, dados)


@variacoes.delete("/{nome}")
def remover_variacao(
    svc: Svc, codigo: str, comodo: str, nome: str, versao: Versao
) -> ResultadoEdicao:
    return svc.salvar_variacao(codigo, versao, comodo, nome, None)


# ---------------------------------------------------------------- render (fila)

render = APIRouter(tags=["render"])


@render.post("/projetos/{codigo}/comodos/{comodo}/renders", status_code=status.HTTP_202_ACCEPTED)
def pedir_render(svc: Svc, codigo: str, comodo: str, pedido: PedidoRender) -> InfoRender:
    """Põe o render na fila; acompanhe por ``GET /renders/{id}`` (progresso e tempo)."""
    return svc.pedir_render(codigo, comodo, pedido)


@render.post(
    "/projetos/{codigo}/pavimentos/{pavimento}/renders", status_code=status.HTTP_202_ACCEPTED
)
def pedir_render_pavimento(
    svc: Svc, codigo: str, pavimento: str, pedido: PedidoRenderPavimento
) -> InfoRender:
    """Modelo 3D do pavimento inteiro (todos os cômodos, teto cortado) na fila."""
    return svc.pedir_render_pavimento(codigo, pavimento, pedido)


@render.get("/projetos/{codigo}/renders")
def listar_renders(
    svc: Svc, codigo: str, comodo: str | None = None, pavimento: str | None = None
) -> list[InfoRender]:
    """Pedidos recentes; ``comodo`` filtra um cômodo, ``pavimento`` os do pavimento inteiro."""
    return svc.renders(codigo, comodo, pavimento)


@render.get("/renders/estimativas")
def estimativas(
    svc: Svc, imagens: Annotated[int, Query(ge=1, le=20, description="Quantas vistas.")] = 2
) -> dict[str, float]:
    """Segundos estimados por qualidade (rascunho, final), pelo histórico."""
    return svc.estimativas(imagens)


@render.get("/projetos/{codigo}/comodos/{comodo}/cena")
def cena_comodo(svc: Svc, codigo: str, comodo: str) -> Cena3D:
    """Cena 3D ao vivo do cômodo (geometria e materiais calculados pelo core)."""
    return svc.cena(codigo, comodo=comodo)


@render.get("/projetos/{codigo}/pavimentos/{pavimento}/cena")
def cena_pavimento(svc: Svc, codigo: str, pavimento: str) -> Cena3D:
    """Cena 3D ao vivo do pavimento inteiro (todos os cômodos, cada parede uma vez)."""
    return svc.cena(codigo, pavimento=pavimento)


def _variacoes(variacao: list[str]) -> dict[str, str]:
    """``["quarto:escura"]`` → ``{"quarto": "escura"}``."""
    saida = {}
    for par in variacao:
        comodo, sep, nome = par.partition(":")
        if not sep or not comodo or not nome:
            raise ValueError(f"variação '{par}': use cômodo:variação")
        saida[comodo] = nome
    return saida


Escolhas = Annotated[
    list[str],
    Query(description="Cores de cada cômodo: cômodo:variação (repita; sem = cor padrão)."),
]


@render.get("/projetos/{codigo}/pavimentos/{pavimento}/tinta")
def tinta(svc: Svc, codigo: str, pavimento: str, variacao: Escolhas = []) -> Tinta:  # noqa: B006
    """Tinta do pavimento: látex de paredes e teto, esmalte de portas e rodapé, por cor."""
    return svc.tinta(codigo, pavimento, _variacoes(variacao))


@render.get("/projetos/{codigo}/pavimentos/{pavimento}/tinta.xlsx")
def tinta_xlsx(svc: Svc, codigo: str, pavimento: str, variacao: Escolhas = []) -> Response:  # noqa: B006
    """A mesma planilha do ``make tinta``, para baixar."""
    dados = svc.tinta_xlsx(codigo, pavimento, _variacoes(variacao))
    return Response(
        dados,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="tinta-{codigo}-{pavimento}.xlsx"'},
    )


@render.get("/projetos/{codigo}/comodos/{comodo}/vistas")
def vistas(svc: Svc, codigo: str, comodo: str) -> list[Vista]:
    """Câmeras disponíveis no cômodo (perspectiva, porta, cama, canto-N, superior)."""
    return svc.vistas(codigo, comodo)


@render.get("/renders/{id_}")
def ver_render(svc: Svc, id_: int) -> InfoRender:
    return svc.render(id_)


@render.get("/renders/{id_}/imagens/{nome}", response_class=FileResponse)
def imagem_render(svc: Svc, id_: int, nome: str) -> FileResponse:
    return FileResponse(svc.imagem_render(id_, nome), media_type="image/png")


@render.get("/renders/{id_}/modelo", response_class=FileResponse)
def modelo_render(svc: Svc, id_: int) -> FileResponse:
    """Modelo 3D (.glb) do cômodo ou do pavimento do render pronto, para o visor da tela."""
    return FileResponse(svc.modelo_render(id_), media_type="model/gltf-binary")
