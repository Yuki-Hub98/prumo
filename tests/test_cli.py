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
