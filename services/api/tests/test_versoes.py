"""Desfazer, refazer e voltar para uma versão (grava como versão nova)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

P = "/projetos/casa"
QUARTO = f"{P}/pavimentos/terreo/comodos/quarto"
MOVEIS = f"{P}/comodos/quarto/moveis"


def _moveis(projetos: Path) -> list[str]:
    arq = projetos / "casa" / "comodos" / "quarto.json"
    return [m["id"] for m in json.loads(arq.read_text())["moveis"]] if arq.exists() else []


def test_apagar_quarto_desfazer_e_refazer(api: TestClient, projetos: Path) -> None:
    antes = _moveis(projetos)
    assert antes
    inicio = api.get(f"{P}/versoes").json()
    assert (inicio["atual"], inicio["desfazer"], inicio["refazer"]) == (1, None, None)
    assert api.post(f"{P}/desfazer", params={"versao": 1}).status_code == 422  # nada ainda

    assert api.delete(QUARTO, params={"versao": 1}).json()["versao"] == 2
    assert _moveis(projetos) == []
    v = api.get(f"{P}/versoes").json()
    assert (v["desfazer"], v["refazer"]) == (1, None)

    r = api.post(f"{P}/desfazer", params={"versao": 2})
    assert r.status_code == 200, r.text
    assert r.json()["versao"] == 3
    assert _moveis(projetos) == antes  # quarto e móveis de volta, também no JSON
    comodos = api.get(P).json()["projeto"]["pavimentos"][0]["comodos"]
    assert "quarto" in [c["id"] for c in comodos]
    v = api.get(f"{P}/versoes").json()
    assert (v["atual"], v["desfazer"], v["refazer"]) == (3, None, 2)
    topo = v["versoes"][0]
    assert (topo["operacao"], topo["tipo"], topo["para"]) == ("desfazer:1", "desfazer", 1)
    assert [x["versao"] for x in v["versoes"]] == [3, 2, 1]  # nada foi apagado

    assert api.post(f"{P}/refazer", params={"versao": 3}).json()["versao"] == 4
    assert _moveis(projetos) == []  # refeito: apagado de novo
    v = api.get(f"{P}/versoes").json()
    assert (v["desfazer"], v["refazer"]) == (1, None)


def test_versao_desatualizada_da_conflito(api: TestClient) -> None:
    api.delete(f"{MOVEIS}/cama", params={"versao": 1})
    assert api.post(f"{P}/desfazer", params={"versao": 1}).status_code == 409


def test_restaurar_uma_versao_e_desfazer_a_volta(api: TestClient, projetos: Path) -> None:
    antes = _moveis(projetos)
    api.delete(f"{MOVEIS}/cama", params={"versao": 1})
    api.delete(QUARTO, params={"versao": 2})
    r = api.post(f"{P}/versoes/1/restaurar", params={"versao": 3})
    assert r.status_code == 200, r.text
    assert r.json()["versao"] == 4 and _moveis(projetos) == antes
    v = api.get(f"{P}/versoes").json()
    assert (v["versoes"][0]["tipo"], v["desfazer"], v["refazer"]) == ("reverter", 3, None)
    assert api.post(f"{P}/versoes/4/restaurar", params={"versao": 4}).status_code == 422
    assert api.post(f"{P}/versoes/99/restaurar", params={"versao": 4}).status_code == 404
    assert api.post(f"{P}/desfazer", params={"versao": 4}).json()["versao"] == 5
    assert _moveis(projetos) == []  # desfazer o "voltar": quarto apagado de novo
