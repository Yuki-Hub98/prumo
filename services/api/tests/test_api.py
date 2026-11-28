"""API: projetos, edição da planta com versão, problemas, histórico e exportação."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

PAV = "/projetos/casa/pavimentos/terreo"


def _trena(valor: int) -> dict[str, object]:
    return {"valor": valor, "origem": "trena"}


def test_saude_e_lista(api: TestClient) -> None:
    assert api.get("/saude").json()["status"] == "ok"
    assert api.get("/projetos").json() == [
        {"codigo": "casa", "versao": 1, "imovel": "casa", "apelido": "minha casa"}
    ]
    casa = api.get("/projetos/casa").json()
    assert casa["versao"] == 1
    assert {c["id"] for c in casa["projeto"]["pavimentos"][0]["comodos"]} == {"quarto", "banheiro"}
    assert "cama" in {m["id"] for m in casa["comodos"]["quarto"]["moveis"]}
    assert api.get("/projetos/nao-existe").status_code == 404


def test_editar_parede_grava_versao_e_exporta(api: TestClient, projetos: Path) -> None:
    r = api.patch(
        f"{PAV}/paredes/p1", params={"versao": 1}, json={"campos": {"espessura": _trena(140)}}
    )
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["versao"] == 2
    assert corpo["alteracoes"][0]["caminho"] == "projeto.pavimentos[terreo].paredes[p1].espessura"
    # a edição é um passo de rascunho: o JSON só muda ao salvar
    assert api.post("/projetos/casa/rascunho/salvar", params={"versao": 2}).status_code == 200
    exportado = json.loads((projetos / "casa" / "projeto.json").read_text())
    p1 = next(w for w in exportado["pavimentos"][0]["paredes"] if w["id"] == "p1")
    assert p1["espessura"] == {"valor": 140, "origem": "trena", "obs": "antes: 150 mm (estimada)"}

    hist = api.get("/projetos/casa/historico", params={"desde": 1}).json()
    assert [(h["versao"], h["operacao"]) for h in hist] == [(2, "alterar_parede")]
    assert api.get("/projetos/casa/versoes/1").json()["versao"] == 1


def test_versao_velha_da_409(api: TestClient) -> None:
    ok = api.patch(f"{PAV}/comodos/quarto", params={"versao": 1}, json={"campos": {"nome": "A"}})
    assert ok.status_code == 200
    r = api.patch(f"{PAV}/comodos/quarto", params={"versao": 1}, json={"campos": {"nome": "B"}})
    assert r.status_code == 409
    assert r.json()["versao_atual"] == 2
    assert api.patch(f"{PAV}/comodos/quarto", json={"campos": {}}).status_code == 422  # sem versão


def test_edicao_invalida_da_422_e_nao_grava(api: TestClient) -> None:
    r = api.patch(f"{PAV}/paredes/p1", params={"versao": 1}, json={"campos": {"lado_b": "x"}})
    assert r.status_code == 422
    assert r.json()["erro"] == "edicao_invalida"
    assert api.get("/projetos/casa").json()["versao"] == 1
    sem_origem = api.patch(
        f"{PAV}/paredes/p1", params={"versao": 1}, json={"campos": {"espessura": {"valor": 1}}}
    )
    assert sem_origem.status_code == 422  # a tela sempre pergunta a origem
    assert api.delete(f"{PAV}/paredes/p99", params={"versao": 1}).status_code == 404


def test_tomada_porta_e_janela(api: TestClient) -> None:
    tomada = {
        "instalacao": {"id": "tomada-tv", "forma": "ponto", "tipo": "tomada", "parede": "p2",
                       "altura": _trena(1100)},
        "distancia": 2000,
    }  # fmt: skip
    r = api.post(f"{PAV}/instalacoes", params={"versao": 1}, json=tomada)
    assert r.status_code == 200, r.text
    janela = {"id": "janela-2", "tipo": "janela", "parede": "p2",
              "distancia_inicio": _trena(500), "largura": _trena(800), "altura": _trena(800),
              "peitoril": _trena(1200)}  # fmt: skip
    r = api.post(f"{PAV}/aberturas", params={"versao": 2}, json=janela)
    assert r.status_code == 200, r.text
    r = api.patch(f"{PAV}/aberturas/porta-quarto", params={"versao": 3},
                  json={"dobradica": "fim"})  # fmt: skip
    assert r.status_code == 200, r.text
    assert api.delete(f"{PAV}/instalacoes/tomada-tv", params={"versao": 4}).json()["versao"] == 5


def test_remover_comodo_leva_o_mobiliario(api: TestClient, projetos: Path) -> None:
    r = api.delete(f"{PAV}/comodos/quarto", params={"versao": 1})
    assert r.status_code == 200, r.text
    assert "quarto" not in api.get("/projetos/casa").json()["comodos"]
    assert (projetos / "casa" / "comodos" / "quarto.json").exists()  # rascunho: ainda não
    api.post("/projetos/casa/rascunho/salvar", params={"versao": 2})
    assert not (projetos / "casa" / "comodos" / "quarto.json").exists()


def test_problemas_e_estimadas(api: TestClient) -> None:
    problemas = api.get("/projetos/casa/problemas").json()
    assert all({"severidade", "codigo", "mensagem"} <= p.keys() for p in problemas)
    estimadas = api.get("/projetos/casa/estimadas").json()
    caminhos = {e["caminho"] for e in estimadas}
    assert "pavimentos[terreo].paredes[p1].espessura" in caminhos
    api.patch(
        f"{PAV}/paredes/p1", params={"versao": 1}, json={"campos": {"espessura": _trena(150)}}
    )
    depois = {e["caminho"] for e in api.get("/projetos/casa/estimadas").json()}
    assert caminhos - depois == {"pavimentos[terreo].paredes[p1].espessura"}


def test_casa_do_zero_pela_api(api: TestClient, projetos: Path) -> None:
    novo = {"codigo": "ape", "imovel": "apartamento",
            "pavimento": {"pe_direito": _trena(2500)}}  # fmt: skip
    r = api.post("/projetos", json=novo)
    assert r.status_code == 201, r.text
    assert api.post("/projetos", json=novo).status_code == 422  # já existe
    base = "/projetos/ape/pavimentos/terreo"
    cantos = [(0, 0), (0, 3000), (4000, 3000), (4000, 0)]
    versao = 1
    for n, (a, b) in enumerate(zip(cantos, [*cantos[1:], cantos[0]], strict=True), 1):
        parede = {"id": f"p{n}", "inicio": a, "fim": b, "espessura": _trena(150),
                  "lado_a": "externo", "lado_b": "externo"}  # fmt: skip
        r = api.post(f"{base}/paredes", params={"versao": versao}, json=parede)
        assert r.status_code == 200, r.text
        versao = r.json()["versao"]
    sala = {"comodo": {"id": "sala", "nome": "Sala", "tipo": "sala",
                       "paredes": ["p1", "p2", "p3", "p4"]}}  # fmt: skip
    r = api.post(f"{base}/comodos", params={"versao": versao}, json=sala)
    assert r.status_code == 200, r.text
    assert not [p for p in r.json()["problemas"] if p["severidade"] == "erro"]
    r = api.post(f"{base}/vertices/mover", params={"versao": versao + 1},
                 json={"de": [4000, 0], "para": [4200, 0]})  # fmt: skip
    assert r.status_code == 200, r.text
    assert (projetos / "ape" / "projeto.json").is_file()
    assert {p["codigo"] for p in api.get("/projetos").json()} == {"ape", "casa"}


def test_openapi_para_o_frontend(api: TestClient) -> None:
    esquema = api.get("/openapi.json").json()
    assert "/projetos/{codigo}/pavimentos/{pavimento}/paredes/{id_}" in esquema["paths"]
    assert "Medida" in esquema["components"]["schemas"]


def test_geometria_para_a_tela(api: TestClient) -> None:
    g = api.get(f"{PAV}/geometria").json()
    assert {p["id"] for p in g["paredes"]} >= {"p1", "p2"}
    assert next(c for c in g["comodos"] if c["id"] == "quarto")["area_m2"] == 11.04
    assert {m["id"] for m in g["moveis"]} == {"cama", "guarda-roupa"}
    assert api.get("/projetos/casa/pavimentos/superior/geometria").status_code == 404


def test_preferencias(api: TestClient) -> None:
    assert api.get("/preferencias").json() == {"unidade": "cm"}  # padrão
    assert api.patch("/preferencias", json={"unidade": "m"}).json() == {"unidade": "m"}
    assert api.get("/preferencias").json() == {"unidade": "m"}
    assert api.patch("/preferencias", json={"unidade": "pé"}).status_code == 422


def test_estrutura_pilar_viga_laje(api: TestClient) -> None:
    """Aba Estruturas: lançar, mudar e tirar pilar, viga e laje; a planta traz a projeção."""
    laje = {"id": "laje-terreo", "tipo": "laje", "espessura": _trena(120)}
    pilar = {"id": "pilar-1", "tipo": "pilar", "centro": [0, 0],
             "largura": _trena(200), "profundidade": _trena(200)}  # fmt: skip
    for v, e in enumerate((laje, pilar), start=1):
        r = api.post(f"{PAV}/estrutura", params={"versao": v}, json=e)
        assert r.status_code == 200, r.text
    furo = [[500, 500], [1500, 500], [1500, 2500], [500, 2500]]
    r = api.patch(f"{PAV}/estrutura/laje-terreo", params={"versao": 3}, json={"furos": [furo]})
    assert r.status_code == 200, r.text
    tela = api.get(f"{PAV}/geometria").json()
    est = {e["id"]: e for e in tela["estrutura"]}
    assert est["laje-terreo"]["tipo"] == "laje" and len(est["laje-terreo"]["furos"]) == 1
    assert not est["pilar-1"]["estimada"]
    r = api.patch(f"{PAV}/estrutura/pilar-1", params={"versao": 4}, json={"espessura": _trena(1)})
    assert r.status_code == 422, r.text  # campo de laje no pilar
    assert api.delete(f"{PAV}/estrutura/pilar-1", params={"versao": 4}).json()["versao"] == 5
