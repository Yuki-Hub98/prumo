import json
import shutil
from pathlib import Path

import pytest
from apoio import CASA, RAIZ
from pydantic import ValidationError

from interiores_core import schema
from interiores_core.carregar import carregar


@pytest.fixture
def copia(tmp_path: Path) -> Path:
    destino = tmp_path / "casa"
    shutil.copytree(CASA, destino)
    return destino


def test_carrega_casa(copia: Path) -> None:
    c = carregar(copia)
    assert c.projeto.projeto == "casa"
    assert set(c.dados_comodos) == {"quarto"}
    assert len(c.hash_entrada) == 64
    assert len(c.hash_curto) == 10


def test_hash_ignora_formatacao_e_muda_com_medida(copia: Path) -> None:
    original = carregar(copia).hash_entrada
    arq = copia / "projeto.json"
    dados = json.loads(arq.read_text(encoding="utf-8"))
    arq.write_text(json.dumps(dados, indent=4, ensure_ascii=False), encoding="utf-8")
    assert carregar(copia).hash_entrada == original

    dados["pavimentos"][0]["pe_direito"]["valor"] = 2700
    arq.write_text(json.dumps(dados), encoding="utf-8")
    assert carregar(copia).hash_entrada != original


def test_hash_muda_com_mobiliario(copia: Path) -> None:
    original = carregar(copia).hash_entrada
    arq = copia / "comodos" / "quarto.json"
    dados = json.loads(arq.read_text(encoding="utf-8"))
    dados["moveis"][0]["centro"] = [1000, 1700]
    arq.write_text(json.dumps(dados), encoding="utf-8")
    assert carregar(copia).hash_entrada != original


def test_estimadas_por_escopo(copia: Path) -> None:
    c = carregar(copia)
    total = c.estimadas()
    quarto = {caminho for caminho, _ in c.estimadas("quarto")}
    banheiro = {caminho for caminho, _ in c.estimadas("banheiro")}
    assert len(total) == 40
    assert "comodos/quarto.moveis[cama].largura" in quarto
    assert not any("basculante" in x for x in quarto)
    assert not any("cama" in x for x in banheiro)
    assert "pavimentos[terreo].pe_direito" in quarto and "pavimentos[terreo].pe_direito" in banheiro
    with pytest.raises(KeyError):
        c.estimadas("cozinha")


def test_sem_pasta_comodos(copia: Path) -> None:
    shutil.rmtree(copia / "comodos")
    assert carregar(copia).dados_comodos == {}


def test_erros_de_leitura(copia: Path, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        carregar(tmp_path / "nao-existe")
    (copia / "comodos" / "quarto.json").write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(ValidationError):
        carregar(copia)


def test_exporta_schema(tmp_path: Path) -> None:
    gravados = schema.exportar(tmp_path / "schema")
    assert {g.name for g in gravados} == {"projeto.schema.json", "comodo.schema.json"}
    projeto = json.loads((tmp_path / "schema" / "projeto.schema.json").read_text(encoding="utf-8"))
    assert projeto["title"] == "Projeto"
    assert "Medida" in projeto["$defs"]


def test_schema_versionado_esta_atualizado(tmp_path: Path) -> None:
    """schema/ é versionado para o frontend: se falhar, rode `make schema`."""
    for gerado in schema.exportar(tmp_path):
        versionado = RAIZ / "schema" / gerado.name
        assert versionado.read_text(encoding="utf-8") == gerado.read_text(encoding="utf-8")
