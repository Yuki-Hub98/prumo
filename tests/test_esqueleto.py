"""Testes de fumaça do esqueleto do monorepo."""

import importlib

import pytest
from typer.testing import CliRunner

from interiores_cli.main import app


@pytest.mark.parametrize(
    "modulo",
    [
        "interiores_core",
        "interiores_core.tipos",
        "interiores_core.regras",
        "interiores_cad",
        "interiores_render",
        "interiores_relatorios",
        "interiores_cli",
    ],
)
def test_pacotes_importam(modulo: str) -> None:
    importlib.import_module(modulo)


def test_cli_versao() -> None:
    resultado = CliRunner().invoke(app, ["versao"])
    assert resultado.exit_code == 0
    assert "interiores 0.1.0" in resultado.output
