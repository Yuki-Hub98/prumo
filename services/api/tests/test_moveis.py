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


def test_criar_do_zero_e_montar_por_dentro(api: TestClient) -> None:
    med = {k: {"valor": v, "origem": "projeto"} for k, v in
           (("largura", 1200), ("profundidade", 500), ("altura", 850))}  # fmt: skip
    pedido = {"tipo": "sob_medida", "nome": "Gabinete", "centro": [1500, 1500], "medidas": med}
    r = api.post(MOVEIS, params={"versao": 1}, json=pedido)
    assert r.status_code == 200, r.text
    geo = api.get("/projetos/casa/pavimentos/terreo/geometria").json()
    novo = next(m for m in geo["moveis"] if m["id"] == "sob-medida")
    assert (novo["planejavel"], novo["planejado"]) == (True, False)
    assert api.get(f"{MOVEIS}/sob-medida/planejado").status_code == 422  # ainda não montado

    r = api.post(f"{MOVEIS}/sob-medida/construcao/sugerir", params={"versao": 2})
    assert r.status_code == 200, r.text
    vista = api.get(f"{MOVEIS}/sob-medida/planejado").json()
    assert vista["largura"] == 1200 and vista["pecas"] > 0 and vista["chapas"]

    construcao = {
        "chapa": {"material": "MDF branco", "espessura": {"valor": 18, "origem": "projeto"}},
        "fundo": {"material": "HDF branco", "espessura": {"valor": 6, "origem": "projeto"}},
        "vaos": [{"espacos": [{"tipo": "gaveta"}, {"tipo": "gaveta"}, {"tipo": "gaveta"}]}],
    }
    r = api.put(
        f"{MOVEIS}/sob-medida/construcao", params={"versao": 3}, json={"construcao": construcao}
    )
    assert r.status_code == 200, r.text
    tipos = [x["tipo"] for x in api.get(f"{MOVEIS}/sob-medida/planejado").json()["retangulos"]]
    assert tipos.count("gaveta") == 3
    ruim = {
        **construcao,
        "vaos": [{"largura": {"valor": 9000, "origem": "projeto"}, "espacos": [{"tipo": "nicho"}]}],
    }
    assert (
        api.put(
            f"{MOVEIS}/sob-medida/construcao", params={"versao": 4}, json={"construcao": ruim}
        ).status_code
        == 422
    )
    r = api.put(f"{MOVEIS}/sob-medida/construcao", params={"versao": 4}, json={"construcao": None})
    assert r.status_code == 200
    assert api.post(f"{MOVEIS}/cama/construcao/sugerir", params={"versao": 5}).status_code == 422


def test_mudar_forma(api: TestClient) -> None:
    med = {k: {"valor": v, "origem": "projeto"} for k, v in
           (("largura", 1200), ("profundidade", 800), ("altura", 750))}  # fmt: skip
    pedido = {"tipo": "mesa", "centro": [1500, 1500], "medidas": med}
    assert api.post(MOVEIS, params={"versao": 1}, json=pedido).status_code == 200
    forma = {"forma": "arredondado", "raio": {"valor": 200, "origem": "projeto"}}
    r = api.patch(f"{MOVEIS}/mesa", params={"versao": 2}, json=forma)
    assert r.status_code == 200, r.text
    geo = api.get("/projetos/casa/pavimentos/terreo/geometria").json()
    mesa = next(m for m in geo["moveis"] if m["id"] == "mesa")
    assert mesa["forma"] == "arredondado" and len(mesa["contorno"]) > 4
    assert set(mesa["formas"]) == {"retangular", "arredondado", "redondo", "L"}
    ruim = {"raio": {"valor": 700, "origem": "projeto"}}
    assert api.patch(f"{MOVEIS}/mesa", params={"versao": 3}, json=ruim).status_code == 422
    assert (
        api.patch(f"{MOVEIS}/mesa", params={"versao": 3}, json={"forma": None}).status_code == 200
    )
    cama = next(m for m in geo["moveis"] if m["id"] == "cama")
    assert cama["formas"] == ["retangular"]


def test_sofa_de_canto_em_l(api: TestClient) -> None:
    pedido = {"tipo": "sofa", "modelo": "canto", "centro": [2000, 1500]}
    r = api.post(MOVEIS, params={"versao": 1}, json=pedido)
    assert r.status_code == 200, r.text
    geo = api.get("/projetos/casa/pavimentos/terreo/geometria").json()
    sofa = next(m for m in geo["moveis"] if m["tipo"] == "sofa")
    assert sofa["forma"] == "L" and len(sofa["contorno"]) == 6
    assert sofa["formas"] == ["retangular", "L"]
    r = api.patch(f"{MOVEIS}/{sofa['id']}", params={"versao": 2}, json={"lado_l": "direita"})
    assert r.status_code == 200, r.text


def test_catalogo_de_portas_e_janelas_e_tipo_gravado(api: TestClient, projetos: Path) -> None:
    cat = api.get("/catalogo/aberturas").json()
    assert {"giro-80", "camarao-80", "correr-120"} <= {p["id"] for p in cat["portas"]}
    basc = next(j for j in cat["janelas"] if j["id"] == "basculante-60x60")
    assert basc["abertura"] == "basculante" and cat["aberturas_janela"]["maxim_ar"] == "Maxim-ar"
    # muda o tipo de uma janela existente e salva: vai para o banco e para o JSON
    r = api.patch(
        "/projetos/casa/pavimentos/terreo/aberturas/basculante-banheiro",
        params={"versao": 1},
        json={"abertura": "basculante", "folhas": 1, "modelo": "basculante-60x60"},
    )
    assert r.status_code == 200, r.text
    api.post("/projetos/casa/rascunho/salvar", params={"versao": r.json()["versao"]})
    dados = json.loads((projetos / "casa" / "projeto.json").read_text())
    j = next(a for a in dados["pavimentos"][0]["aberturas"] if a["id"] == "basculante-banheiro")
    assert (j["abertura"], j["folhas"], j["modelo"]) == ("basculante", 1, "basculante-60x60")
    p = next(a for a in dados["pavimentos"][0]["aberturas"] if a["id"] == "porta-quarto")
    assert "estilo" not in p and "modelo" not in p  # campo vazio não aparece no JSON


def test_modelo_proprio_salvar_usar_e_apagar(api: TestClient) -> None:
    r = api.post(
        "/modelos-proprios",
        json={"projeto": "casa", "comodo": "quarto", "movel": "cama", "nome": "Cama do casal"},
    )
    assert r.status_code == 201, r.text
    modelo = r.json()
    assert modelo["codigo"] == "cama-do-casal" and modelo["tipo"] == "cama"
    assert modelo["estimadas"] > 0  # a cama da casa é chute: o modelo diz isso
    # mesmo nome de novo: código não repete
    r2 = api.post(
        "/modelos-proprios",
        json={"projeto": "casa", "comodo": "quarto", "movel": "cama", "nome": "Cama do casal"},
    )
    assert r2.json()["codigo"] == "cama-do-casal-2"
    assert [m["codigo"] for m in api.get("/modelos-proprios").json()] == [
        "cama-do-casal",
        "cama-do-casal-2",
    ]
    # usar: o móvel novo sai igual (tipo do pedido é ignorado)
    r = api.post(
        MOVEIS, params={"versao": 1},
        json={"tipo": "qualquer", "modelo_proprio": "cama-do-casal", "centro": [1500, 1500]},
    )  # fmt: skip
    assert r.status_code == 200, r.text
    assert r.json()["alteracoes"][0]["caminho"].startswith("comodos.quarto.moveis[cama")
    assert (
        api.post(
            MOVEIS,
            params={"versao": 2},
            json={"tipo": "x", "modelo_proprio": "nao-tem", "centro": [0, 0]},
        ).status_code
        == 404
    )
    assert api.delete("/modelos-proprios/cama-do-casal-2").status_code == 204
    assert api.delete("/modelos-proprios/cama-do-casal-2").status_code == 404
    assert (
        api.post(
            "/modelos-proprios",
            json={"projeto": "casa", "comodo": "quarto", "movel": "nao-tem", "nome": "x"},
        ).status_code
        == 404
    )


def test_redimensionar_pelo_lado(api: TestClient) -> None:
    r = api.post(
        f"{MOVEIS}/cama/redimensionar",
        params={"versao": 1},
        json={"lado": "direita", "tamanho": 1600},
    )
    assert r.status_code == 200, r.text
    caminhos = {a["caminho"] for a in r.json()["alteracoes"]}
    assert {"comodos.quarto.moveis[cama].largura", "comodos.quarto.moveis[cama].centro"} <= caminhos
    ruim = api.post(
        f"{MOVEIS}/cama/redimensionar",
        params={"versao": 2},
        json={"lado": "direita", "tamanho": 20},
    )
    assert ruim.status_code == 422


def test_bancada_em_l(api: TestClient) -> None:
    """Bancada do catálogo já vem montada; dá para trocar pernas e módulos (o que não fecha
    é recusado) e a tela recebe as vistas e os detalhes da planta."""
    pedido = {"tipo": "bancada", "modelo": "l_gaveteiro", "centro": [2000, 1500]}
    r = api.post(MOVEIS, params={"versao": 1}, json=pedido)
    assert r.status_code == 200, r.text
    geo = api.get("/projetos/casa/pavimentos/terreo/geometria").json()
    mesa = next(m for m in geo["moveis"] if m["tipo"] == "bancada")
    assert mesa["bancada"] and mesa["forma"] == "L" and mesa["formas"] == ["retangular", "L"]
    assert len(mesa["detalhes"]) == 5  # gaveteiro + 4 pernas
    vista = api.get(f"{MOVEIS}/{mesa['id']}/planejado").json()
    assert set(vista["vistas"]) == {"costas", "braco"}
    assert vista["modulos"]["gaveteiro"]["larguras_vaos"]  # vista do módulo, para montar
    assert {"tampo", "perna", "gaveta"} <= {x["tipo"] for x in vista["retangulos"]}
    projeto = api.get("/projetos/casa").json()
    dados = next(m for m in projeto["comodos"]["quarto"]["moveis"] if m["id"] == mesa["id"])
    bancada = {**dados["bancada"], "pernas": "painel"}
    r = api.put(f"{MOVEIS}/{mesa['id']}/bancada", params={"versao": 2}, json={"bancada": bancada})
    assert r.status_code == 200, r.text
    fora = {
        **bancada,
        "modulos": [{**bancada["modulos"][0], "distancia": {"valor": 1500, "origem": "projeto"}}],
    }
    r = api.put(f"{MOVEIS}/{mesa['id']}/bancada", params={"versao": 3}, json={"bancada": fora})
    assert r.status_code == 422 and "sai do tampo" in r.text


def test_baixar_desenho_e_lista_de_corte(api: TestClient) -> None:
    """Desenho (PDF/DXF) e lista de corte (.xlsx) do planejado e da bancada, pela API."""
    pedido = {"tipo": "bancada", "modelo": "reta_gaveteiro", "centro": [2000, 1500]}
    assert api.post(MOVEIS, params={"versao": 1}, json=pedido).status_code == 200
    geo = api.get("/projetos/casa/pavimentos/terreo/geometria").json()
    mesa = next(m for m in geo["moveis"] if m["tipo"] == "bancada")["id"]
    pdf = api.get(f"{MOVEIS}/{mesa}/planejado.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-disposition"].startswith("inline")
    dxf = api.get(f"{MOVEIS}/{mesa}/planejado.dxf")
    assert dxf.status_code == 200 and b"SECTION" in dxf.content[:200]
    xlsx = api.get(f"{MOVEIS}/{mesa}/planejado.xlsx")
    assert xlsx.status_code == 200 and xlsx.content.startswith(b"PK")
    assert f"planejado-{mesa}-corte.xlsx" in xlsx.headers["content-disposition"]
    vista = api.get(f"{MOVEIS}/{mesa}/planejado").json()
    assert any(p["nome"] == "Tampo" and p["fita"] == "2C2L" for p in vista["lista"])
    assert api.get(f"{MOVEIS}/{mesa}/planejado.png").status_code == 404
    assert api.get(f"{MOVEIS}/cama/planejado.pdf").status_code == 422  # não é planejado
