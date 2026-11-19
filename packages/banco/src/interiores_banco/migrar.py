"""Aplicar e criar migrações sem precisar de ``alembic.ini`` na pasta atual."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

PASTA = Path(__file__).parent / "migracoes"


def configuracao(url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(PASTA))
    cfg.set_main_option("path_separator", "os")
    if url:
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def atualizar(engine: Engine, revisao: str = "head") -> None:
    """Leva o banco até ``revisao`` (padrão: a mais nova)."""
    cfg = configuracao()
    with engine.begin() as conexao:
        cfg.attributes["connection"] = conexao
        command.upgrade(cfg, revisao)


def criar_revisao(url: str, mensagem: str) -> None:
    """Gera uma migração comparando as tabelas com o banco em ``url`` (dev)."""
    command.revision(configuracao(url), message=mensagem, autogenerate=True)
