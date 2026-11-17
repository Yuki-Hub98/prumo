"""Ponto de entrada da CLI `interiores`."""

import typer

from interiores_core import __version__

app = typer.Typer(help="Projeto de interiores a partir de medidas reais.", no_args_is_help=True)


@app.callback()
def principal() -> None:
    """Projeto de interiores a partir de medidas reais."""


@app.command()
def versao() -> None:
    """Mostra a versão instalada."""
    print(f"interiores {__version__}")
