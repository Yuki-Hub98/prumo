"""Worker arq: consome a fila do Redis e executa os jobs.

Rodar: ``uv run interiores-worker`` (``make worker``). Um render por vez (o Cycles
usa todos os núcleos da CPU).
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, ClassVar

from arq import run_worker
from arq.connections import RedisSettings

from interiores_banco.conexao import criar_engine, ler_env
from interiores_worker.tarefas import executar_render

FUNCAO_RENDER = "renderizar"


def redis_do_ambiente() -> RedisSettings:
    env = {**ler_env(), **os.environ}
    return RedisSettings(
        host=env.get("REDIS_HOST", "localhost"), port=int(env.get("REDIS_PORT", "6379"))
    )


def pasta_saida() -> Path:
    env = {**ler_env(), **os.environ}
    return Path(env.get("INTERIORES_SAIDA", "out"))


async def renderizar(ctx: dict[str, Any], render_id: int) -> str:
    """Job da fila: o Blender bloqueia, então roda numa thread."""
    return await asyncio.to_thread(executar_render, ctx["engine"], render_id, ctx["saida"])


async def ao_iniciar(ctx: dict[str, Any]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ctx["engine"] = criar_engine()
    ctx["saida"] = pasta_saida()


async def ao_parar(ctx: dict[str, Any]) -> None:
    ctx["engine"].dispose()


class Configuracao:
    functions: ClassVar[list[Any]] = [renderizar]
    on_startup = ao_iniciar
    on_shutdown = ao_parar
    max_jobs = 1
    job_timeout = 1900
    redis_settings = redis_do_ambiente()


def rodar() -> None:
    run_worker(Configuracao)  # type: ignore[arg-type]
