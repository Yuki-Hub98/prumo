"""Testes de integração da CLI sobre o projeto de exemplo."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from interiores_cli.main import app

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "packages" / "core" / "tests" / "dados"
"""Cópia congelada de projetos/casa (os testes não dependem dos dados reais)."""
runner = CliRunner()


def test_validar_casa() -> None:
    r = runner.invoke(app, ["validar", "casa", "--projetos", str(DADOS), "--estimadas"])
    assert r.exit_code == 0, r.output
    assert "quarto" in r.output and "banheiro" in r.output
    assert "PRELIMINAR — NÃO USAR PARA OBRA" in r.output
    assert "pavimentos[terreo].pe_direito = 2600 mm" in r.output
    assert "lateral_cama" in r.output and "AVISO (3)" in r.output  # checagens de uso


def test_validar_com_erro_sai_com_1(tmp_path: Path) -> None:
    shutil.copytree(DADOS / "casa", tmp_path / "casa")
    arq = tmp_path / "casa" / "projeto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["pavimentos"][0]["comodos"][1]["paredes"].remove("p4")
    arq.write_text(json.dumps(d), encoding="utf-8")
    r = runner.invoke(app, ["validar", "casa", "--projetos", str(tmp_path)])
    assert r.exit_code == 1
    assert "ERRO" in r.output and "comodo_nao_fechado" in r.output and "não fechado" in r.output


def test_validar_formato_invalido_e_inexistente(tmp_path: Path) -> None:
    r = runner.invoke(app, ["validar", "nada", "--projetos", str(tmp_path)])
    assert r.exit_code == 2 and "não encontrado" in r.output
    (tmp_path / "ruim").mkdir()
    (tmp_path / "ruim" / "projeto.json").write_text('{"schema_version": 1}', encoding="utf-8")
    r = runner.invoke(app, ["validar", "ruim", "--projetos", str(tmp_path)])
    assert r.exit_code == 2 and "formato inválido" in r.output


def test_schema(tmp_path: Path) -> None:
    r = runner.invoke(app, ["schema", "--saida", str(tmp_path)])
    assert r.exit_code == 0
    assert (tmp_path / "projeto.schema.json").exists()


def test_cad_comodo_e_cache(tmp_path: Path) -> None:
    args = ["cad", "casa", "--projetos", str(DADOS), "--saida", str(tmp_path)]
    r = runner.invoke(app, [*args, "--comodo", "quarto"])
    assert r.exit_code == 0, r.output
    assert "terreo/quarto" in r.output and "gerado" in r.output and "1:25 A3" in r.output
    assert (tmp_path / "casa/terreo/quarto/base/planta.dxf").exists()
    assert (tmp_path / "casa/terreo/quarto/base/planta.pdf").exists()
    assert "PRELIMINAR — NÃO USAR PARA OBRA" in r.output
    assert "INFO" in r.output  # problemas listados depois da geração
    assert "cortes e elevações (gerado): corte-aa, corte-bb, elevacao-" in r.output
    assert (tmp_path / "casa/terreo/quarto/base/elevacao-p1.pdf").exists()

    r = runner.invoke(app, [*args, "--comodo", "quarto"])
    assert "inalterado" in r.output


def test_cad_tudo_e_pavimento(tmp_path: Path) -> None:
    args = ["cad", "casa", "--projetos", str(DADOS), "--saida", str(tmp_path)]
    r = runner.invoke(app, args)
    assert r.exit_code == 0, r.output
    for pasta in ("_geral", "quarto/base", "banheiro/base"):
        assert (tmp_path / "casa/terreo" / pasta / "planta.pdf").exists()
    r = runner.invoke(app, [*args, "--pavimento", "terreo", "--forcar"])
    assert r.exit_code == 0 and "terreo/_geral" in r.output and "gerado" in r.output


def test_cad_escopo_inexistente_e_comodo_aberto(tmp_path: Path) -> None:
    args = ["cad", "casa", "--projetos", str(DADOS), "--saida", str(tmp_path)]
    assert runner.invoke(app, [*args, "--comodo", "cozinha"]).exit_code == 2
    assert runner.invoke(app, [*args, "--pavimento", "superior"]).exit_code == 2
    r = runner.invoke(app, [*args, "--comodo", "quarto", "--pavimento", "superior"])
    assert r.exit_code == 2

    shutil.copytree(DADOS / "casa", tmp_path / "p" / "casa")
    arq = tmp_path / "p" / "casa" / "projeto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["pavimentos"][0]["comodos"][1]["paredes"].remove("p4")
    arq.write_text(json.dumps(d), encoding="utf-8")
    r = runner.invoke(
        app, ["cad", "casa", "--projetos", str(tmp_path / "p"), "--saida", str(tmp_path / "o")]
    )
    assert r.exit_code == 1
    assert "banheiro" in r.output and "FALHOU" in r.output


def test_catalogo() -> None:
    r = runner.invoke(app, ["catalogo"])
    assert r.exit_code == 0 and "guarda_roupa" in r.output and "eletronicos" in r.output
    r = runner.invoke(app, ["catalogo", "cama"])
    assert "queen" in r.output and "(padrão)" in r.output
    assert runner.invoke(app, ["catalogo", "foguete"]).exit_code == 2


def test_movel_adicionar_mover_listar_remover(tmp_path: Path) -> None:
    shutil.copytree(DADOS / "casa", tmp_path / "casa")
    p = ["--projetos", str(tmp_path)]
    r = runner.invoke(
        app,
        [
            "movel",
            "adicionar",
            "casa",
            "quarto",
            "tv",
            "--modelo",
            "43pol",
            "--em",
            "160,1325",
            "--rotacao",
            "270",
            *p,
        ],
    )
    assert r.exit_code == 0, r.output
    assert "adicionado 'tv'" in r.output and "moveis_sobrepostos" in r.output
    r = runner.invoke(
        app, ["movel", "mover", "casa", "quarto", "tv", "--em", "3380,1325", "--rotacao", "90", *p]
    )
    assert r.exit_code == 0 and "movido 'tv'" in r.output
    r = runner.invoke(app, ["movel", "listar", "casa", "quarto", *p])
    assert "tv" in r.output and "em (3380, 1325) rot 90" in r.output
    r = runner.invoke(
        app,
        [
            "movel",
            "adicionar",
            "casa",
            "quarto",
            "cama",
            "--em",
            "1,1",
            "--largura",
            "1500",
            "--origem",
            "trena",
            *p,
        ],
    )
    assert "adicionado 'cama-2'" in r.output
    dados = json.loads((tmp_path / "casa/comodos/quarto.json").read_text(encoding="utf-8"))
    assert dados["moveis"][-1]["largura"]["origem"] == "trena"
    assert runner.invoke(app, ["movel", "remover", "casa", "quarto", "tv", *p]).exit_code == 0
    assert runner.invoke(app, ["movel", "remover", "casa", "quarto", "tv", *p]).exit_code == 2
    assert runner.invoke(app, ["movel", "mover", "casa", "quarto", "tv", *p]).exit_code == 2
    r = runner.invoke(app, ["movel", "listar", "casa", "banheiro", *p])
    assert "nenhum móvel" in r.output


def test_movel_erros(tmp_path: Path) -> None:
    shutil.copytree(DADOS / "casa", tmp_path / "casa")
    p = ["--projetos", str(tmp_path)]
    for args in (
        ["foguete", "--em", "1,1"],
        ["cama", "--modelo", "x", "--em", "1,1"],
        ["cama", "--id", "cama", "--em", "1,1"],
    ):
        r = runner.invoke(app, ["movel", "adicionar", "casa", "quarto", *args, *p])
        assert r.exit_code == 2 and "erro:" in r.output
    r = runner.invoke(app, ["movel", "adicionar", "casa", "quarto", "cama", "--em", "1", *p])
    assert r.exit_code == 2


def test_movel_na_parede(tmp_path: Path) -> None:
    shutil.copytree(DADOS / "casa", tmp_path / "casa")
    p = ["--projetos", str(tmp_path)]
    r = runner.invoke(
        app,
        ["movel", "adicionar", "casa", "quarto", "criado_mudo", "--parede", "p2", "--a", "100", *p],
    )
    assert r.exit_code == 0, r.output
    assert "centro (3225, 325), rotação 90" in r.output
    r = runner.invoke(
        app, ["movel", "mover", "casa", "quarto", "criado-mudo", "--parede", "p1", "--a", "200", *p]
    )
    assert "centro (425, 275), rotação 0" in r.output
    erros = (
        ["adicionar", "casa", "quarto", "estante", *p],
        ["adicionar", "casa", "quarto", "estante", "--em", "1,1", "--parede", "p1", *p],
        ["adicionar", "casa", "quarto", "estante", "--parede", "p4", *p],
        ["mover", "casa", "quarto", "criado-mudo", "--parede", "p1", "--rotacao", "0", *p],
    )
    for args in erros:
        assert runner.invoke(app, ["movel", *args]).exit_code == 2, args


def test_planejado_criar_e_gerar(tmp_path: Path) -> None:
    shutil.copytree(DADOS / "casa", tmp_path / "casa")
    p = ["--projetos", str(tmp_path)]
    r = runner.invoke(app, ["planejado", "criar", "casa", "quarto", "guarda-roupa", *p])
    assert r.exit_code == 0, r.output
    assert "2 vão(s)" in r.output and "MDF branco 18 mm" in r.output
    assert "planejado gerar casa quarto guarda-roupa" in r.output
    r = runner.invoke(app, ["planejado", "criar", "casa", "quarto", "guarda-roupa", *p])
    assert r.exit_code == 2 and "já tem construção" in r.output
    r = runner.invoke(
        app, ["planejado", "criar", "casa", "quarto", "guarda-roupa", "--substituir", *p]
    )
    assert r.exit_code == 0
    saida = tmp_path / "out"
    r = runner.invoke(app, ["planejado", "gerar", "casa", "quarto", *p, "--saida", str(saida)])
    assert r.exit_code == 0, r.output
    base = saida / "casa/terreo/quarto/base"
    for nome in (
        "planejado-guarda-roupa.pdf",
        "planejado-guarda-roupa.dxf",
        "planejado-guarda-roupa-corte.xlsx",
    ):
        assert (base / nome).exists(), nome
    r = runner.invoke(
        app, ["planejado", "gerar", "casa", "quarto", "guarda-roupa", *p, "--saida", str(saida)]
    )
    assert "inalterado" in r.output


def test_planejado_erros(tmp_path: Path) -> None:
    shutil.copytree(DADOS / "casa", tmp_path / "casa")
    p = ["--projetos", str(tmp_path)]
    assert runner.invoke(app, ["planejado", "criar", "casa", "quarto", "nada", *p]).exit_code == 2
    r = runner.invoke(app, ["planejado", "criar", "casa", "quarto", "cama", *p])
    assert r.exit_code == 2 and "não é planejável" in r.output
    r = runner.invoke(app, ["planejado", "gerar", "casa", "quarto", *p])
    assert r.exit_code == 2 and "nenhum móvel planejado" in r.output
    r = runner.invoke(
        app, ["planejado", "gerar", "casa", "quarto", "cama", *p, "--saida", str(tmp_path / "o")]
    )
    assert r.exit_code == 1 and "FALHOU" in r.output


def test_render_com_blender_falso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import stat

    exe = tmp_path / "blender"
    exe.write_text(
        "#!/usr/bin/env python3\nimport json, sys\nfrom pathlib import Path\n"
        "a = sys.argv[sys.argv.index('--') + 1:]\nc = json.loads(Path(a[0]).read_text())\n"
        "for n in ('render-perspectiva.png', 'render-superior.png', c['comodo'] + '.glb'):\n"
        "    (Path(a[1]) / n).write_bytes(b'ok')\n",
        encoding="utf-8",
    )
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("INTERIORES_BLENDER", str(exe))
    args = ["render", "casa", "quarto", "--projetos", str(DADOS), "--saida", str(tmp_path / "o")]
    r = runner.invoke(app, args)
    assert r.exit_code == 0, r.output
    assert "quarto/base" in r.output and "gerado" in r.output and "PRELIMINAR" in r.output
    assert "inalterado" in runner.invoke(app, args).output
    assert runner.invoke(app, [*args, "--variacao", "nada"]).exit_code == 2
    r = runner.invoke(app, ["render", "casa", "cozinha", "--projetos", str(DADOS)])
    assert r.exit_code == 2
