"""Comandos `interiores banco atualizar`, `importar` e `exportar`."""

from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from interiores_banco import repositorio
from interiores_cli.main import app


@pytest.fixture
def cli(engine: Engine, sessao: Session, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.setenv("INTERIORES_BANCO_URL", engine.url.render_as_string(hide_password=False))
    return CliRunner()


def test_importar_exportar_pela_cli(cli: CliRunner, casa: Path, sessao: Session) -> None:
    pastas = ["--projetos", str(casa.parent)]
    r = cli.invoke(app, ["banco", "atualizar"])
    assert r.exit_code == 0, r.output
    r = cli.invoke(app, ["importar", "casa", *pastas])
    assert r.exit_code == 0 and "versão 1" in r.output, r.output
    r = cli.invoke(app, ["importar", "casa", *pastas])
    assert "nada mudou" in r.output
    assert repositorio.ler(sessao, "casa")[1] == 1

    r = cli.invoke(app, ["exportar", "casa", *pastas])
    assert r.exit_code == 0 and "versão 1" in r.output, r.output
    r = cli.invoke(app, ["exportar", "nao-existe", *pastas])
    assert r.exit_code == 2 and "não está no banco" in r.output


def test_sem_banco_configurado(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for v in ("INTERIORES_BANCO_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.chdir(tmp_path)  # sem .env
    r = CliRunner().invoke(app, ["banco", "atualizar"])
    assert r.exit_code == 2 and "banco não configurado" in r.output
