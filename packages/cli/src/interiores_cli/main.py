"""Ponto de entrada da CLI `interiores`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from interiores_core import __version__, geometria, schema
from interiores_core.carregar import carregar
from interiores_core.validacao import Severidade, validar

app = typer.Typer(help="Projeto de interiores a partir de medidas reais.", no_args_is_help=True)

PastaProjetos = Annotated[
    Path, typer.Option("--projetos", help="Pasta que contém os projetos.", show_default=True)
]


@app.callback()
def principal() -> None:
    """Projeto de interiores a partir de medidas reais."""


@app.command()
def versao() -> None:
    """Mostra a versão instalada."""
    print(f"interiores {__version__}")


@app.command("schema")
def gerar_schema(
    saida: Annotated[Path, typer.Option(help="Pasta de destino.")] = Path("schema"),
) -> None:
    """Gera o JSON Schema oficial a partir do modelo do core."""
    for caminho in schema.exportar(saida):
        print(f"gravado {caminho}")


@app.command("validar")
def cmd_validar(
    projeto: Annotated[str, typer.Argument(help="Nome da pasta em projetos/.")],
    projetos: PastaProjetos = Path("projetos"),
    estimadas: Annotated[
        bool, typer.Option("--estimadas", help="Lista cada medida estimada.")
    ] = False,
) -> None:
    """Valida o projeto e lista os problemas por severidade."""
    pasta = projetos / projeto
    try:
        carregado = carregar(pasta)
    except FileNotFoundError as e:
        print(f"erro: arquivo não encontrado: {e.filename}")
        raise typer.Exit(2) from e
    except ValidationError as e:
        print(f"erro: formato inválido em {pasta}:\n{e}")
        raise typer.Exit(2) from e

    proj = carregado.projeto
    print(f"projeto {proj.projeto} · {proj.imovel.tipo} · hash {carregado.hash_curto}")
    for pav in proj.pavimentos:
        print(f"\npavimento {pav.id} (pé-direito {pav.pe_direito.valor} mm)")
        for c in pav.comodos:
            area = geometria.area_util_m2(pav, c)
            area_txt = f"{area:.2f} m²" if area is not None else "não fechado"
            n_est = len(carregado.estimadas(c.id))
            print(f"  {c.id:<16} {c.tipo:<12} {area_txt:>10}   estimadas: {n_est}")

    problemas = validar(proj, carregado.dados_comodos)
    print()
    if not problemas:
        print("nenhum problema encontrado")
    for sev in Severidade:
        da_severidade = [p for p in problemas if p.severidade is sev]
        if da_severidade:
            print(f"{sev.upper()} ({len(da_severidade)})")
            for p in da_severidade:
                print(f"  {p}")

    lista = carregado.estimadas()
    if lista:
        print(f"\nPRELIMINAR — NÃO USAR PARA OBRA: {len(lista)} medida(s) estimada(s)")
        if estimadas:
            for caminho, m in lista:
                print(f"  {caminho} = {m.valor} mm" + (f"  ({m.obs})" if m.obs else ""))
        else:
            print("  (use --estimadas para listar)")

    if any(p.severidade is Severidade.ERRO for p in problemas):
        raise typer.Exit(1)
