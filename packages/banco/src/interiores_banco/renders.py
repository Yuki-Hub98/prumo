"""Pedidos de render (fila): criar, acompanhar, concluir e estimar o tempo.

A estimativa usa o histórico desta máquina: cada render pronto dá um "custo por
pixel × amostra × imagem" (descontado um tempo fixo de partida do Blender/Docker);
a mediana dos últimos multiplica o tamanho do pedido novo. Sem histórico, vale o
que foi medido em 2026-11-18 (1600×1000, 96 amostras, 2 imagens ≈ 2 min).
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from interiores_banco import tabelas as t
from interiores_banco.repositorio import ProjetoInexistenteError

PARTIDA_S = 3.0
"""Tempo fixo por render (subir o Blender no Docker, montar a cena, gravar)."""
CUSTO_PADRAO = (119.0 - PARTIDA_S) / (1600 * 1000 * 96 * 2)
"""Segundos por pixel·amostra·imagem medidos aqui sem histórico."""
HISTORICO = 20

ATIVOS = ("na_fila", "rodando")


def _agora() -> datetime:
    return datetime.now(UTC)


def estimar_s(sessao: Session, largura: int, altura: int, amostras: int, imagens: int) -> float:
    """Segundos estimados para um render deste tamanho, pelo histórico.

    1. Renders prontos do **mesmo tamanho**: mediana das durações.
    2. Senão, renders de outros tamanhos: custo por pixel·amostra·imagem (mediana),
       sem deixar zerar (render pequeno é quase todo tempo de partida).
    3. Sem histórico: o medido em 2026-11-18.
    """
    prontos = sessao.scalars(
        select(t.Render)
        .where(t.Render.status == "pronto", t.Render.duracao_s.is_not(None))
        .order_by(t.Render.fim.desc())
        .limit(HISTORICO * 3)
    ).all()
    tamanho = largura * altura * amostras * imagens
    iguais = [
        r.duracao_s
        for r in prontos
        if (r.largura, r.altura, r.amostras, r.imagens) == (largura, altura, amostras, imagens)
    ][:HISTORICO]
    if iguais:
        return round(statistics.median(d for d in iguais if d is not None), 1)
    custos = [
        max(r.duracao_s - PARTIDA_S, 0.0) / (r.largura * r.altura * r.amostras * r.imagens)
        for r in prontos[:HISTORICO]
        if r.duracao_s is not None and r.largura * r.altura * r.amostras * r.imagens > 0
    ]
    custo = max(statistics.median(custos), CUSTO_PADRAO / 5) if custos else CUSTO_PADRAO
    return round(PARTIDA_S + custo * tamanho, 1)


def pedir(
    sessao: Session,
    codigo: str,
    comodo: str,
    variacao: str,
    qualidade: str,
    tamanho: tuple[int, int, int],
    vistas: list[str],
) -> tuple[t.Render, bool]:
    """Cria o pedido (``na_fila``) ou devolve o que já está na fila/rodando igual.

    Cada vista é uma imagem (perspectiva, porta, cama, canto-N, superior).

    Devolve ``(pedido, novo)``: só os novos vão para a fila.
    """
    projeto = sessao.scalars(select(t.Projeto).where(t.Projeto.codigo == codigo)).first()
    if projeto is None:
        raise ProjetoInexistenteError(f"projeto '{codigo}' não está no banco")
    igual = sessao.scalars(
        select(t.Render).where(
            t.Render.projeto_id == projeto.id,
            t.Render.comodo == comodo,
            t.Render.variacao == variacao,
            t.Render.qualidade == qualidade,
            t.Render.versao_projeto == projeto.versao,
            t.Render.status.in_(ATIVOS),
            t.Render.vistas == vistas,
        )
    ).first()
    if igual is not None:
        return igual, False
    largura, altura, amostras = tamanho
    imagens = len(vistas)
    pedido = t.Render(
        projeto_id=projeto.id,
        comodo=comodo,
        variacao=variacao,
        qualidade=qualidade,
        largura=largura,
        altura=altura,
        amostras=amostras,
        imagens=imagens,
        vistas=vistas,
        status="na_fila",
        versao_projeto=projeto.versao,
        estimativa_s=estimar_s(sessao, largura, altura, amostras, imagens),
        progresso=0.0,
        em_cache=False,
    )
    sessao.add(pedido)
    sessao.flush()
    return pedido, True


def obter(sessao: Session, id_: int) -> t.Render:
    r = sessao.get(t.Render, id_)
    if r is None:
        raise KeyError(f"render {id_} não existe")
    return r


def listar(sessao: Session, codigo: str, comodo: str | None = None) -> list[t.Render]:
    consulta = (
        select(t.Render)
        .join(t.Projeto)
        .where(t.Projeto.codigo == codigo)
        .order_by(t.Render.criado_em.desc(), t.Render.id.desc())
        .limit(50)
    )
    if comodo is not None:
        consulta = consulta.where(t.Render.comodo == comodo)
    return list(sessao.scalars(consulta))


def codigo_do_projeto(sessao: Session, render: t.Render) -> str:
    codigo = sessao.scalar(select(t.Projeto.codigo).where(t.Projeto.id == render.projeto_id))
    assert codigo is not None
    return codigo


def comecar(sessao: Session, r: t.Render) -> None:
    r.status, r.inicio, r.progresso = "rodando", _agora(), 0.0
    sessao.flush()


def andar(
    sessao: Session, r: t.Render, progresso: float, imagem: int, restante_s: float | None
) -> None:
    r.progresso, r.imagem_atual, r.restante_s = round(progresso, 3), imagem, restante_s
    sessao.flush()


def concluir(
    sessao: Session,
    r: t.Render,
    pasta: str,
    arquivos: list[str],
    duracao_s: float | None,
    em_cache: bool,
) -> None:
    r.status, r.fim, r.progresso, r.restante_s = "pronto", _agora(), 1.0, 0.0
    r.pasta, r.arquivos, r.duracao_s, r.em_cache = pasta, arquivos, duracao_s, em_cache
    sessao.flush()


def falhar(sessao: Session, r: t.Render, erro: str) -> None:
    r.status, r.fim, r.erro = "erro", _agora(), erro[-4000:]
    sessao.flush()
