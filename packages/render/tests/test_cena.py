"""Cena do render (sem Blender): geometria, materiais, câmeras e aviso."""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from shapely import Point, Polygon
from shapely.ops import unary_union

from interiores_core import geometria
from interiores_core.carregar import carregar
from interiores_render.cena import AVISO_OBRA, montar_cena

DADOS = Path(__file__).resolve().parents[2] / "core" / "tests" / "dados" / "casa"


@pytest.fixture
def copia(tmp_path: Path) -> Path:
    destino = tmp_path / "casa"
    shutil.copytree(DADOS, destino)
    return destino


@pytest.fixture
def cena() -> dict[str, Any]:
    return montar_cena(carregar(DADOS), "quarto")


def _nomes(itens: list[dict[str, Any]]) -> set[str]:
    return {i["nome"] for i in itens}


def test_arquitetura(cena: dict[str, Any]) -> None:
    nomes = _nomes(cena["prismas"])
    assert {
        "piso",
        "teto",
        "vidro-janela-quarto",
        "peitoril-janela-quarto",
        "verga-janela-quarto",
        "verga-porta-quarto",
        "verga-porta-banheiro",
    } <= nomes
    teto = next(p for p in cena["prismas"] if p["nome"] == "teto")
    assert teto["oculto_em"] == ["superior"] and teto["z0"] == 2600
    peitoril = next(p for p in cena["prismas"] if p["nome"] == "peitoril-janela-quarto")
    assert (peitoril["z0"], peitoril["z1"]) == (0, 1000)
    assert any(n.startswith("rodape-") for n in nomes)


def test_paredes_sem_sobreposicao(cena: dict[str, Any]) -> None:
    """Nas quinas as paredes não se sobrepõem (no render as faces coincidentes saem pretas)."""
    paredes = [Polygon(p["contorno"]) for p in cena["prismas"] if p["nome"].startswith("parede-")]
    assert sum(p.area for p in paredes) == pytest.approx(unary_union(paredes).area, rel=1e-6)


def test_moveis_e_porta(cena: dict[str, Any]) -> None:
    nomes = _nomes(cena["caixas"])
    assert {
        "cama-base",
        "cama-colchao",
        "cama-cabeceira",
        "cama-travesseiro0",
        "cama-travesseiro1",
        "guarda-roupa-corpo",
    } <= nomes
    assert "porta-porta-quarto" in nomes  # abre para o quarto: folha aberta aparece
    assert "porta-porta-banheiro" not in nomes  # abre para o banheiro: não
    folha = next(c for c in cena["caixas"] if c["nome"] == "porta-porta-quarto")
    assert folha["tamanho"] == [800, 35, 2100] and folha["centro"][2] == 1050


def test_cameras(cena: dict[str, Any]) -> None:
    carregado = carregar(DADOS)
    pav = carregado.projeto.pavimentos[0]
    quarto = pav.comodo("quarto")
    assert quarto is not None
    util = geometria.poligono_util(pav, quarto)
    perspectiva, superior = cena["cameras"]
    x, y, z = perspectiva["posicao"]
    assert util is not None and util.contains(Point(x, y)) and z == 1600
    for m in carregado.dados_comodos["quarto"].moveis:
        assert geometria.poligono_movel(m).distance(Point(x, y)) >= 150
    assert superior["tipo"] == "ortografica" and superior["posicao"][2] > 2600


def test_aviso_e_cores_padrao(cena: dict[str, Any], copia: Path) -> None:
    assert cena["aviso"].startswith(AVISO_OBRA)
    assert cena["materiais"]["parede"]["cor"] == "#EEEAE3"
    assert cena["materiais"]["vidro"]["vidro"] is True

    def trocar(x: Any) -> Any:
        if isinstance(x, dict):
            return {
                k: ("trena" if k == "origem" and v == "estimada" else trocar(v))
                for k, v in x.items()
            }
        return [trocar(v) for v in x] if isinstance(x, list) else x

    for arq in copia.rglob("*.json"):
        arq.write_text(json.dumps(trocar(json.loads(arq.read_text("utf-8")))), "utf-8")
    assert montar_cena(carregar(copia), "quarto")["aviso"] is None


def test_variacao(copia: Path) -> None:
    pasta = copia / "variacoes" / "quarto"
    pasta.mkdir(parents=True)
    (pasta / "escura.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "comodo": "quarto",
                "cores": {
                    "parede": "#7A8B94",
                    "moveis": {"guarda-roupa": "#2F3B45", "cama": "#3E2C20"},
                },
            }
        ),
        "utf-8",
    )
    cena = montar_cena(carregar(copia), "quarto", "escura")
    assert cena["variacao"] == "escura"
    mats = cena["materiais"]
    assert mats["parede"]["cor"] == "#7A8B94" and mats["piso"]["cor"] == "#A67C52"
    assert mats["movel-guarda-roupa"]["cor"] == "#2F3B45"  # por id
    assert mats["movel-cama"]["cor"] == "#3E2C20"  # por tipo
    with pytest.raises(KeyError, match="não existe"):
        montar_cena(carregar(copia), "quarto", "clara")


def test_parede_de_destaque(copia: Path) -> None:
    pasta = copia / "variacoes" / "quarto"
    pasta.mkdir(parents=True)
    var = {"schema_version": 1, "comodo": "quarto",
           "cores": {"parede": "#EEEEEE", "paredes": {"p2": "#C46B4F"}}}  # fmt: skip
    (pasta / "destaque.json").write_text(json.dumps(var), "utf-8")
    cena = montar_cena(carregar(copia), "quarto", "destaque")
    mats = cena["materiais"]
    assert mats["parede-p2"]["cor"] == "#C46B4F" and mats["parede"]["cor"] == "#EEEEEE"
    por_nome = {p["nome"]: p["material"] for p in cena["prismas"]}
    assert all(m == "parede-p2" for n, m in por_nome.items() if n.startswith("parede-p2-"))
    assert all(m == "parede" for n, m in por_nome.items() if n.startswith("parede-p1-"))


def test_erros() -> None:
    with pytest.raises(KeyError):
        montar_cena(carregar(DADOS), "cozinha")


def test_moveis_com_detalhe(cena: dict[str, Any]) -> None:
    nomes = _nomes(cena["caixas"])
    assert {"cama-edredom", "cama-dobra", "cama-cabeceira", "cama-rodape"} <= nomes
    assert any(n.startswith("guarda-roupa-puxador") for n in nomes)
    assert any(n.startswith("guarda-roupa-folha") for n in nomes)
    edredom = next(c for c in cena["caixas"] if c["nome"] == "cama-edredom")
    assert edredom["chanfro"] > 0 and edredom["material"] == "edredom"
    assert cena["materiais"]["metal"].get("metal") is True


def test_janela_porta_e_luz(cena: dict[str, Any]) -> None:
    nomes = _nomes(cena["caixas"])
    assert {
        "caixilho-janela-quarto-b",
        "caixilho-janela-quarto-m",
        "soleira-janela-quarto",
    } <= nomes
    assert {"batente-porta-quarto-e", "batente-porta-quarto-t"} <= nomes
    assert any(n.startswith("macaneta-porta-quarto") for n in nomes)
    luz = next(c for c in cena["caixas"] if c["nome"].startswith("luminaria-"))
    assert luz["oculto_em"] == ["superior"]
    assert cena["materiais"]["luminaria"]["emissao"] > 0
    sol = next(lz for lz in cena["luzes"] if lz["tipo"] == "sol")
    assert sol["direcao"][2] < 0 and sol["direcao"][1] > 0  # janela na p1 (y=0): sol entra para +y


def test_texturas(cena: dict[str, Any]) -> None:
    from interiores_core.modelo import Comodo
    from interiores_render.cena import textura_piso

    mats = cena["materiais"]
    assert mats["piso"]["textura"] == "madeira"  # quarto sem acabamento escrito
    assert mats["parede"]["textura"] == "pintura" and mats["edredom"]["textura"] == "tecido"
    assert mats["movel-cama"]["textura"] == "madeira"
    assert "textura" not in mats["movel-guarda-roupa"]  # MDF branco liso

    def comodo(tipo: str, piso: str | None = None) -> Comodo:
        return Comodo(id="x", nome="X", tipo=tipo, paredes=["a", "b", "c"], piso=piso)  # type: ignore[arg-type]

    assert textura_piso(comodo("banheiro")) == "porcelanato"
    assert textura_piso(comodo("quarto", "Porcelanato 60x60")) == "porcelanato"
    assert textura_piso(comodo("cozinha", "vinílico amadeirado")) == "madeira"
    banheiro = montar_cena(carregar(DADOS), "banheiro")["materiais"]["piso"]
    assert banheiro["textura"] == "porcelanato" and banheiro["cor"] == "#D6D1C8"
