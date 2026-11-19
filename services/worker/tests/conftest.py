"""Worker contra um Postgres temporário (testcontainers); sem Docker, pulado."""

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text

from interiores_banco import arquivos
from interiores_banco.conexao import sessao
from interiores_banco.migrar import atualizar

CASA = Path(__file__).resolve().parents[3] / "packages" / "core" / "tests" / "dados" / "casa"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ.get("INTERIORES_BANCO_TESTE_URL")
    if url:
        eng = create_engine(url)
        yield eng
        eng.dispose()
        return
    if shutil.which("docker") is None:
        pytest.skip("sem Docker: testes do worker pulados")
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:16.11", driver="psycopg") as pg:
        eng = create_engine(pg.get_connection_url())
        yield eng
        eng.dispose()


@pytest.fixture
def banco(engine: Engine, tmp_path: Path) -> Engine:
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    atualizar(engine)
    pasta = tmp_path / "projetos" / "casa"
    shutil.copytree(CASA, pasta)
    with sessao(engine) as s:
        arquivos.importar(s, pasta)
    return engine
