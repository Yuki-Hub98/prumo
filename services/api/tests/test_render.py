"""API da fila de render (fila falsa: sem Redis nem Blender)."""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from interiores_banco import renders
from interiores_banco.conexao import sessao

URL = "/projetos/casa/comodos/quarto/renders"


def test_pedir_acompanhar_e_baixar(api: TestClient, fila: Any, engine: Any, tmp_path: Path) -> None:
    r = api.post(URL, json={"qualidade": "rascunho"})
    assert r.status_code == 202, r.text
    info = r.json()
    assert (info["status"], info["variacao"], info["qualidade"]) == ("na_fila", "base", "rascunho")
    assert info["estimativa_s"] and info["restante_s"] == info["estimativa_s"]
    assert fila.ids == [info["id"]]
    assert api.post(URL, json={"qualidade": "rascunho"}).json()["id"] == info["id"]  # mesmo pedido
    assert fila.ids == [info["id"]]  # não enfileira de novo

    rid = info["id"]
    assert api.get(f"/renders/{rid}/imagens/render-perspectiva.png").status_code == 404
    with sessao(engine) as s:  # o worker faria isto
        pedido = renders.obter(s, rid)
        renders.comecar(s, pedido)
        renders.andar(s, pedido, 0.5, 2, 3.0)
    rodando = api.get(f"/renders/{rid}").json()
    assert rodando["status"] == "rodando" and rodando["imagem_atual"] == 2
    assert rodando["restante_s"] is not None and rodando["decorrido_s"] is not None

    png = tmp_path / "render-perspectiva.png"
    png.write_bytes(b"\x89PNG")
    (tmp_path / "q.glb").write_bytes(b"glTF")
    with sessao(engine) as s:
        renders.concluir(s, renders.obter(s, rid), str(tmp_path), [png.name, "q.glb"], 9.5, False)
    pronto = api.get(f"/renders/{rid}").json()
    assert pronto["status"] == "pronto" and pronto["duracao_s"] == 9.5
    assert pronto["imagens_url"] == [f"/renders/{rid}/imagens/render-perspectiva.png"]
    assert pronto["modelo_url"] == f"/renders/{rid}/modelo"
    glb = api.get(pronto["modelo_url"])
    assert glb.status_code == 200 and glb.headers["content-type"] == "model/gltf-binary"
    assert rodando["modelo_url"] is None  # só depois de pronto
    img = api.get(pronto["imagens_url"][0])
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert api.get(f"/renders/{rid}/imagens/..%2F..%2Fsegredo").status_code == 404
    assert api.get(f"/renders/{rid}/imagens/q.glb").status_code == 404  # só as imagens
    assert [x["id"] for x in api.get("/projetos/casa/renders").json()] == [rid]


def test_recusas(api: TestClient) -> None:
    assert api.post(URL, json={"variacao": "nao-existe"}).status_code == 404
    assert api.post(URL, json={"qualidade": "ultra"}).status_code == 422
    assert api.post("/projetos/casa/comodos/cozinha/renders", json={}).status_code == 404
    assert api.get("/renders/999").status_code == 404
    assert api.get("/renders/999/modelo").status_code == 404


def test_estimativas(api: TestClient) -> None:
    e = api.get("/renders/estimativas").json()
    assert e["final"] == 119.0 and 0 < e["rascunho"] < e["final"]  # sem histórico


def test_vistas(api: TestClient, fila: Any) -> None:
    vs = api.get("/projetos/casa/comodos/quarto/vistas").json()
    nomes = [v["nome"] for v in vs]
    assert {"perspectiva", "porta", "cama", "superior"} <= set(nomes) and "canto-1" in nomes
    r = api.post(URL, json={"qualidade": "rascunho", "vistas": ["cama", "porta", "cama"]})
    assert r.status_code == 202, r.text
    info = r.json()
    assert info["vistas"] == ["cama", "porta"] and info["imagens"] == 2
    outro = api.post(URL, json={"qualidade": "rascunho", "vistas": ["cama"]}).json()
    assert outro["id"] != info["id"]  # vistas diferentes: outro pedido
    assert api.post(URL, json={"vistas": ["janela-magica"]}).status_code == 422
    assert api.post(URL, json={"vistas": []}).status_code == 422
    assert api.get("/projetos/casa/comodos/banheiro/vistas").status_code == 200
    um, tres = (api.get("/renders/estimativas", params={"imagens": n}).json() for n in (1, 3))
    assert um["final"] < tres["final"]


def test_render_do_pavimento(api: TestClient, fila: Any) -> None:
    url = "/projetos/casa/pavimentos/terreo/renders"
    r = api.post(url, json={})
    assert r.status_code == 202, r.text
    info = r.json()
    assert (info["escopo"], info["comodo"], info["vistas"]) == (
        "pavimento",
        "terreo",
        ["perspectiva", "superior"],
    )
    assert fila.ids == [info["id"]]
    assert api.post(url, json={}).json()["id"] == info["id"]  # mesmo pedido, não repete
    # listagens separadas: o pavimento não aparece como cômodo e vice-versa
    assert [x["id"] for x in api.get("/projetos/casa/renders?pavimento=terreo").json()] == [
        info["id"]
    ]
    assert api.get("/projetos/casa/renders?comodo=terreo").json() == []
    quarto = api.post(URL, json={}).json()
    assert quarto["escopo"] == "comodo"
    assert [x["id"] for x in api.get("/projetos/casa/renders?pavimento=terreo").json()] == [
        info["id"]
    ]


def test_recusas_do_pavimento(api: TestClient) -> None:
    assert api.post("/projetos/casa/pavimentos/superior/renders", json={}).status_code == 404
    url = "/projetos/casa/pavimentos/terreo/renders"
    assert api.post(url, json={"vistas": ["cama"]}).status_code == 422
    assert api.post(url, json={"qualidade": "ultra"}).status_code == 422


def test_cena_3d_ao_vivo(api: TestClient) -> None:
    """A cena do visor muda junto com o projeto (sem render): móvel movido sai na posição nova."""
    r = api.get("/projetos/casa/comodos/quarto/cena")
    assert r.status_code == 200, r.text
    cena = r.json()
    nomes = {p["nome"] for p in cena["prismas"]} | {c["nome"] for c in cena["caixas"]}
    assert {"piso", "teto"} <= nomes and any(n.startswith("cama-") for n in nomes)
    teto = next(p for p in cena["prismas"] if p["nome"] == "teto")
    assert teto["oculto_em"] == ["superior"]
    cama = next(c for c in cena["caixas"] if c["nome"] == "cama-cabeceira")
    assert cama["extras"] == {"movel": "cama", "parte": "cabeceira"}

    antes = cama["centro"]
    v = cena["versao"]
    api.post("/projetos/casa/comodos/quarto/moveis/cama/mover", params={"versao": v},
             json={"centro": [1000, 1300]})  # fmt: skip
    depois = api.get("/projetos/casa/comodos/quarto/cena").json()
    assert depois["versao"] == v + 1
    nova = next(c for c in depois["caixas"] if c["nome"] == "cama-cabeceira")["centro"]
    assert nova != antes

    pav = api.get("/projetos/casa/pavimentos/terreo/cena").json()
    assert {"piso-quarto", "piso-banheiro"} <= {p["nome"] for p in pav["prismas"]}
    assert api.get("/projetos/casa/comodos/cozinha/cena").status_code == 404
    assert api.get("/projetos/casa/pavimentos/superior/cena").status_code == 404
