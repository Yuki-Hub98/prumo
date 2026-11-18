"""Ponto de entrada da CLI `interiores`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from interiores_cad.gerar import Resultado, Situacao, gerar_planta
from interiores_core import __version__, geometria, schema
from interiores_core.carregar import ProjetoCarregado, carregar
from interiores_core.validacao import Problema, Severidade, validar

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
    carregado = _carregar(projetos / projeto)
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
    _listar_problemas(problemas)

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


@app.command("cad")
def cmd_cad(
    projeto: Annotated[str, typer.Argument(help="Nome da pasta em projetos/.")],
    pavimento: Annotated[
        str | None, typer.Option("--pavimento", "-a", help="Planta geral deste pavimento.")
    ] = None,
    comodo: Annotated[str | None, typer.Option("--comodo", "-c", help="Planta do cômodo.")] = None,
    projetos: PastaProjetos = Path("projetos"),
    saida: Annotated[Path, typer.Option(help="Pasta das saídas geradas.")] = Path("out"),
    forcar: Annotated[
        bool, typer.Option("--forcar", help="Regera mesmo se a entrada não mudou.")
    ] = False,
) -> None:
    """Gera plantas em DXF e PDF.

    Com --comodo, a planta do cômodo; com --pavimento, a planta geral dele;
    sem nenhum dos dois, a planta geral de cada pavimento e a de cada cômodo.
    """
    carregado = _carregar(projetos / projeto)
    proj = carregado.projeto
    escopos: list[tuple[str, str | None]] = []
    if comodo is not None:
        pav = proj.pavimento_do_comodo(comodo)
        if pav is None or (pavimento is not None and pav.id != pavimento):
            print(
                f"erro: cômodo '{comodo}' não existe" + (f" em '{pavimento}'" if pavimento else "")
            )
            raise typer.Exit(2)
        escopos.append((pav.id, comodo))
    elif pavimento is not None:
        if not any(p.id == pavimento for p in proj.pavimentos):
            print(f"erro: pavimento '{pavimento}' não existe")
            raise typer.Exit(2)
        escopos.append((pavimento, None))
    else:
        for pav in proj.pavimentos:
            escopos += [(pav.id, None), *((pav.id, c.id) for c in pav.comodos)]

    falhou = False
    preliminar = False
    for pav_id, com_id in escopos:
        nome = f"{pav_id}/{com_id or '_geral'}"
        try:
            r = gerar_planta(carregado, saida, pav_id, com_id, forcar=forcar)
        except ValueError as e:
            print(f"  {nome:<24} FALHOU: {e}")
            falhou = True
            continue
        preliminar |= r.preliminar
        _mostrar_resultado(nome, r)

    print()
    _listar_problemas(validar(proj, carregado.dados_comodos))
    if preliminar:
        print("\nPRELIMINAR — NÃO USAR PARA OBRA: há medidas estimadas nos desenhos")
        print("  (veja a lista no carimbo ou em `interiores validar --estimadas`)")
    if falhou:
        raise typer.Exit(1)


def _carregar(pasta: Path) -> ProjetoCarregado:
    try:
        return carregar(pasta)
    except FileNotFoundError as e:
        print(f"erro: arquivo não encontrado: {e.filename}")
        raise typer.Exit(2) from e
    except ValidationError as e:
        print(f"erro: formato inválido em {pasta}:\n{e}")
        raise typer.Exit(2) from e


def _listar_problemas(problemas: list[Problema]) -> None:
    if not problemas:
        print("nenhum problema encontrado")
    for sev in Severidade:
        da_severidade = [p for p in problemas if p.severidade is sev]
        if da_severidade:
            print(f"{sev.upper()} ({len(da_severidade)})")
            for p in da_severidade:
                print(f"  {p}")


def _mostrar_resultado(nome: str, r: Resultado) -> None:
    marca = "gerado    " if r.situacao is Situacao.GERADO else "inalterado"
    aviso = "  PRELIMINAR" if r.preliminar else ""
    print(f"  {nome:<24} {marca}  1:{r.escala} {r.folha}{aviso}")
    if r.situacao is Situacao.GERADO:
        for arq in r.arquivos[:2]:
            print(f"      {arq}")
