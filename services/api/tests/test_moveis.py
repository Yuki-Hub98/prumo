"""API de móveis: catálogo, adicionar, mover, alterar e remover."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

MOVEIS = "/projetos/casa/comodos/quarto/moveis"


def test_catalogo(api: TestClient) -> None:
    cat = api.get("/catalogo").json()
    tipos = {i["tipo"] for i in cat["itens"]}
    assert {"cama", "tv", "guarda_roupa", "sofa"} <= tipos


def test_tv_na_parede_e_exportada(api: TestClient, projetos: Path) -> None:
    tv = {"tipo": "tv", "modelo": "50pol", "parede": "p2", "distancia": 1000}
    r = api.post(MOVEIS, params={"versao": 1}, json=tv)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["versao"] == 2
    assert [a["caminho"] for a in corpo["alteracoes"]] == ["comodos.quarto.moveis[tv]"]
    api.post("/projetos/casa/rascunho/salvar", params={"versao": 2})
    arq = json.loads((projetos / "casa" / "comodos" / "quarto.json").read_text())
    tv = next(m for m in arq["moveis"] if m["id"] == "tv")
    assert tv["rotacao"] == 90
    hist = api.get("/projetos/casa/historico", params={"desde": 1}).json()
    assert [h["operacao"] for h in hist] == ["adicionar_movel"]


def test_arrastar_girar_alterar_remover(api: TestClient) -> None:
    r = api.post(f"{MOVEIS}/cama/mover", params={"versao": 1}, json={"centro": [2000, 1300]})
    assert r.status_code == 200, r.text
    r = api.post(f"{MOVEIS}/cama/mover", params={"versao": 2}, json={"rotacao": 180})
    assert r.status_code == 200, r.text
    r = api.patch(f"{MOVEIS}/cama", params={"versao": 3},
                  json={"largura": {"valor": 1580, "origem": "trena"}})  # fmt: skip
    assert r.status_code == 200, r.text
    cama = next(
        m for m in api.get("/projetos/casa").json()["comodos"]["quarto"]["moveis"]
        if m["id"] == "cama"
    )  # fmt: skip
    assert (cama["centro"], cama["rotacao"], cama["largura"]["valor"]) == ([2000, 1300], 180, 1580)
    assert api.delete(f"{MOVEIS}/cama", params={"versao": 4}).json()["versao"] == 5
    assert api.delete(f"{MOVEIS}/cama", params={"versao": 5}).status_code == 404


def test_erros(api: TestClient) -> None:
    assert api.post(MOVEIS, params={"versao": 1}, json={"tipo": "tv"}).status_code == 422
    r = api.post(MOVEIS, params={"versao": 1}, json={"tipo": "foguete", "centro": [0, 0]})
    assert r.status_code == 422 and "catálogo" in r.json()["mensagem"]
    r = api.post(f"{MOVEIS}/cama/mover", params={"versao": 1}, json={"parede": "p4"})
    assert r.status_code == 422  # p4 não é parede do quarto
    r = api.post(f"{MOVEIS}/cama/mover", params={"versao": 9}, json={"rotacao": 0})
    assert r.status_code == 409
    r = api.post("/projetos/casa/comodos/cozinha/moveis", params={"versao": 1},
                 json={"tipo": "tv", "centro": [0, 0]})  # fmt: skip
    assert r.status_code == 404


def test_checagem_volta_na_resposta(api: TestClient) -> None:
    r = api.post(f"{MOVEIS}/cama/mover", params={"versao": 1}, json={"centro": [900, 1325]})
    assert r.status_code == 200
    assert r.json()["novos"], "cama em cima do guarda-roupa deveria gerar problema"
