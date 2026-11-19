"""Postgres temporário para os testes (testcontainers: sobe e apaga um container).

Sem Docker os testes do banco são pulados. ``INTERIORES_BANCO_TESTE_URL`` usa um
banco já existente em vez do container (ele é zerado!).
"""

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from interiores_banco.migrar import atualizar

CASA = Path(__file__).resolve().parents[2] / "core" / "tests" / "dados" / "casa"
IMAGEM = "postgres:16.11"  # mesma do docker-compose.yml


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ.get("INTERIORES_BANCO_TESTE_URL")
    if url:
        eng = create_engine(url)
        yield eng
        eng.dispose()
        return
    if shutil.which("docker") is None:
        pytest.skip("sem Docker: testes do banco pulados")
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(IMAGEM, driver="psycopg") as pg:
        eng = create_engine(pg.get_connection_url())
        yield eng
        eng.dispose()


@pytest.fixture
def sessao(engine: Engine) -> Iterator[Session]:
    """Banco limpo a cada teste, montado pelas migrações (não pelo create_all)."""
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    atualizar(engine)
    with Session(engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture
def casa(tmp_path: Path) -> Path:
    """Cópia da casa congelada, que o teste pode editar."""
    destino = tmp_path / "casa"
    shutil.copytree(CASA, destino)
    return destino
