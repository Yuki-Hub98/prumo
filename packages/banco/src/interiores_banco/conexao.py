"""Conexão com o PostgreSQL a partir de variáveis de ambiente (CLAUDE.md §10).

``INTERIORES_BANCO_URL`` tem prioridade (ex.: nos testes); senão a URL é montada
com as mesmas variáveis do ``docker-compose.yml`` (``POSTGRES_*``), com host
``localhost`` por padrão (``POSTGRES_HOST`` para mudar, ex.: ``db`` dentro do compose).
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker


def ler_env(caminho: Path = Path(".env")) -> dict[str, str]:
    """Lê um ``.env`` simples (``CHAVE=valor``, ``#`` comenta). Sem dependência nova."""
    if not caminho.is_file():
        return {}
    valores = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if "=" in linha:
            chave, valor = linha.split("=", 1)
            valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def url_do_ambiente(env: Mapping[str, str] | None = None) -> str:
    """URL do banco. Sem ``env``, usa o ambiente do processo e, para o que faltar,
    o ``.env`` da pasta atual (o mesmo que o docker compose lê)."""
    env = {**ler_env(), **os.environ} if env is None else env
    if env.get("INTERIORES_BANCO_URL"):
        return env["INTERIORES_BANCO_URL"]
    faltando = [v for v in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB") if not env.get(v)]
    if faltando:
        raise RuntimeError(
            "banco não configurado: defina INTERIORES_BANCO_URL ou "
            + ", ".join(faltando)
            + " (veja o .env.example)"
        )
    return URL.create(
        "postgresql+psycopg",
        username=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        host=env.get("POSTGRES_HOST", "localhost"),
        port=int(env.get("POSTGRES_PORT", "5432")),
        database=env["POSTGRES_DB"],
    ).render_as_string(hide_password=False)


def criar_engine(url: str | None = None) -> Engine:
    return create_engine(url or url_do_ambiente(), pool_pre_ping=True)


@contextmanager
def sessao(engine: Engine) -> Iterator[Session]:
    """Sessão com commit no fim e rollback se der erro."""
    fabrica = sessionmaker(engine, expire_on_commit=False)
    with fabrica() as s, s.begin():
        yield s
