"""API: imóvel, pavimentos, renomear e apagar projeto."""

from pathlib import Path

from fastapi.testclient import TestClient


def test_imovel(api: TestClient) -> None:
    r = api.patch("/projetos/casa/imovel", params={"versao": 1},
                  json={"endereco_apelido": "casa da praia"})  # fmt: skip
    assert r.status_code == 200, r.text
    assert api.get("/projetos").json()[0]["apelido"] == "casa da praia"


def test_pavimentos(api: TestClient, projetos: Path) -> None:
    sup = {"pavimento": {"id": "superior", "nome": "Superior",
                         "cota_piso": {"valor": 2900, "origem": "projeto"},
                         "pe_direito": {"valor": 2600, "origem": "trena"}}}  # fmt: skip
    r = api.post("/projetos/casa/pavimentos", params={"versao": 1}, json=sup)
    assert r.status_code == 200, r.text
    pavs = [p["id"] for p in api.get("/projetos/casa").json()["projeto"]["pavimentos"]]
    assert pavs == ["terreo", "superior"]
    r = api.delete("/projetos/casa/pavimentos/terreo", params={"versao": 2})
    assert r.status_code == 422 and "cascata" in r.json()["mensagem"]
    r = api.delete("/projetos/casa/pavimentos/terreo", params={"versao": 2, "cascata": True})
    assert r.status_code == 200, r.text
    casa = api.get("/projetos/casa").json()
    assert casa["comodos"] == {}  # o mobiliário do térreo foi junto
    assert not (projetos / "casa" / "comodos" / "quarto.json").exists()


def test_renomear(api: TestClient, projetos: Path) -> None:
    (projetos / "casa" / "referencias").mkdir()
    (projetos / "casa" / "referencias" / "croqui.png").write_bytes(b"png")
    r = api.post("/projetos/casa/renomear", params={"versao": 1}, json={"codigo": "casa-praia"})
    assert r.status_code == 200, r.text
    assert r.json()["versao"] == 2
    assert [p["codigo"] for p in api.get("/projetos").json()] == ["casa-praia"]
    assert (projetos / "casa-praia" / "referencias" / "croqui.png").is_file()  # pasta foi junto
    assert not (projetos / "casa").exists()
    assert api.get("/projetos/casa-praia/historico").json()[-1]["operacao"] == "renomear_projeto"
    assert api.get("/projetos/casa").status_code == 404


def test_renomear_para_existente(api: TestClient) -> None:
    novo = {"codigo": "ape", "imovel": "apartamento",
            "pavimento": {"pe_direito": {"valor": 2500, "origem": "trena"}}}  # fmt: skip
    assert api.post("/projetos", json=novo).status_code == 201
    r = api.post("/projetos/casa/renomear", params={"versao": 1}, json={"codigo": "ape"})
    assert r.status_code == 422 and "já existe" in r.json()["mensagem"]


def test_apagar_pede_confirmacao_e_guarda_a_pasta(api: TestClient, projetos: Path) -> None:
    r = api.delete("/projetos/casa", params={"versao": 1, "confirmar": "outra"})
    assert r.status_code == 422
    r = api.delete("/projetos/casa", params={"versao": 9, "confirmar": "casa"})
    assert r.status_code == 409
    r = api.delete("/projetos/casa", params={"versao": 1, "confirmar": "casa"})
    assert r.status_code == 200, r.text
    movida = Path(r.json()["pasta_movida_para"])
    assert movida.parent == projetos / "_apagados" and (movida / "projeto.json").is_file()
    assert api.get("/projetos").json() == []
