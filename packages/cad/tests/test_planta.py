"""Planta DXF/PDF sobre uma cópia congelada do projeto de exemplo (tests/dados/casa).

A cópia é congelada para que mudar medidas em ``projetos/`` não quebre o snapshot;
o snapshot só deve mudar quando o gerador mudar (e aí sobe o ``planta vN``).
Para regravar: ``PRUMO_ATUALIZAR_SNAPSHOTS=1 pytest packages/cad``.
"""

import json
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from ezdxf import bbox
from ezdxf.document import Drawing

from interiores_cad.estilo import AVISO_OBRA, NOMES_CAMADAS
from interiores_cad.folha import agrupar_estimadas, escolher_folha
from interiores_cad.gerar import Situacao, gerar_planta, pasta_saida
from interiores_cad.pdf import montar_figura
from interiores_cad.planta import desenhar_planta
from interiores_core.carregar import ProjetoCarregado, carregar
from interiores_core.medidas import Medida, Origem

AQUI = Path(__file__).parent
DADOS = AQUI / "dados" / "casa"
SNAPSHOTS = AQUI / "snapshots"
DATA = date(2026, 11, 17)


@pytest.fixture
def copia(tmp_path: Path) -> Path:
    destino = tmp_path / "projetos" / "casa"
    shutil.copytree(DADOS, destino)
    return destino


@pytest.fixture
def casa() -> ProjetoCarregado:
    return carregar(DADOS)


def _tudo_trena(pasta: Path) -> None:
    """Troca toda origem ``estimada`` por ``trena`` nos JSON da pasta."""

    def trocar(x: Any) -> Any:
        if isinstance(x, dict):
            if x.get("origem") == "estimada":
                x["origem"] = "trena"
            return {k: trocar(v) for k, v in x.items()}
        if isinstance(x, list):
            return [trocar(v) for v in x]
        return x

    for arq in pasta.rglob("*.json"):
        arq.write_text(json.dumps(trocar(json.loads(arq.read_text(encoding="utf-8")))), "utf-8")


def _textos(doc: Drawing, camada: str | None = None) -> list[str]:
    return [
        e.dxf.text
        for e in doc.modelspace().query("TEXT")
        if camada is None or e.dxf.layer == camada
    ]


def _cotas(doc: Drawing) -> list[int]:
    return sorted(round(d.get_measurement()) for d in doc.modelspace().query("DIMENSION"))


# ---------------------------------------------------------------- DXF


def test_camadas_e_unidades(casa: ProjetoCarregado) -> None:
    doc = desenhar_planta(casa, "terreo", "quarto", DATA).doc
    assert {layer.dxf.name for layer in doc.layers} >= NOMES_CAMADAS
    assert doc.header["$INSUNITS"] == 4  # milímetros
    usadas = {e.dxf.layer for e in doc.modelspace()}
    assert usadas <= NOMES_CAMADAS, "entidade fora das camadas padronizadas"
    assert {"PAREDE", "ABERTURA", "MOVEL", "ELETRICA", "COTA", "TEXTO", "AVISO"} <= usadas


def test_escala_real_1_unidade_1_mm(casa: ProjetoCarregado) -> None:
    """Paredes do quarto: eixos 0..3500 × 0..4750, externas de 150 → face a 75 do eixo."""
    doc = desenhar_planta(casa, "terreo", "quarto", DATA).doc
    caixa = bbox.extents(doc.modelspace().query('LWPOLYLINE[layer=="PAREDE"]'))
    assert (round(caixa.extmin.x), round(caixa.extmin.y)) == (-75, -75)
    assert (round(caixa.extmax.x), round(caixa.extmax.y)) == (3575, 4825)


def test_cotas_do_quarto(casa: ProjetoCarregado) -> None:
    """Medidas internas (3350 × 4600) e cadeias de janela e portas."""
    cotas = _cotas(desenhar_planta(casa, "terreo", "quarto", DATA).doc)
    assert {3350, 4600, 2080, 2100, 1270} <= set(cotas)  # faces internas
    assert cotas.count(925) == 2 and 1500 in cotas  # janela centrada na parede de 3350
    assert {245, 800, 225} <= set(cotas)  # porta do quarto
    assert {360, 700, 1040} <= set(cotas)  # porta do banheiro
    assert min(cotas) > 50, "cota espúria de encontro de paredes"


def test_frente_dos_moveis(casa: ProjetoCarregado) -> None:
    """Cabeceira da cama junto à parede leste; portas do guarda-roupa viradas para o quarto."""
    doc = desenhar_planta(casa, "terreo", "quarto", DATA).doc
    linhas = [
        ((round(e.dxf.start.x), round(e.dxf.start.y)), (round(e.dxf.end.x), round(e.dxf.end.y)))
        for e in doc.modelspace().query('LINE[layer=="MOVEL"]')
    ]
    # cama: centro x 2485, profundidade 1880 -> costas em x = 3425; cabeceira 60 para dentro
    assert any(a[0] == b[0] == 3365 for a, b in linhas)
    # guarda-roupa: centro x 350, profundidade 550 -> frente em x = 625; portas 40 para dentro
    assert any(a[0] == b[0] == 585 for a, b in linhas)


def test_instalacoes_eletrica_e_hidraulica(casa: ProjetoCarregado, copia: Path) -> None:
    quarto = desenhar_planta(casa, "terreo", "quarto", DATA).doc
    assert not quarto.modelspace().query('*[layer=="HIDRAULICA"]'), "pia do banheiro no quarto"
    assert {"T h300", "h1100", "luz h2600"} <= set(_textos(quarto, "ELETRICA"))
    assert any(t.startswith("AF água fria") for t in _textos(quarto, "TEXTO"))  # legenda

    banheiro = desenhar_planta(casa, "terreo", "banheiro", DATA).doc
    assert {"AF h600", "AQ h2100", "ES h0", "ralo h0"} <= set(_textos(banheiro, "HIDRAULICA"))
    # pia na parede p7 (eixo y = 2635, espessura 120): símbolo do lado do banheiro (y maior)
    pia = [
        c
        for c in banheiro.modelspace().query('CIRCLE[layer=="HIDRAULICA"]')
        if round(c.dxf.center.x) == 1000
    ]
    assert pia and all(c.dxf.center.y > 2635 + 60 for c in pia)

    arq = copia / "projeto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["pavimentos"][0]["instalacoes"].append(
        {
            "id": "gas-1",
            "forma": "ponto",
            "tipo": "gas",
            "posicao": [3000, 3000],
            "altura": {"valor": 400, "origem": "projeto"},
        }
    )
    d["pavimentos"][0]["instalacoes"].append(
        {
            "id": "cano",
            "forma": "trecho",
            "tipo": "agua_fria",
            "caminho": [[500, 75], [500, 2000]],
            "altura": {"valor": 600, "origem": "projeto"},
        }
    )
    arq.write_text(json.dumps(d), encoding="utf-8")
    doc = desenhar_planta(carregar(copia), "terreo", "quarto", DATA).doc
    textos = _textos(doc, "HIDRAULICA")
    assert textos == ["AF h600 (embutido)"]  # trecho desenhado; gás não
    assert not any("gás" in t for t in _textos(doc))


def test_checagens_na_planta(casa: ProjetoCarregado, copia: Path) -> None:
    """Áreas com problema na camada RESTRICAO, numeradas como no painel."""
    doc = desenhar_planta(casa, "terreo", "quarto", DATA).doc
    msp = doc.modelspace()
    assert len(msp.query('LWPOLYLINE[layer=="RESTRICAO"]')) == 3  # 2 laterais + passagem
    assert {"1", "2", "3"} <= set(_textos(doc, "RESTRICAO"))
    painel = [t for t in _textos(doc, "RESTRICAO") if t[:1].isdigit() and ". [" in t]
    assert any("[aviso] lateral de 'Cama de casal'" in t for t in painel)
    assert any(t.startswith("4. [info]") for t in painel)

    # sem problema: painel diz que está tudo certo e nada na camada RESTRICAO
    (copia / "regras.toml").write_text(
        "[geral]\npassagem_livre = 500\n[quarto]\nlateral_cama = 500\n", encoding="utf-8"
    )
    arq = copia / "comodos" / "quarto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["moveis"][1]["portas"] = "correr"
    arq.write_text(json.dumps(d), encoding="utf-8")
    doc = desenhar_planta(carregar(copia), "terreo", "quarto", DATA).doc
    assert not doc.modelspace().query('*[layer=="RESTRICAO"]')
    assert "Nenhum problema nas checagens de uso." in _textos(doc)


def test_simbolos_do_catalogo(copia: Path) -> None:
    """Cada tipo ganha seu símbolo; móvel elevado sai tracejado e com a elevação."""
    from interiores_core.catalogo import novo_movel

    arq = copia / "comodos" / "quarto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["moveis"] = [
        novo_movel("sofa", "sofa", (1300, 525), "3_lugares"),
        novo_movel("tv", "tv", (1300, 2535), "55pol", rotacao=180),
        novo_movel("guarda_roupa", "gr", (3150, 3200), "2_portas", rotacao=90),
        {**novo_movel("cama", "x", (2800, 1300)), "tipo": "rede"},  # fora do catálogo
    ]
    arq.write_text(json.dumps(d), encoding="utf-8")
    doc = desenhar_planta(carregar(copia), "terreo", "quarto", DATA).doc
    msp = doc.modelspace()
    tracejadas = [e for e in msp.query('*[layer=="MOVEL"]') if e.dxf.linetype == "TRACEJADO"]
    assert tracejadas and all(e.dxf.linetype == "TRACEJADO" for e in tracejadas)
    textos = _textos(doc, "MOVEL")
    assert '55" · 1230 × 80' in textos and "elev. 1000" in textos
    linhas = msp.query('LINE[layer=="MOVEL"]')

    # sofá 3 lugares (centro 1300,525; 2100 × 900 → x 250..2350, y 75..975):
    # encosto + 2 braços + 2 divisões de lugar
    def dentro_do_sofa(e: Any) -> bool:
        return all(250 <= p.x <= 2350 and 75 <= p.y <= 975 for p in (e.dxf.start, e.dxf.end))

    sofa_y = [e for e in linhas if dentro_do_sofa(e)]
    assert len(sofa_y) == 5
    # guarda-roupa de 2 portas de abrir (450): linha das portas + 1 divisão + cabideiro
    assert "TRACEJADO" in [lt.dxf.name for lt in doc.linetypes]


def test_carimbo(casa: ProjetoCarregado) -> None:
    desenho = desenhar_planta(casa, "terreo", "quarto", DATA)
    textos = _textos(desenho.doc)
    for esperado in (
        "casa (minha casa)",
        "Planta baixa — Quarto (suíte)",
        "Térreo",
        "cômodo quarto",
        "2026-11-17",
        casa.hash_curto,
    ):
        assert esperado in textos
    assert any(t.startswith("1:25 · A3") for t in textos)
    assert "cama: largura, profundidade, altura" in textos
    assert desenho.folha.escala in (20, 25, 50)


# ---------------------------------------------------------------- aviso de obra


def test_aviso_obra_com_estimada(casa: ProjetoCarregado, tmp_path: Path) -> None:
    desenho = desenhar_planta(casa, "terreo", "quarto", DATA)
    assert desenho.preliminar
    assert AVISO_OBRA in _textos(desenho.doc, "AVISO")
    fig = montar_figura(desenho)
    assert any(t.get_text() == AVISO_OBRA for t in fig.texts)

    r = gerar_planta(casa, tmp_path, "terreo", "quarto", data=DATA)
    if shutil.which("pdftotext"):
        texto = subprocess.run(
            ["pdftotext", "-raw", str(r.arquivos[1]), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        # marca d'água diagonal: o pdftotext devolve as letras sem espaços
        assert AVISO_OBRA.replace(" ", "") in texto.replace("\n", "").replace(" ", "")


def test_sem_estimada_sem_aviso(copia: Path) -> None:
    _tudo_trena(copia)
    desenho = desenhar_planta(carregar(copia), "terreo", "quarto", DATA)
    assert not desenho.preliminar
    assert not _textos(desenho.doc, "AVISO")
    assert "Nenhuma medida estimada." in _textos(desenho.doc)
    assert not montar_figura(desenho).texts


def test_aviso_vale_para_o_pavimento_se_um_comodo_tiver_estimada(copia: Path) -> None:
    _tudo_trena(copia)
    arq = copia / "comodos" / "quarto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["moveis"][0]["largura"]["origem"] = "estimada"
    arq.write_text(json.dumps(d), encoding="utf-8")
    c = carregar(copia)
    assert desenhar_planta(c, "terreo", None, DATA).preliminar
    assert desenhar_planta(c, "terreo", "quarto", DATA).preliminar
    assert not desenhar_planta(c, "terreo", "banheiro", DATA).preliminar  # cama não é dele


# ---------------------------------------------------------------- escopos


def test_planta_do_pavimento(casa: ProjetoCarregado) -> None:
    doc = desenhar_planta(casa, "terreo", None, DATA).doc
    textos = _textos(doc)
    assert "Quarto (suíte)" in textos and "Banheiro da suíte" in textos
    assert "pavimento terreo" in textos
    assert {2095, 1405, 3650, 2635, 2115, 4900} <= set(_cotas(doc))  # eixos + totais


def test_erros_de_escopo(casa: ProjetoCarregado, copia: Path) -> None:
    with pytest.raises(KeyError):
        desenhar_planta(casa, "superior")
    with pytest.raises(KeyError):
        desenhar_planta(casa, "terreo", "cozinha")
    arq = copia / "projeto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["pavimentos"][0]["comodos"][1]["paredes"].remove("p4")
    arq.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError, match="não fecha"):
        desenhar_planta(carregar(copia), "terreo", "banheiro")


# ---------------------------------------------------------------- saídas e cache


def test_pastas_de_saida(tmp_path: Path) -> None:
    assert pasta_saida(tmp_path, "casa", "terreo", "quarto") == tmp_path / "casa/terreo/quarto/base"
    assert pasta_saida(tmp_path, "casa", "terreo", None) == tmp_path / "casa/terreo/_geral"


def test_cache_por_hash(copia: Path, tmp_path: Path) -> None:
    saida = tmp_path / "out"
    r1 = gerar_planta(carregar(copia), saida, "terreo", "quarto", data=DATA)
    assert r1.situacao is Situacao.GERADO and all(a.exists() for a in r1.arquivos)
    meta = json.loads(r1.arquivos[2].read_text(encoding="utf-8"))
    assert meta["preliminar"] and meta["escala"] == 25 and meta["hash_entrada"]

    r2 = gerar_planta(carregar(copia), saida, "terreo", "quarto", data=DATA)
    assert r2.situacao is Situacao.INALTERADO and r2.escala == 25

    assert gerar_planta(carregar(copia), saida, "terreo", "quarto", forcar=True).situacao is (
        Situacao.GERADO
    )

    arq = copia / "comodos" / "quarto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["moveis"][0]["centro"] = [2400, 1325]
    arq.write_text(json.dumps(d), encoding="utf-8")
    assert gerar_planta(carregar(copia), saida, "terreo", "quarto").situacao is Situacao.GERADO

    outra = gerar_planta(carregar(copia), saida, "terreo", "quarto", variacao="clara")
    assert outra.arquivos[0].parent.name == "clara"
    assert r1.arquivos[0].exists(), "gerar outra variação não pode apagar a base"


def test_pdf_na_escala_da_folha(casa: ProjetoCarregado, tmp_path: Path) -> None:
    r = gerar_planta(casa, tmp_path, "terreo", "quarto", data=DATA)
    if not shutil.which("pdfinfo"):
        pytest.skip("pdfinfo (poppler) não instalado")
    info = subprocess.run(
        ["pdfinfo", str(r.arquivos[1])], capture_output=True, text=True, check=True
    ).stdout
    assert "1190.55 x 841.89 pts (A3)" in info


# ---------------------------------------------------------------- folha


def test_escolher_folha() -> None:
    assert escolher_folha((0, 0, 3650, 4900)).escala == 25
    assert escolher_folha((0, 0, 2000, 2000)).escala == 20
    grande = escolher_folha((0, 0, 18_000, 14_000))
    assert (grande.formato.nome, grande.escala) == ("A2", 50)
    with pytest.raises(ValueError, match="não cabe"):
        escolher_folha((0, 0, 100_000, 100_000))


def test_agrupar_estimadas() -> None:
    m = Medida(valor=1, origem=Origem.ESTIMADA)
    linhas = agrupar_estimadas(
        [
            ("pavimentos[terreo].pe_direito", m),
            ("pavimentos[terreo].aberturas[j1].largura", m),
            ("pavimentos[terreo].aberturas[j1].altura", m),
            ("comodos/quarto.moveis[cama].largura", m),
        ]
    )
    assert linhas == ["terreo: pe_direito", "j1: largura, altura", "cama: largura"]


# ---------------------------------------------------------------- snapshot


def _resumo(doc: Drawing) -> list[dict[str, Any]]:
    """Entidades do modelo, com geometria arredondada a 1 mm (comparação por entidades)."""

    def r(v: Any) -> list[int]:
        return [round(v[0]), round(v[1])]

    itens: list[dict[str, Any]] = []
    for e in doc.modelspace():
        tipo = e.dxftype()
        item: dict[str, Any] = {"tipo": tipo, "camada": e.dxf.layer}
        if tipo == "LINE":
            item["pontos"] = sorted([r(e.dxf.start), r(e.dxf.end)])
        elif tipo == "LWPOLYLINE":
            item["pontos"] = [r(p) for p in e.get_points("xy")]
        elif tipo in ("ARC", "CIRCLE"):
            item["centro"], item["raio"] = r(e.dxf.center), round(e.dxf.radius)
        elif tipo == "TEXT":
            item["texto"] = e.dxf.text
            item["ponto"] = r(e.dxf.align_point if e.dxf.hasattr("align_point") else e.dxf.insert)
        elif tipo == "DIMENSION":
            item["medida"] = round(e.get_measurement())
            item["pontos"] = [r(e.dxf.defpoint2), r(e.dxf.defpoint3)]
        elif tipo == "HATCH":
            item["contornos"] = len(e.paths)
        itens.append(item)
    return itens


@pytest.mark.parametrize("comodo", ["quarto", None], ids=["quarto", "pavimento"])
def test_snapshot(casa: ProjetoCarregado, comodo: str | None) -> None:
    atual = _resumo(desenhar_planta(casa, "terreo", comodo, DATA).doc)
    arquivo = SNAPSHOTS / f"planta_{comodo or 'pavimento'}.json"
    if os.environ.get("PRUMO_ATUALIZAR_SNAPSHOTS") or not arquivo.exists():
        arquivo.write_text(json.dumps(atual, ensure_ascii=False, indent=1) + "\n", "utf-8")
    esperado = json.loads(arquivo.read_text(encoding="utf-8"))
    assert atual == esperado, (
        "planta mudou; se foi de propósito, suba o 'planta vN' e regrave o snapshot"
    )


@pytest.mark.parametrize("lado", ["esquerda", "direita"])
def test_sofa_em_l_na_planta(copia: Path, lado: str) -> None:
    """Sofá de canto: contorno em L e o símbolo (encostos, braços, lugares) dentro dele."""
    from shapely import LineString

    from interiores_core import geometria
    from interiores_core.catalogo import novo_movel
    from interiores_core.modelo import Movel

    arq = copia / "comodos" / "quarto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    sofa = {**novo_movel("sofa", "sofa", (1600, 1200), "canto"), "lado_l": lado}
    d["moveis"] = [sofa]
    arq.write_text(json.dumps(d), encoding="utf-8")
    doc = desenhar_planta(carregar(copia), "terreo", "quarto", DATA).doc
    msp = doc.modelspace()
    contorno = geometria.poligono_movel(Movel.model_validate(sofa))
    polis = [e for e in msp.query('LWPOLYLINE[layer=="MOVEL"]') if len(e) == 6]
    assert polis, "contorno em L"
    linhas = [
        LineString([e.dxf.start.vec2, e.dxf.end.vec2]) for e in msp.query('LINE[layer=="MOVEL"]')
    ]
    dentro = [ln for ln in linhas if contorno.buffer(1).contains(ln)]
    # 2 encostos + 2 braços + 3 divisões nas costas (230 cm) + 1 no começo do braço do L
    assert len(dentro) == 8
    # encosto da lateral fica do lado do braço do L
    lateral = max(dentro, key=lambda ln: ln.length if ln.coords[0][0] == ln.coords[1][0] else 0)
    assert (lateral.coords[0][0] > 1600) == (lado == "esquerda")


def test_simbolos_do_escritorio(copia: Path) -> None:
    """Monitor, notebook e teclado (na mesa, tracejados) e gabinete ganham símbolo."""
    from interiores_core.catalogo import novo_movel

    arq = copia / "comodos" / "quarto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["moveis"] = [
        novo_movel("monitor", "monitor", (1000, 1000)),
        novo_movel("notebook", "notebook", (2000, 1000)),
        novo_movel("teclado", "teclado", (1000, 2000)),
        novo_movel("computador", "pc", (2000, 2000)),
    ]
    arq.write_text(json.dumps(d), encoding="utf-8")
    msp = desenhar_planta(carregar(copia), "terreo", "quarto", DATA).doc.modelspace()

    def perto(e: Any, cx: float, cy: float) -> bool:
        return all(abs(p.x - cx) < 400 and abs(p.y - cy) < 400 for p in (e.dxf.start, e.dxf.end))

    linhas = list(msp.query('LINE[layer=="MOVEL"]'))
    for cx, cy in ((1000, 1000), (2000, 1000), (1000, 2000), (2000, 2000)):
        assert [e for e in linhas if perto(e, cx, cy)], (cx, cy)
    tracejadas = [e for e in linhas if perto(e, 1000, 1000) and e.dxf.linetype == "TRACEJADO"]
    assert tracejadas  # monitor fica sobre a mesa (elevado)
    assert "Monitor" in _textos(desenhar_planta(carregar(copia), "terreo", "quarto", DATA).doc)
    # sobre a mesa: só o símbolo (o nome cairia em cima do nome da mesa)
    d["moveis"].append(novo_movel("escrivaninha", "mesa", (1000, 1000), "escritorio_160"))
    arq.write_text(json.dumps(d), encoding="utf-8")
    textos = _textos(desenhar_planta(carregar(copia), "terreo", "quarto", DATA).doc)
    assert "Monitor" not in textos and "Notebook" in textos
