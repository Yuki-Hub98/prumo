"""Testes de integração da CLI sobre o projeto de exemplo."""

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from interiores_cli.main import app

RAIZ = Path(__file__).resolve().parents[1]
runner = CliRunner()


def test_validar_casa() -> None:
    r = runner.invoke(app, ["validar", "casa", "--projetos", str(RAIZ / "projetos"), "--estimadas"])
    assert r.exit_code == 0, r.output
    assert "quarto" in r.output and "banheiro" in r.output
    assert "PRELIMINAR — NÃO USAR PARA OBRA" in r.output
    assert "pavimentos[terreo].pe_direito = 2600 mm" in r.output


def test_validar_com_erro_sai_com_1(tmp_path: Path) -> None:
    shutil.copytree(RAIZ / "projetos" / "casa", tmp_path / "casa")
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
    args = ["cad", "casa", "--projetos", str(RAIZ / "projetos"), "--saida", str(tmp_path)]
    r = runner.invoke(app, [*args, "--comodo", "quarto"])
    assert r.exit_code == 0, r.output
    assert "terreo/quarto" in r.output and "gerado" in r.output and "1:25 A3" in r.output
    assert (tmp_path / "casa/terreo/quarto/base/planta.dxf").exists()
    assert (tmp_path / "casa/terreo/quarto/base/planta.pdf").exists()
    assert "PRELIMINAR — NÃO USAR PARA OBRA" in r.output
    assert "INFO" in r.output  # problemas listados depois da geração

    r = runner.invoke(app, [*args, "--comodo", "quarto"])
    assert "inalterado" in r.output


def test_cad_tudo_e_pavimento(tmp_path: Path) -> None:
    args = ["cad", "casa", "--projetos", str(RAIZ / "projetos"), "--saida", str(tmp_path)]
    r = runner.invoke(app, args)
    assert r.exit_code == 0, r.output
    for pasta in ("_geral", "quarto/base", "banheiro/base"):
        assert (tmp_path / "casa/terreo" / pasta / "planta.pdf").exists()
    r = runner.invoke(app, [*args, "--pavimento", "terreo", "--forcar"])
    assert r.exit_code == 0 and "terreo/_geral" in r.output and "gerado" in r.output


def test_cad_escopo_inexistente_e_comodo_aberto(tmp_path: Path) -> None:
    args = ["cad", "casa", "--projetos", str(RAIZ / "projetos"), "--saida", str(tmp_path)]
    assert runner.invoke(app, [*args, "--comodo", "cozinha"]).exit_code == 2
    assert runner.invoke(app, [*args, "--pavimento", "superior"]).exit_code == 2
    r = runner.invoke(app, [*args, "--comodo", "quarto", "--pavimento", "superior"])
    assert r.exit_code == 2

    shutil.copytree(RAIZ / "projetos" / "casa", tmp_path / "p" / "casa")
    arq = tmp_path / "p" / "casa" / "projeto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["pavimentos"][0]["comodos"][1]["paredes"].remove("p4")
    arq.write_text(json.dumps(d), encoding="utf-8")
    r = runner.invoke(
        app, ["cad", "casa", "--projetos", str(tmp_path / "p"), "--saida", str(tmp_path / "o")]
    )
    assert r.exit_code == 1
    assert "banheiro" in r.output and "FALHOU" in r.output
