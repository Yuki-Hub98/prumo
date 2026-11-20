"""API de cores: variações por cômodo com cor por parede."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

VAR = "/projetos/casa/comodos/quarto/variacoes"


def test_parede_de_destaque(api: TestClient, projetos: Path) -> None:
    assert api.get(VAR).json() == {}
    corpo = {"nome": "Destaque", "cores": {"parede": "#eeeeee", "paredes": {"p2": "#c46b4f"},
                                            "moveis": {"cama": "#3e2c20"}}}  # fmt: skip
    r = api.put(f"{VAR}/destaque", params={"versao": 1}, json=corpo)
    assert r.status_code == 200, r.text
    assert r.json()["versao"] == 2
    assert any(a["caminho"].startswith("variacoes.quarto") for a in r.json()["alteracoes"])
    api.post("/projetos/casa/rascunho/salvar", params={"versao": 2})
    arq = json.loads((projetos / "casa" / "variacoes" / "quarto" / "destaque.json").read_text())
    assert arq["cores"]["paredes"] == {"p2": "#c46b4f"}
    assert api.get(VAR).json()["destaque"]["cores"]["parede"] == "#eeeeee"

    r = api.put(f"{VAR}/destaque", params={"versao": 2}, json={"cores": {"piso": "#8b6f4e"}})
    assert r.status_code == 200  # substitui a paleta inteira
    assert api.get(VAR).json()["destaque"]["cores"]["paredes"] == {}

    assert api.delete(f"{VAR}/destaque", params={"versao": 3}).status_code == 200
    assert api.get(VAR).json() == {}
    api.post("/projetos/casa/rascunho/salvar", params={"versao": 4})
    assert not (projetos / "casa" / "variacoes" / "quarto" / "destaque.json").exists()


def test_recusas(api: TestClient) -> None:
    r = api.put(f"{VAR}/x", params={"versao": 1}, json={"cores": {"paredes": {"p4": "#000000"}}})
    assert r.status_code == 422 and "p4" in r.json()["mensagem"]
    assert api.put(f"{VAR}/base", params={"versao": 1}, json={}).status_code == 422
    assert api.put(f"{VAR}/x", params={"versao": 1},
                   json={"cores": {"parede": "azul"}}).status_code == 422  # fmt: skip
    assert api.delete(f"{VAR}/nao-existe", params={"versao": 1}).status_code == 404
    assert api.get("/projetos/casa/comodos/cozinha/variacoes").status_code == 404


def test_faces_na_geometria(api: TestClient) -> None:
    g = api.get("/projetos/casa/pavimentos/terreo/geometria").json()
    quarto = next(c for c in g["comodos"] if c["id"] == "quarto")
    assert {f["parede"] for f in quarto["faces"]} >= {"p1", "p2", "p7"}
