"""Pedidos de render: estimativa pelo histórico e ciclo do pedido."""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from interiores_banco import renders, repositorio
from interiores_banco.mapear import Conteudo
from interiores_core.carregar import carregar

FINAL = (1600, 1000, 96)
PADRAO = ["perspectiva", "superior"]


def _casa(sessao: Session, casa: Path) -> None:
    repositorio.gravar(sessao, Conteudo.de_carregado(carregar(casa)), fonte="teste")


def test_estimativa_sem_historico_e_com(sessao: Session, casa: Path) -> None:
    assert renders.estimar_s(sessao, *FINAL, len(PADRAO)) == 119.0  # medido em 2026-11-18
    assert 3 < renders.estimar_s(sessao, 800, 500, 16, 2) < 10
    _casa(sessao, casa)

    def pronto(qualidade: str, tamanho: tuple[int, int, int], duracao: float) -> None:
        r, _ = renders.pedir(sessao, "casa", "quarto", "base", qualidade, tamanho, PADRAO)
        renders.comecar(sessao, r)
        renders.concluir(sessao, r, "/x", ["a.png"], duracao_s=duracao, em_cache=False)

    # caso real de 2026-11-18: rascunho de 8,1 s não pode fazer o final virar "10 s"
    pronto("rascunho", (800, 500, 16), 8.1)
    assert renders.estimar_s(sessao, 800, 500, 16, 2) == 8.1  # mesmo tamanho: o medido
    assert renders.estimar_s(sessao, *FINAL, len(PADRAO)) > 60  # outro tamanho: escala, sem zerar
    pronto("final", FINAL, 127.0)
    assert renders.estimar_s(sessao, *FINAL, len(PADRAO)) == 127.0


def test_pedido_igual_nao_duplica(sessao: Session, casa: Path) -> None:
    _casa(sessao, casa)
    r1, novo1 = renders.pedir(sessao, "casa", "quarto", "base", "rascunho", (800, 500, 16), PADRAO)
    r2, novo2 = renders.pedir(sessao, "casa", "quarto", "base", "rascunho", (800, 500, 16), PADRAO)
    assert novo1 and not novo2 and r1.id == r2.id
    r3, novo3 = renders.pedir(sessao, "casa", "quarto", "base", "final", FINAL, PADRAO)
    assert novo3 and r3.id != r1.id
    assert r1.status == "na_fila" and r1.estimativa_s and r1.versao_projeto == 1
    renders.falhar(sessao, r1, "deu ruim")
    r4, novo4 = renders.pedir(sessao, "casa", "quarto", "base", "rascunho", (800, 500, 16), PADRAO)
    assert novo4 and r4.id != r1.id  # o que falhou não bloqueia um novo
    assert renders.listar(sessao, "casa", "quarto")[0].id == r4.id
    renders.andar(sessao, r4, 0.4567, 1, 12.0)
    assert (r4.progresso, r4.imagem_atual, r4.restante_s) == (0.457, 1, 12.0)
    with pytest.raises(KeyError):
        renders.obter(sessao, 999)
    with pytest.raises(repositorio.ProjetoInexistenteError):
        renders.pedir(sessao, "nao-existe", "quarto", "base", "final", FINAL, PADRAO)


def test_vistas_diferentes_sao_pedidos_diferentes(sessao: Session, casa: Path) -> None:
    _casa(sessao, casa)
    a, _ = renders.pedir(sessao, "casa", "quarto", "base", "rascunho", (800, 500, 16), PADRAO)
    b, novo = renders.pedir(sessao, "casa", "quarto", "base", "rascunho", (800, 500, 16), ["cama"])
    assert novo and a.id != b.id and (a.imagens, b.imagens) == (2, 1)
    assert b.estimativa_s is not None and a.estimativa_s is not None
    assert b.estimativa_s < a.estimativa_s  # uma imagem só: mais rápido
