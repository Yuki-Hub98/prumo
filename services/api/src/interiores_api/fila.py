"""Fila de jobs vista pela API: só enfileira (quem executa é o worker)."""

from __future__ import annotations

import asyncio
from typing import Protocol

from arq import create_pool
from arq.connections import RedisSettings


class Fila(Protocol):
    def enfileirar(self, render_id: int) -> None: ...


class FilaArq:
    """Enfileira no Redis com arq (o worker consome com ``interiores-worker``)."""

    def __init__(self, redis: RedisSettings) -> None:
        self.redis = redis

    async def _enfileirar(self, render_id: int) -> None:
        pool = await create_pool(self.redis)
        try:
            await pool.enqueue_job("renderizar", render_id, _job_id=f"render-{render_id}")
        finally:
            await pool.aclose()

    def enfileirar(self, render_id: int) -> None:
        # as rotas são síncronas (rodam numa thread sem loop): um loop curto por pedido
        asyncio.run(self._enfileirar(render_id))
