"""Ponto de entrada da CLI `interiores`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from interiores_cad.gerar import Resultado, Situacao, gerar_movel, gerar_planta, gerar_vistas
from interiores_core import __version__, catalogo, editar, geometria, planejado, schema
from interiores_core.carregar import ProjetoCarregado, carregar
from interiores_core.medidas import medidas_em
from interiores_core.regras import checar
from interiores_core.validacao import ORDEM_SEVERIDADE, Problema, Severidade, validar
from interiores_relatorios.lista_corte import gerar_lista

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
    """Valida o projeto, roda as checagens de uso e lista os problemas por severidade."""
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

    problemas = _problemas(carregado)
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
    """Gera plantas, cortes e elevações em DXF e PDF.

    Com --comodo, a planta, os cortes AA/BB e a elevação de cada parede do cômodo;
    com --pavimento, a planta geral dele;
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
        if com_id is not None:
            situacao, arquivos = gerar_vistas(carregado, saida, pav_id, com_id, forcar=forcar)
            pdfs = [a.stem for a in arquivos if a.suffix == ".pdf"]
            print(f"      cortes e elevações ({situacao}): {', '.join(pdfs)}")

    print()
    _listar_problemas(_problemas(carregado))
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


def _problemas(carregado: ProjetoCarregado) -> list[Problema]:
    """Validação estrutural + checagens de uso, por severidade."""
    proj = carregado.projeto
    todos = validar(proj, carregado.dados_comodos) + checar(
        proj, carregado.dados_comodos, carregado.regras
    )
    return sorted(todos, key=lambda p: ORDEM_SEVERIDADE[p.severidade])


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


# ---------------------------------------------------------------- catálogo e móveis

movel_app = typer.Typer(help="Adiciona, move, remove e lista móveis de um cômodo.")
app.add_typer(movel_app, name="movel")


def _ponto(texto: str) -> tuple[int, int]:
    try:
        x, y = (int(v) for v in texto.replace(";", ",").split(","))
    except ValueError as e:
        raise typer.BadParameter(f"use x,y em mm (ex.: 1200,800), não '{texto}'") from e
    return x, y


@app.command("catalogo")
def cmd_catalogo(
    tipo: Annotated[str | None, typer.Argument(help="Mostra os modelos deste tipo.")] = None,
) -> None:
    """Lista os tipos de móvel do catálogo, ou os modelos de um tipo."""
    if tipo is None:
        for cat in catalogo.Categoria:
            itens = [i for i in catalogo.CATALOGO.values() if i.categoria is cat]
            print(f"\n{cat.value}")
            for i in itens:
                print(f"  {i.tipo:<14} {i.nome:<16} {len(i.modelos)} modelo(s)")
        print("\nuse `interiores catalogo <tipo>` para ver os modelos")
        return
    item = catalogo.item_do_tipo(tipo)
    if item is None:
        print(f"erro: tipo '{tipo}' não está no catálogo")
        raise typer.Exit(2)
    print(f"{item.nome} ({item.tipo}) · lados de uso: {', '.join(item.lados_uso) or 'nenhum'}")
    for m in item.modelos:
        padrao = "  (padrão)" if m.id == item.modelo_padrao else ""
        extra = "".join(
            [
                f" · {m.portas}" if m.portas else "",
                f" · elev. {m.elevacao}" if m.elevacao else "",
            ]
        )
        print(
            f"  {m.id:<12} {m.nome:<22} {m.largura} × {m.profundidade} × {m.altura}{extra}{padrao}"
        )


@movel_app.command("listar")
def cmd_movel_listar(
    projeto: Annotated[str, typer.Argument(help="Nome da pasta em projetos/.")],
    comodo: Annotated[str, typer.Argument(help="Id do cômodo.")],
    projetos: PastaProjetos = Path("projetos"),
) -> None:
    """Lista os móveis do cômodo com posição e medidas."""
    carregado = _carregar(projetos / projeto)
    dados = carregado.dados_comodos.get(comodo)
    if dados is None or not dados.moveis:
        print("nenhum móvel")
        return
    for m in dados.moveis:
        est = " (estimadas)" if any(md.estimada for _, md in medidas_em(m)) else ""
        print(
            f"  {m.id:<16} {m.tipo:<13} {m.largura.valor} × {m.profundidade.valor} × "
            f"{m.altura.valor}  em ({m.centro[0]}, {m.centro[1]}) rot {m.rotacao}{est}"
        )


@movel_app.command("adicionar")
def cmd_movel_adicionar(
    projeto: Annotated[str, typer.Argument(help="Nome da pasta em projetos/.")],
    comodo: Annotated[str, typer.Argument(help="Id do cômodo.")],
    tipo: Annotated[str, typer.Argument(help="Tipo do catálogo (veja `interiores catalogo`).")],
    em: Annotated[str | None, typer.Option("--em", help="Centro do móvel: x,y em mm.")] = None,
    parede: Annotated[
        str | None,
        typer.Option(help="Prende o móvel nesta parede, virado para o cômodo (no lugar de --em)."),
    ] = None,
    a: Annotated[
        int, typer.Option("--a", help="Com --parede: mm do início da parede até a borda do móvel.")
    ] = 0,
    modelo: Annotated[str | None, typer.Option(help="Modelo do catálogo.")] = None,
    id_: Annotated[str | None, typer.Option("--id", help="Id do móvel.")] = None,
    rotacao: Annotated[int, typer.Option(help="0, 90, 180 ou 270 (frente para +y em 0).")] = 0,
    nome: Annotated[str | None, typer.Option(help="Nome no desenho.")] = None,
    largura: Annotated[int | None, typer.Option(help="mm (substitui a do modelo).")] = None,
    profundidade: Annotated[int | None, typer.Option(help="mm.")] = None,
    altura: Annotated[int | None, typer.Option(help="mm.")] = None,
    elevacao: Annotated[int | None, typer.Option(help="mm do piso até a base.")] = None,
    origem: Annotated[
        str, typer.Option(help="Origem das medidas informadas: estimada, trena ou projeto.")
    ] = "estimada",
    projetos: PastaProjetos = Path("projetos"),
) -> None:
    """Adiciona um móvel do catálogo ao cômodo e roda as checagens dele.

    Posição: --em x,y (centro, com --rotacao) ou --parede <id> --a <mm>, que encosta
    as costas do móvel na parede, virado para o cômodo.
    """
    pasta = projetos / projeto
    medidas = {
        k: v
        for k, v in {
            "largura": largura,
            "profundidade": profundidade,
            "altura": altura,
            "elevacao": elevacao,
        }.items()
        if v is not None
    }
    if (em is None) == (parede is None):
        print("erro: informe a posição com --em x,y ou com --parede <id> [--a mm]")
        raise typer.Exit(2)
    try:
        novo_id = id_ or editar.id_livre(pasta, comodo, tipo)
        movel = catalogo.novo_movel(
            tipo, novo_id, _ponto(em) if em else (0, 0), modelo, rotacao, nome, medidas, origem
        )
        if parede is not None:
            editar.encostar(pasta, comodo, movel, parede, a)
        editar.adicionar_movel(pasta, comodo, movel)
    except (KeyError, ValueError) as e:
        print(f"erro: {e.args[0] if isinstance(e, KeyError) else e}")
        raise typer.Exit(2) from e
    cx, cy = movel["centro"]
    print(
        f"adicionado '{novo_id}' ({tipo} {movel['modelo']}) em {comodo}: "
        f"centro ({cx}, {cy}), rotação {movel['rotacao']}"
    )
    _checagens_do_comodo(pasta, comodo)


@movel_app.command("mover")
def cmd_movel_mover(
    projeto: Annotated[str, typer.Argument(help="Nome da pasta em projetos/.")],
    comodo: Annotated[str, typer.Argument(help="Id do cômodo.")],
    id_: Annotated[str, typer.Argument(metavar="ID", help="Id do móvel.")],
    em: Annotated[str | None, typer.Option("--em", help="Novo centro: x,y em mm.")] = None,
    rotacao: Annotated[int | None, typer.Option(help="Nova rotação.")] = None,
    parede: Annotated[
        str | None, typer.Option(help="Prende nesta parede, virado para o cômodo.")
    ] = None,
    a: Annotated[
        int, typer.Option("--a", help="Com --parede: mm do início da parede até a borda do móvel.")
    ] = 0,
    projetos: PastaProjetos = Path("projetos"),
) -> None:
    """Muda a posição e/ou a rotação de um móvel (ou o prende numa parede) e roda as checagens."""
    pasta = projetos / projeto
    if parede is not None and (em is not None or rotacao is not None):
        print("erro: com --parede a posição e a rotação são calculadas; não use --em/--rotacao")
        raise typer.Exit(2)
    try:
        dados = editar.mover_movel(
            pasta, comodo, id_, _ponto(em) if em else None, rotacao, parede, a
        )
    except (KeyError, ValueError) as e:
        print(f"erro: {e.args[0] if isinstance(e, KeyError) else e}")
        raise typer.Exit(2) from e
    m = next(x for x in dados.moveis if x.id == id_)
    print(f"movido '{id_}': centro ({m.centro[0]}, {m.centro[1]}), rotação {m.rotacao}")
    _checagens_do_comodo(pasta, comodo)


@movel_app.command("remover")
def cmd_movel_remover(
    projeto: Annotated[str, typer.Argument(help="Nome da pasta em projetos/.")],
    comodo: Annotated[str, typer.Argument(help="Id do cômodo.")],
    id_: Annotated[str, typer.Argument(metavar="ID", help="Id do móvel.")],
    projetos: PastaProjetos = Path("projetos"),
) -> None:
    """Remove um móvel do cômodo."""
    try:
        editar.remover_movel(projetos / projeto, comodo, id_)
    except KeyError as e:
        print(f"erro: {e.args[0]}")
        raise typer.Exit(2) from e
    print(f"removido '{id_}'")


def _checagens_do_comodo(pasta: Path, comodo: str) -> None:
    carregado = _carregar(pasta)
    problemas = checar(carregado.projeto, carregado.dados_comodos, carregado.regras, comodo)
    print()
    _listar_problemas(problemas)


# ---------------------------------------------------------------- móveis planejados

planejado_app = typer.Typer(help="Móveis planejados: construção interna, desenho e lista de corte.")
app.add_typer(planejado_app, name="planejado")


@planejado_app.command("criar")
def cmd_planejado_criar(
    projeto: Annotated[str, typer.Argument(help="Nome da pasta em projetos/.")],
    comodo: Annotated[str, typer.Argument(help="Id do cômodo.")],
    id_: Annotated[str, typer.Argument(metavar="MOVEL", help="Id do móvel.")],
    substituir: Annotated[
        bool, typer.Option("--substituir", help="Troca a construção que já existir.")
    ] = False,
    projetos: PastaProjetos = Path("projetos"),
) -> None:
    """Dá ao móvel a construção padrão do tipo dele (vãos, gavetas, prateleiras...).

    As medidas sugeridas entram como estimadas; ajuste no JSON (ou no frontend).
    """
    pasta = projetos / projeto
    carregado = _carregar(pasta)
    dados = carregado.dados_comodos.get(comodo)
    movel = next((m for m in dados.moveis if m.id == id_), None) if dados else None
    if movel is None:
        print(f"erro: móvel '{id_}' não existe no cômodo '{comodo}'")
        raise typer.Exit(2)
    try:
        construcao = planejado.construcao_sugerida(movel)
        editar.definir_construcao(pasta, comodo, id_, construcao, substituir)
    except (KeyError, ValueError) as e:
        print(f"erro: {e.args[0] if isinstance(e, KeyError) else e}")
        raise typer.Exit(2) from e
    vaos = construcao["vaos"]
    assert isinstance(vaos, list)
    print(f"construção padrão de '{movel.tipo}' gravada em '{id_}': {len(vaos)} vão(s)")
    _resumo_planejado(pasta, comodo, id_)


@planejado_app.command("gerar")
def cmd_planejado_gerar(
    projeto: Annotated[str, typer.Argument(help="Nome da pasta em projetos/.")],
    comodo: Annotated[str, typer.Argument(help="Id do cômodo.")],
    id_: Annotated[
        str | None, typer.Argument(metavar="[MOVEL]", help="Id do móvel (todos, se omitido).")
    ] = None,
    projetos: PastaProjetos = Path("projetos"),
    saida: Annotated[Path, typer.Option(help="Pasta das saídas geradas.")] = Path("out"),
    forcar: Annotated[
        bool, typer.Option("--forcar", help="Regera mesmo se a entrada não mudou.")
    ] = False,
) -> None:
    """Desenho técnico (DXF/PDF) e lista de corte (.xlsx) dos móveis planejados."""
    carregado = _carregar(projetos / projeto)
    dados = carregado.dados_comodos.get(comodo)
    planejados = [m.id for m in (dados.moveis if dados else []) if m.construcao is not None]
    alvos = [id_] if id_ else planejados
    if not alvos:
        print(f"nenhum móvel planejado em '{comodo}' (use `interiores planejado criar`)")
        raise typer.Exit(2)
    falhou = False
    for alvo in alvos:
        try:
            r = gerar_movel(carregado, saida, comodo, alvo, forcar=forcar)
            xlsx, gerou = gerar_lista(carregado, r.arquivos[0].parent, comodo, alvo, forcar)
        except (KeyError, ValueError) as e:
            print(f"  {alvo:<20} FALHOU: {e.args[0] if isinstance(e, KeyError) else e}")
            falhou = True
            continue
        _mostrar_resultado(alvo, r)
        if gerou:
            print(f"      {xlsx}")
    _listar_problemas(
        [
            p
            for p in checar(carregado.projeto, carregado.dados_comodos, carregado.regras, comodo)
            if p.elemento in alvos
        ]
    )
    if falhou:
        raise typer.Exit(1)


def _resumo_planejado(pasta: Path, comodo: str, id_: str) -> None:
    carregado = _carregar(pasta)
    movel = next(m for m in carregado.dados_comodos[comodo].moveis if m.id == id_)
    try:
        calc = planejado.calcular(movel)
    except planejado.ConstrucaoInvalidaError as e:
        print(f"erro: {e}")
        raise typer.Exit(1) from e
    pecas = sum(p.quantidade for p in calc.pecas)
    chapas = ", ".join(f"{c.chapas} × {c.material} {c.espessura} mm" for c in calc.chapas)
    print(f"  {pecas} peças · chapas: {chapas}")
    print(
        f"  gere o desenho e a lista de corte: interiores planejado gerar {pasta.name} {comodo} "
        f"{id_}"
    )
