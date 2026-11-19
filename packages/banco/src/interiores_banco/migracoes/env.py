"""Ambiente do Alembic: usa a conexão passada por :func:`interiores_banco.migrar`
ou a URL do ambiente (``INTERIORES_BANCO_URL`` / ``POSTGRES_*``)."""

from alembic import context
from sqlalchemy import Connection

from interiores_banco.conexao import criar_engine
from interiores_banco.tabelas import Base

config = context.config


def _rodar(conexao: Connection) -> None:
    context.configure(
        connection=conexao,
        target_metadata=Base.metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


conexao = config.attributes.get("connection")
if conexao is not None:
    _rodar(conexao)
else:
    engine = criar_engine(config.get_main_option("sqlalchemy.url") or None)
    with engine.connect() as c:
        _rodar(c)
