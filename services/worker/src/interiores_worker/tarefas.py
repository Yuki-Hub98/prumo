"""O trabalho de verdade de cada job (síncrono, testável sem Redis).

``executar_render``: lê o pedido, monta o projeto **na versão pedida** (snapshot do
banco) numa pasta temporária, chama o render com progresso ao vivo e grava o
resultado. O progresso é gravado em transações curtas, no máximo 1 por segundo,
para a tela acompanhar.
"""

from __future__ import annotations

import logging
import tempfile
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from interiores_banco import arquivos, renders, repositorio
from interiores_banco.conexao import sessao as abrir_sessao
from interiores_core.carregar import carregar
from interiores_render import gerar

log = logging.getLogger("interiores.worker")

INTERVALO_S = 1.0

Renderizador = Callable[..., gerar.ResultadoRender]


def executar_render(
    engine: Engine,
    render_id: int,
    saida: Path,
    renderizar: Renderizador = gerar.renderizar,
) -> str:
    """Faz o render ``render_id``. Devolve o status final (``pronto`` | ``erro``)."""
    with abrir_sessao(engine) as s:
        r = renders.obter(s, render_id)
        if r.status not in renders.ATIVOS:
            return r.status  # cancelado ou já feito
        codigo = renders.codigo_do_projeto(s, r)
        conteudo = repositorio.snapshot(s, codigo, r.versao_projeto)
        comodo, variacao = r.comodo, r.variacao
        tamanho = (r.largura, r.altura, r.amostras)
        # o rascunho não pode sobrescrever o render final da mesma variação
        subpasta = None if r.qualidade == "final" else r.qualidade
        vistas = tuple(r.vistas)
        renders.comecar(s, r)

    ultimo = 0.0

    def progresso(p: gerar.Progresso) -> None:
        nonlocal ultimo
        agora = time.monotonic()
        if agora - ultimo < INTERVALO_S:
            return
        ultimo = agora
        with abrir_sessao(engine) as s:
            renders.andar(s, renders.obter(s, render_id), p.fracao, p.imagem, p.restante_s)

    try:
        with tempfile.TemporaryDirectory(prefix="render-") as tmp:
            pasta = Path(tmp) / codigo
            arquivos.escrever(conteudo, pasta)
            largura, altura, amostras = tamanho
            resultado = renderizar(
                carregar(pasta), saida, comodo, variacao,
                largura=largura, altura=altura, amostras=amostras, progresso=progresso,
                subpasta=subpasta,
                vistas=vistas,
            )  # fmt: skip
    except Exception as e:  # o pedido fica com o erro para a tela mostrar
        log.exception("render %s falhou", render_id)
        with abrir_sessao(engine) as s:
            renders.falhar(s, renders.obter(s, render_id), f"{e}\n{traceback.format_exc()}")
        return "erro"
    with abrir_sessao(engine) as s:
        renders.concluir(
            s,
            renders.obter(s, render_id),
            str(resultado.arquivos[0].parent),
            [a.name for a in resultado.arquivos],
            resultado.duracao_s,
            em_cache=not resultado.gerado,
        )
    log.info("render %s pronto (%s s)", render_id, resultado.duracao_s)
    return "pronto"


__all__: list[Any] = ["executar_render"]
