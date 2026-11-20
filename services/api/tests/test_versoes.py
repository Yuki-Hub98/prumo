"""Desfazer, refazer e voltar para uma versão; rascunho (mudanças ainda não salvas)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

P = "/projetos/casa"
QUARTO = f"{P}/pavimentos/terreo/comodos/quarto"
MOVEIS = f"{P}/comodos/quarto/moveis"


def _moveis(projetos: Path) -> list[str]:
    arq = projetos / "casa" / "comodos" / "quarto.json"
    return [m["id"] for m in json.loads(arq.read_text())["moveis"]] if arq.exists() else []


def _centro(api: TestClient) -> list[int]:
    moveis = api.get(P).json()["comodos"]["quarto"]["moveis"]
    return next(m["centro"] for m in moveis if m["id"] == "cama")


def _salvar(api: TestClient, versao: int) -> None:
    r = api.post(f"{P}/rascunho/salvar", params={"versao": versao})
    assert r.status_code == 200, r.text


def test_rascunho_desfaz_passo_a_passo(api: TestClient, projetos: Path) -> None:
    inicio = _centro(api)
    for v, x in ((1, 1000), (2, 1100), (3, 1200)):  # testar três posições
        r = api.post(f"{MOVEIS}/cama/mover", params={"versao": v}, json={"centro": [x, 1300]})
        assert r.json()["versao"] == v + 1
    v = api.get(f"{P}/versoes").json()
    assert v["rascunho"] == {"desde": 1, "passos": 3, "refazer": False}
    assert (v["atual"], v["desfazer"], v["refazer"]) == (4, 3, None)
    arq = json.loads((projetos / "casa" / "comodos" / "quarto.json").read_text())
    assert next(m for m in arq["moveis"] if m["id"] == "cama")["centro"] == inicio  # JSON intacto

    # desfazer volta um passo de verdade (a versão desce)
    assert api.post(f"{P}/desfazer", params={"versao": 4}).json()["versao"] == 3
    assert _centro(api) == [1100, 1300]
    assert api.post(f"{P}/desfazer", params={"versao": 3}).json()["versao"] == 2
    v = api.get(f"{P}/versoes").json()
    assert v["rascunho"] == {"desde": 1, "passos": 1, "refazer": True}
    assert [x["versao"] for x in v["versoes"]] == [2, 1]  # os desfeitos não aparecem
    assert api.post(f"{P}/refazer", params={"versao": 2}).json()["versao"] == 3
    assert _centro(api) == [1100, 1300]

    # edição nova apaga o que dava para refazer
    api.post(f"{MOVEIS}/cama/mover", params={"versao": 3}, json={"centro": [1500, 1300]})
    v = api.get(f"{P}/versoes").json()
    assert (v["atual"], v["rascunho"]["refazer"], v["refazer"]) == (4, False, None)

    # voltar para uma versão do histórico pede para salvar antes
    assert api.post(f"{P}/versoes/1/restaurar", params={"versao": 4}).status_code == 422

    _salvar(api, 4)
    arq = json.loads((projetos / "casa" / "comodos" / "quarto.json").read_text())
    assert next(m for m in arq["moveis"] if m["id"] == "cama")["centro"] == [1500, 1300]
    v = api.get(f"{P}/versoes").json()
    assert v["rascunho"] is None
    assert [x["versao"] for x in v["versoes"]] == [4, 3, 2, 1]  # uma versão por mudança
    # salvo: o desfazer volta a gravar versão nova
    assert api.post(f"{P}/desfazer", params={"versao": 4}).json()["versao"] == 5
    assert _centro(api) == [1100, 1300]


def test_descartar_volta_ao_salvo(api: TestClient) -> None:
    inicio = _centro(api)
    api.post(f"{MOVEIS}/cama/mover", params={"versao": 1}, json={"centro": [900, 900]})
    api.post(f"{MOVEIS}/cama/mover", params={"versao": 2}, json={"rotacao": 180})
    r = api.post(f"{P}/rascunho/descartar", params={"versao": 3})
    assert r.status_code == 200, r.text
    assert r.json()["versao"] == 1
    assert _centro(api) == inicio
    v = api.get(f"{P}/versoes").json()
    assert (v["atual"], v["rascunho"], v["refazer"]) == (1, None, None)
    assert api.post(f"{P}/rascunho/descartar", params={"versao": 1}).status_code == 422


def test_desfazer_o_ultimo_passo_fecha_e_segue_no_historico(api: TestClient) -> None:
    api.post(f"{MOVEIS}/cama/mover", params={"versao": 1}, json={"centro": [900, 900]})
    _salvar(api, 2)
    api.post(f"{MOVEIS}/cama/mover", params={"versao": 2}, json={"centro": [800, 800]})
    assert api.post(f"{P}/desfazer", params={"versao": 3}).json()["versao"] == 2  # o passo
    v = api.get(f"{P}/versoes").json()
    assert v["rascunho"]["passos"] == 0 and v["desfazer"] == 1
    # sem passos: desfazer fecha o rascunho e desfaz a versão salva (versão nova)
    assert api.post(f"{P}/desfazer", params={"versao": 2}).json()["versao"] == 3
    v = api.get(f"{P}/versoes").json()
    assert v["rascunho"] is None and v["versoes"][0]["tipo"] == "desfazer"


def test_apagar_quarto_desfazer_e_refazer(api: TestClient, projetos: Path) -> None:
    antes = _moveis(projetos)
    assert antes
    inicio = api.get(f"{P}/versoes").json()
    assert (inicio["atual"], inicio["desfazer"], inicio["refazer"]) == (1, None, None)
    assert api.post(f"{P}/desfazer", params={"versao": 1}).status_code == 422  # nada ainda

    assert api.delete(QUARTO, params={"versao": 1}).json()["versao"] == 2
    _salvar(api, 2)
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
    _salvar(api, 3)
    r = api.post(f"{P}/versoes/1/restaurar", params={"versao": 3})
    assert r.status_code == 200, r.text
    assert r.json()["versao"] == 4 and _moveis(projetos) == antes
    v = api.get(f"{P}/versoes").json()
    assert (v["versoes"][0]["tipo"], v["desfazer"], v["refazer"]) == ("reverter", 3, None)
    assert api.post(f"{P}/versoes/4/restaurar", params={"versao": 4}).status_code == 422
    assert api.post(f"{P}/versoes/99/restaurar", params={"versao": 4}).status_code == 404
    assert api.post(f"{P}/desfazer", params={"versao": 4}).json()["versao"] == 5
    assert _moveis(projetos) == []  # desfazer o "voltar": quarto apagado de novo
