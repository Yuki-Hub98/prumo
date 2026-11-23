"""Cena do render (sem Blender): geometria, materiais, câmeras e aviso."""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from shapely import Point, Polygon
from shapely.ops import unary_union

from interiores_core import catalogo, geometria
from interiores_core.carregar import carregar
from interiores_core.modelo import Movel
from interiores_core.partes import parte_da_peca, partes_do_movel
from interiores_render.cena import AVISO_OBRA, CORTE_SUPERIOR, montar_cena, montar_cena_pavimento

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
    for vista in [c["nome"] for c in cena["cameras"]]:  # em cada vista, o que aparece nela
        paredes = [
            Polygon(p["contorno"])
            for p in cena["prismas"]
            if p["nome"].startswith("parede-") and vista not in p.get("oculto_em", [])
        ]
        assert sum(p.area for p in paredes) == pytest.approx(unary_union(paredes).area, rel=1e-6)


def test_vista_de_cima_corta_as_paredes_da_frente(cena: dict[str, Any]) -> None:
    """De cima (de um canto), as paredes do lado da câmera viram tocos baixos só nessa vista;
    nas outras, a parede inteira e nada de toco."""
    cam = next(c for c in cena["cameras"] if c["nome"] == "superior")
    tocos = [p for p in cena["prismas"] if "-corte-" in p["nome"]]
    assert tocos and all(p["z1"] == CORTE_SUPERIOR for p in tocos)
    assert all("perspectiva" in p["oculto_em"] and "superior" not in p["oculto_em"] for p in tocos)
    cortadas = {p["nome"].split("-corte-")[0] for p in tocos}
    inteiras = [
        p for p in cena["prismas"]
        if p["nome"].startswith("parede-") and "-corte-" not in p["nome"]
    ]  # fmt: skip
    for p in inteiras:
        nome = p["nome"].rsplit("-", 1)[0]
        assert ("superior" in p.get("oculto_em", [])) == (nome in cortadas)
    # as cortadas estão do lado da câmera (x ou y menor que o centro, câmera no canto -x/-y)
    assert cam["posicao"][0] < cam["alvo"][0] and cam["posicao"][1] < cam["alvo"][1]
    assert len(cortadas) < len({p["nome"].rsplit("-", 1)[0] for p in inteiras})


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
        "caixilho-janela-quarto-m1",
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


# ---------------------------------------------------------------- pavimento inteiro


def test_pavimento_junta_os_comodos() -> None:
    c = carregar(DADOS)
    cena = montar_cena_pavimento(c, "terreo")
    pav = c.projeto.pavimentos[0]
    nomes = _nomes(cena["prismas"]) | _nomes(cena["caixas"])
    for comodo in pav.comodos:
        assert {f"piso-{comodo.id}", f"teto-{comodo.id}"} <= nomes
    # nomes únicos: no .glb cada objeto é achado pelo nome
    todos = [i["nome"] for i in cena["prismas"] + cena["caixas"]]
    assert len(todos) == len(set(todos))
    # cada móvel do quarto aparece uma vez, com o cômodo no nome
    assert any(n.startswith("cama") and n.endswith("-quarto") for n in nomes)
    assert cena["modelo"] == "terreo" and cena["comodo"] == "_geral"
    assert cena["aviso"] is not None and cena["aviso"].startswith(AVISO_OBRA)
    assert [cam["nome"] for cam in cena["cameras"]] == ["perspectiva", "superior"]


def test_pavimento_parede_compartilhada_sai_uma_vez() -> None:
    c = carregar(DADOS)
    pav = c.projeto.pavimentos[0]
    cena = montar_cena_pavimento(c, "terreo")
    paredes = [p for p in cena["prismas"] if p["nome"].startswith("parede-")]
    # sem volume sobreposto: a área somada é a da união
    pols = [Polygon(p["contorno"]) for p in paredes]
    assert sum(p.area for p in pols) == pytest.approx(unary_union(pols).area, rel=1e-6)
    ids = {p["nome"].split("-")[1] for p in paredes}
    assert ids == {p.id for p in pav.paredes if geometria.comprimento(p) > 0}


def test_pavimento_teto_some_nas_duas_vistas() -> None:
    cena = montar_cena_pavimento(carregar(DADOS), "terreo")
    tetos = [p for p in cena["prismas"] if p["nome"].startswith("teto-")]
    assert tetos and all(set(p["oculto_em"]) == {"perspectiva", "superior"} for p in tetos)
    luminarias = [cx for cx in cena["caixas"] if cx["nome"].startswith("luminaria-")]
    assert all("perspectiva" in cx["oculto_em"] for cx in luminarias)


def test_pavimento_vista_de_cima_cabe_no_quadro() -> None:
    c = carregar(DADOS)
    cena = montar_cena_pavimento(c, "terreo", largura=1600, altura=1000)
    sup = next(cam for cam in cena["cameras"] if cam["nome"] == "superior")
    pav = c.projeto.pavimentos[0]
    x0, y0, x1, y1 = unary_union([geometria.corpo(p) for p in pav.paredes]).bounds
    assert sup["escala"] >= x1 - x0  # a escala vale na largura do quadro
    assert sup["escala"] * 1000 / 1600 >= y1 - y0


def test_pavimento_inexistente_e_vistas_erradas() -> None:
    c = carregar(DADOS)
    with pytest.raises(KeyError, match="terreo"):
        montar_cena_pavimento(c, "superior")
    with pytest.raises(KeyError, match="porta"):
        montar_cena_pavimento(c, "terreo", vistas=("porta",))


def test_cor_por_parte_do_movel() -> None:
    """Portas e puxadores com cor própria; o corpo fica com a cor do móvel."""
    from interiores_core.modelo import Variacao

    c = carregar(DADOS)
    c.variacoes.setdefault("quarto", {})["partes"] = Variacao.model_validate(
        {"schema_version": 1, "comodo": "quarto", "nome": "Partes",
         "cores": {"moveis": {"guarda-roupa": "#111111"},
                   "pecas": {"guarda-roupa": {"portas": "#fafafa"},
                             "guarda_roupa": {"puxadores": "#c0a060"}}}}
    )  # fmt: skip
    cena = montar_cena(c, "quarto", "partes")
    gr = {cx["nome"]: cx for cx in cena["caixas"] if cx["nome"].startswith("guarda-roupa-")}
    mats = cena["materiais"]
    assert mats[gr["guarda-roupa-corpo"]["material"]]["cor"] == "#111111"
    porta = gr["guarda-roupa-folha0"]
    assert porta["extras"] == {"movel": "guarda-roupa", "parte": "portas"}
    assert porta["material"] == "movel-guarda-roupa@guarda-roupa@portas"
    assert mats[porta["material"]]["cor"] == "#fafafa"
    puxador = mats[gr["guarda-roupa-puxador0"]["material"]]
    assert puxador["cor"] == "#c0a060" and puxador["metal"]  # pelo tipo; segue metal
    assert all("extras" in cx for cx in gr.values())


def test_planejado_no_3d_igual_ao_desenho() -> None:
    """Vão 1 (o da esquerda de quem olha de frente) fica em +x com a frente para +y; nichos
    sem porta aparecem (fundo escuro), gavetas com frente e puxador."""
    from interiores_core.carregar import ProjetoCarregado
    from interiores_core.modelo import DadosComodo

    c = carregar(DADOS)
    dados = c.dados_comodos["quarto"].model_dump(mode="json", exclude_none=True)
    med = {"origem": "projeto"}
    dados["moveis"] = [{
        "id": "gab", "tipo": "sob_medida", "centro": [1500, 1500], "rotacao": 0,
        "largura": {"valor": 1200, **med}, "profundidade": {"valor": 500, **med},
        "altura": {"valor": 800, **med},
        "construcao": {
            "chapa": {"material": "MDF", "espessura": {"valor": 18, **med}},
            "fundo": {"material": "HDF", "espessura": {"valor": 6, **med}},
            "vaos": [{"espacos": [{"tipo": "gaveta"}, {"tipo": "gaveta"}]},
                     {"espacos": [{"tipo": "nicho"}, {"tipo": "nicho"}], "porta": False}],
        },
    }]  # fmt: skip
    novo = ProjetoCarregado(
        pasta=c.pasta, projeto=c.projeto,
        dados_comodos={**c.dados_comodos, "quarto": DadosComodo.model_validate(dados)},
        variacoes={},
    )  # fmt: skip
    cena = montar_cena(novo, "quarto")
    pecas = {cx["nome"]: cx for cx in cena["caixas"] if cx["nome"].startswith("gab-")}
    gavetas = [p for n, p in pecas.items() if n.startswith("gab-gaveta")]
    nichos = [p for n, p in pecas.items() if n.startswith("gab-nicho")]
    assert len(gavetas) == 2 and len(nichos) == 2
    assert all(g["centro"][0] > 1500 for g in gavetas)  # vão 1: esquerda de quem olha = +x
    assert all(n["centro"][0] < 1500 for n in nichos)
    assert any(n.startswith("gab-prateleira") for n in pecas)
    assert sum(n.startswith("gab-puxador") for n in pecas) == 2  # um por gaveta


def test_mesa_redonda_e_puff_em_l() -> None:
    """Forma vira sólido extrudado; a mesa ganha tampo na forma e pés por dentro dela."""
    from interiores_core.carregar import ProjetoCarregado
    from interiores_core.modelo import DadosComodo

    c = carregar(DADOS)
    med = {"origem": "projeto"}

    def m(id_: str, tipo: str, **extra: object) -> dict[str, object]:
        return {"id": id_, "tipo": tipo, "centro": [1500, 1500], "rotacao": 0,
                "largura": {"valor": 1000, **med}, "profundidade": {"valor": 1000, **med},
                "altura": {"valor": 750, **med}, **extra}  # fmt: skip

    dados = c.dados_comodos["quarto"].model_dump(mode="json", exclude_none=True)
    dados["moveis"] = [m("mesa", "mesa", forma="redondo"), m("puff", "banco", forma="L")]
    novo = ProjetoCarregado(
        pasta=c.pasta, projeto=c.projeto,
        dados_comodos={**c.dados_comodos, "quarto": DadosComodo.model_validate(dados)},
        variacoes={},
    )  # fmt: skip
    cena = montar_cena(novo, "quarto")
    prismas = {p["nome"]: p for p in cena["prismas"]}
    tampo = prismas["mesa-tampo"]
    assert len(tampo["contorno"]) > 30 and tampo["extras"] == {"movel": "mesa", "parte": "tampo"}
    assert (tampo["z0"], tampo["z1"]) == (720, 750)
    pes = [cx for cx in cena["caixas"] if cx["nome"].startswith("mesa-pe")]
    assert len(pes) == 4
    assert all(Polygon(tampo["contorno"]).contains(Point(cx["centro"][:2])) for cx in pes)
    puff = prismas["puff-corpo"]
    assert len(puff["contorno"]) == 6 and (puff["z0"], puff["z1"]) == (0, 750)


def test_tipos_de_porta_e_janela_no_3d(copia: Path) -> None:
    arq = copia / "projeto.json"
    dados = json.loads(arq.read_text(encoding="utf-8"))
    for a in dados["pavimentos"][0]["aberturas"]:
        if a["id"] == "porta-quarto":
            a.update(folha="camarao", estilo="vidro")
        elif a["id"] == "janela-quarto":
            a.update(abertura="basculante", folhas=1)
    arq.write_text(json.dumps(dados), encoding="utf-8")
    cena = montar_cena(carregar(copia), "quarto")
    nomes = _nomes(cena["caixas"])
    # camarão: duas folhas de meia largura, cada uma com o visor de vidro
    assert {"porta-porta-quarto-0", "porta-porta-quarto-1"} <= nomes
    assert {"porta-porta-quarto-0-vidro", "porta-porta-quarto-1-vidro"} <= nomes
    folha = next(c for c in cena["caixas"] if c["nome"] == "porta-porta-quarto-0")
    assert folha["tamanho"][0] < 400  # meia folha (porta de 800)
    # basculante: palhetas horizontais e puxador, sem montante
    assert {
        "caixilho-janela-quarto-p1",
        "caixilho-janela-quarto-p2",
        "caixilho-janela-quarto-px",
    } <= nomes
    assert not any(n.startswith("caixilho-janela-quarto-m") for n in nomes)


def test_acabamento_puxador_e_pes(copia: Path) -> None:
    arq = copia / "comodos" / "quarto.json"
    original = json.loads(arq.read_text(encoding="utf-8"))

    def cena_com(gr: dict[str, str], cama: dict[str, str]) -> dict[str, Any]:
        dados = json.loads(json.dumps(original))
        for m in dados["moveis"]:
            m.update(gr if m["id"] == "guarda-roupa" else cama if m["id"] == "cama" else {})
        arq.write_text(json.dumps(dados), encoding="utf-8")
        return montar_cena(carregar(copia), "quarto")

    def puxadores(cena: dict[str, Any]) -> list[dict[str, Any]]:
        return [c for c in cena["caixas"] if c["nome"].startswith("guarda-roupa-puxador")]

    cena = cena_com(
        {"acabamento": "madeira_escura", "puxador": "perfil"}, {"acabamento": "laca_brilho"}
    )
    mats = cena["materiais"]
    assert mats["movel-guarda-roupa"]["textura"] == "madeira"
    assert mats["movel-cama"]["rugosidade"] == 0.12 and "textura" not in mats["movel-cama"]
    assert all(p["material"] == "metal" for p in puxadores(cena))
    cava = puxadores(cena_com({"puxador": "cava"}, {}))
    assert cava and all(p["material"] == "sombra" and p["tamanho"][1] <= 2 for p in cava)


@pytest.mark.parametrize("item", catalogo._ITENS, ids=lambda i: i.tipo)
def test_todo_movel_do_catalogo_tem_as_partes_que_declara(item: Any) -> None:
    """Cada parte com cor própria (aba Cores) tem pelo menos uma peça no 3D, em todo modelo."""
    from interiores_render.cena import _Feitio

    class _CenaFalsa:
        def material(self, nome: str, cor: str, **extra: Any) -> str:
            return nome

    for mod in item.modelos:
        m = Movel.model_validate(catalogo.novo_movel(item.tipo, "x", (0, 0), mod.id))
        f = _Feitio(_CenaFalsa(), m, "mat")  # type: ignore[arg-type]
        construtor = {"portas": "portas", "prateleiras": "prateleiras"}.get(
            item.simbolo.value, item.simbolo.value
        )
        getattr(f, construtor, lambda: None)()
        if item.simbolo.value == "generico":
            continue
        achadas = {parte_da_peca(p.nome) for p in f.pecas}
        faltam = set(partes_do_movel(m)) - achadas
        assert not faltam, f"{item.tipo}/{mod.id}: sem peça para {faltam}"


@pytest.mark.parametrize("lado", ["esquerda", "direita"])
@pytest.mark.parametrize("pes", [None, "rodape"])
def test_sofa_em_l_peca_a_peca(lado: str, pes: str | None) -> None:
    """Sofá de canto: montado com encosto, braços, almofadas e pés, tudo dentro do L."""
    from interiores_render.cena import _Feitio

    class _CenaFalsa:
        def material(self, nome: str, cor: str, **extra: Any) -> str:
            return nome

    dados = catalogo.novo_movel("sofa", "s", (0, 0), "canto")
    dados["lado_l"] = lado
    if pes:
        dados["pes"] = pes
    m = Movel.model_validate(dados)
    f = _Feitio(_CenaFalsa(), m, "mat")  # type: ignore[arg-type]
    f.assento_l()
    contorno = geometria.contorno_local(m).buffer(1)
    for p in f.pecas:
        x0, y0, _, x1, y1, _ = p.caixa
        assert x0 < x1 and y0 < y1, p.nome
        assert contorno.contains(Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])), p.nome
    partes = {parte_da_peca(p.nome) for p in f.pecas}
    assert set(partes_do_movel(m)) <= partes
    # almofadas de assento nos dois trechos: a do braço do L fica do lado escolhido
    almofadas = [p.caixa for p in f.pecas if p.nome.startswith("almofada")]
    na_frente = [c for c in almofadas if c[1] > 0]
    assert na_frente and all((c[0] > 0) == (lado == "esquerda") for c in na_frente)


def test_sofa_em_l_na_cena() -> None:
    """Na cena o sofá em L sai em peças (caixas), não como bloco extrudado."""
    from interiores_core.carregar import ProjetoCarregado
    from interiores_core.modelo import DadosComodo

    c = carregar(DADOS)
    dados = c.dados_comodos["quarto"].model_dump(mode="json", exclude_none=True)
    dados["moveis"] = [catalogo.novo_movel("sofa", "sofa", (1600, 1500), "canto")]
    novo = ProjetoCarregado(
        pasta=c.pasta, projeto=c.projeto,
        dados_comodos={**c.dados_comodos, "quarto": DadosComodo.model_validate(dados)},
        variacoes={},
    )  # fmt: skip
    cena = montar_cena(novo, "quarto")
    assert not [p for p in cena["prismas"] if p["nome"].startswith("sofa-")]
    nomes = {cx["nome"] for cx in cena["caixas"] if cx["nome"].startswith("sofa-")}
    assert {"sofa-encosto", "sofa-encosto-l", "sofa-braco-e", "sofa-braco-d"} <= nomes
