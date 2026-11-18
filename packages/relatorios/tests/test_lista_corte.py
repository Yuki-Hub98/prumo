"""Lista de corte (.xlsx) do móvel planejado."""

import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from openpyxl import load_workbook

from interiores_core import planejado
from interiores_core.carregar import carregar
from interiores_core.modelo import Movel
from interiores_relatorios.lista_corte import AVISO_OBRA, gerar_lista, montar_planilha

DADOS = Path(__file__).resolve().parents[2] / "core" / "tests" / "dados" / "casa"


@pytest.fixture
def casa(tmp_path: Path) -> Path:
    destino = tmp_path / "casa"
    shutil.copytree(DADOS, destino)
    arq = destino / "comodos" / "quarto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    gr = d["moveis"][1]
    gr["construcao"] = planejado.construcao_sugerida(Movel.model_validate(gr))
    arq.write_text(json.dumps(d), encoding="utf-8")
    return destino


def test_planilha(casa: Path) -> None:
    wb = montar_planilha(carregar(casa), "quarto", "guarda-roupa", date(2026, 11, 17))
    assert wb.sheetnames == ["Resumo", "Peças", "Ferragens"]
    resumo = [c for linha in wb["Resumo"].iter_rows(values_only=True) for c in linha if c]
    assert any(str(c).startswith(AVISO_OBRA) for c in resumo)
    assert (
        "MDF branco" in resumo
        and "Chapas (estimativa com 15% de perda, sem plano de corte)" in resumo
    )
    pecas = list(wb["Peças"].iter_rows(min_row=2, values_only=True))
    lateral = next(p for p in pecas if p[1] == "Lateral")
    assert lateral[3:8] == (18, 2300, 550, 2, "1C")
    total = next(p for p in pecas if p[1] == "Total")
    assert total[6] == sum(p[6] for p in pecas if isinstance(p[0], int))
    ferragens = [r[0] for r in wb["Ferragens"].iter_rows(min_row=2, values_only=True)]
    assert any("trilho de porta de correr" in f for f in ferragens)  # guarda-roupa de correr
    assert not any("Dobradiça" in f for f in ferragens)
    assert wb.properties.created.year == 2026


def test_gerar_com_cache_e_erros(casa: Path, tmp_path: Path) -> None:
    c = carregar(casa)
    xlsx, gerou = gerar_lista(c, tmp_path, "quarto", "guarda-roupa")
    assert gerou and xlsx.name == "planejado-guarda-roupa-corte.xlsx"
    assert load_workbook(xlsx)["Peças"]["B2"].value == "Lateral"
    assert gerar_lista(c, tmp_path, "quarto", "guarda-roupa") == (xlsx, False)
    assert gerar_lista(c, tmp_path, "quarto", "guarda-roupa", forcar=True)[1]
    with pytest.raises(KeyError):
        montar_planilha(c, "quarto", "nada")
    with pytest.raises(ValueError, match="não tem construção"):
        montar_planilha(c, "quarto", "cama")
