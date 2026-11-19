"""Aplicação FastAPI: monta rotas, CORS e a tradução de erros do domínio para HTTP.

Rodar: ``uv run interiores-api`` (porta ``API_PORT``, padrão 8010). Documentação
interativa em ``/docs``; o OpenAPI (``/openapi.json``) gera os tipos do frontend.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from interiores_api import __version__
from interiores_api.config import Config
from interiores_api.rotas import geral, moveis, planta, projetos, variacoes
from interiores_banco.arquivos import ConflitoDeSincronizacaoError
from interiores_banco.conexao import criar_engine
from interiores_banco.repositorio import ConflitoDeVersaoError, ProjetoInexistenteError
from interiores_core.edicao import EdicaoInvalidaError

log = structlog.get_logger("interiores.api")


def _erro(codigo: int, tipo: str, mensagem: str, **extra: object) -> JSONResponse:
    return JSONResponse({"erro": tipo, "mensagem": mensagem, **extra}, status_code=codigo)


def criar_app(config: Config | None = None, engine: Engine | None = None) -> FastAPI:
    config = config or Config.do_ambiente()

    @asynccontextmanager
    async def ciclo(app: FastAPI) -> AsyncIterator[None]:
        app.state.config = config
        app.state.engine = engine or criar_engine(config.banco_url)
        log.info("api iniciada", porta=config.porta, exportar=config.exportar)
        yield
        if engine is None:
            app.state.engine.dispose()

    app = FastAPI(
        title="Interiores",
        version=__version__,
        description="Projetos de interiores a partir de medidas reais (mm, com origem).",
        lifespan=ciclo,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(projetos)
    app.include_router(planta)
    app.include_router(moveis)
    app.include_router(variacoes)
    app.include_router(geral)

    @app.get("/saude", tags=["infra"])
    def saude() -> dict[str, str]:
        return {"status": "ok", "versao": __version__}

    @app.exception_handler(ProjetoInexistenteError)
    @app.exception_handler(KeyError)
    async def nao_encontrado(_: Request, e: Exception) -> JSONResponse:
        mensagem = e.args[0] if e.args else str(e)
        return _erro(status.HTTP_404_NOT_FOUND, "nao_encontrado", str(mensagem))

    @app.exception_handler(ConflitoDeVersaoError)
    async def conflito_versao(_: Request, e: ConflitoDeVersaoError) -> JSONResponse:
        return _erro(status.HTTP_409_CONFLICT, "versao", str(e), versao_atual=e.atual)

    @app.exception_handler(ConflitoDeSincronizacaoError)
    async def conflito_arquivos(_: Request, e: ConflitoDeSincronizacaoError) -> JSONResponse:
        return _erro(status.HTTP_409_CONFLICT, "arquivos", str(e))

    @app.exception_handler(EdicaoInvalidaError)
    @app.exception_handler(ValueError)
    async def invalida(_: Request, e: Exception) -> JSONResponse:
        return _erro(status.HTTP_422_UNPROCESSABLE_CONTENT, "edicao_invalida", str(e))

    return app


def rodar() -> None:
    """``uv run interiores-api``: sobe o servidor (uvicorn) na porta configurada."""
    import uvicorn

    config = Config.do_ambiente()
    uvicorn.run(criar_app(config), host=config.host, port=config.porta)


def openapi(saida: str = "frontend/src/api/openapi.json") -> None:
    """Grava o OpenAPI sem subir servidor nem banco (os tipos do frontend saem dele)."""
    import json
    from pathlib import Path

    esquema = criar_app(Config(), engine=object()).openapi()  # type: ignore[arg-type]
    Path(saida).write_text(
        json.dumps(esquema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
