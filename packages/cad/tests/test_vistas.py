"""Cortes e elevações do cômodo."""

import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from ezdxf.document import Drawing

from interiores_cad.estilo import NOMES_CAMADAS
from interiores_cad.gerar import Situacao, gerar_vistas
from interiores_cad.planta import desenhar_planta
from interiores_cad.vistas import Vista, desenhar_vistas
from interiores_core.carregar import ProjetoCarregado, carregar

DADOS = Path(__file__).parent / "dados" / "casa"
DATA = date(2026, 11, 17)


@pytest.fixture(scope="module")
def casa() -> ProjetoCarregado:
    return carregar(DADOS)


@pytest.fixture(scope="module")
def quarto(casa: ProjetoCarregado) -> dict[str, tuple[Vista, Drawing]]:
    return {v.nome: (v, d.doc) for v, d in desenhar_vistas(casa, "terreo", "quarto", DATA)}


def _textos(doc: Drawing, camada: str | None = None) -> list[str]:
    return [
        e.dxf.text
        for e in doc.modelspace().query("TEXT")
        if camada is None or e.dxf.layer == camada
    ]


def _cotas(doc: Drawing) -> set[int]:
    return {round(d.get_measurement()) for d in doc.modelspace().query("DIMENSION")}


def test_quais_vistas(quarto: dict[str, tuple[Vista, Drawing]]) -> None:
    """Quarto em L: cortes AA/BB e uma elevação por face (6 faces)."""
    assert set(quarto) == {"corte-aa", "corte-bb"} | {
        f"elevacao-{p}" for p in ("p1", "p2", "p3", "p6", "p7", "p8")
    }
    for _, doc in quarto.values():
        assert {e.dxf.layer for e in doc.modelspace()} <= NOMES_CAMADAS


def test_orientacao_da_elevacao(quarto: dict[str, tuple[Vista, Drawing]]) -> None:
    """Parede da janela (p1, embaixo na planta): olhando para baixo, a direita é o oeste."""
    v, _ = quarto["elevacao-p1"]
    assert v.olhar == (0.0, -1.0) and v.elevacao
    assert v.s(3425, 75) < v.s(75, 75)  # leste à esquerda, oeste à direita
    assert v.t(1000, 75) == pytest.approx(700, abs=1)  # face a 700 do plano


def test_elevacao_da_janela(quarto: dict[str, tuple[Vista, Drawing]]) -> None:
    _, doc = quarto["elevacao-p1"]
    assert {3350, 2600, 1500, 1000, 1200} <= _cotas(doc)  # face, pé-direito, janela
    textos = _textos(doc)
    assert "janela-quarto" in textos and "Cama de casal" in textos and "Guarda-roupa" in textos
    assert "ELEVAÇÃO DA PAREDE P1 — Quarto (suíte)" in textos


def test_elevacao_com_tomadas_e_porta_cortada(quarto: dict[str, tuple[Vista, Drawing]]) -> None:
    _, doc = quarto["elevacao-p2"]
    assert _textos(doc, "ELETRICA").count("T h300") == 2
    assert 4600 in _cotas(doc)
    # na ponta, a parede de cima é cortada na altura da porta do quarto: hachura só acima
    hachuras = [
        h
        for h in doc.modelspace().query('LWPOLYLINE[layer=="PAREDE"]')
        if min(p[1] for p in h.get_points("xy")) == 2100
    ]
    assert hachuras


def test_elevacao_no_canto_do_l(quarto: dict[str, tuple[Vista, Drawing]]) -> None:
    """Parede do banheiro vista do quarto: só a face (2080), sem o ponto da pia."""
    _, doc = quarto["elevacao-p7"]
    assert 2080 in _cotas(doc) and 2281 not in _cotas(doc)
    assert not _textos(doc, "HIDRAULICA")  # a pia é do lado do banheiro


def test_cortes(quarto: dict[str, tuple[Vista, Drawing]]) -> None:
    _, aa = quarto["corte-aa"]
    msp = aa.modelspace()
    assert len(msp.query('HATCH[layer=="PAREDE"]')) == 2  # paredes oeste e leste cortadas
    assert len(msp.query('HATCH[layer=="MOVEL"]')) == 2  # guarda-roupa e cama cortados
    assert {3350, 2600, 2100, 800} <= _cotas(aa)  # largura, pé-direito, porta ao fundo
    _, bb = quarto["corte-bb"]
    janela = [
        e
        for e in bb.modelspace().query('LINE[layer=="ABERTURA"]')
        if {round(e.dxf.start.y), round(e.dxf.end.y)} == {1000, 2200}
    ]
    assert len(janela) == 3  # corte passa pela janela: caixilho e vidro
    assert len(bb.modelspace().query('HATCH[layer=="PAREDE"]')) == 3  # p7 + p1 em 2 trechos


def test_banheiro_mostra_agua(casa: ProjetoCarregado) -> None:
    vistas = {v.nome: d.doc for v, d in desenhar_vistas(casa, "terreo", "banheiro", DATA)}
    assert "AF h600" in _textos(vistas["elevacao-p7"], "HIDRAULICA")
    assert "AQ h2100" in _textos(vistas["elevacao-p5"], "HIDRAULICA")


def test_movel_elevado_na_elevacao(tmp_path: Path) -> None:
    from interiores_core.catalogo import novo_movel

    shutil.copytree(DADOS, tmp_path / "casa")
    arq = tmp_path / "casa" / "comodos" / "quarto.json"
    d = json.loads(arq.read_text(encoding="utf-8"))
    d["moveis"].append(novo_movel("tv", "tv", (1000, 2535), "50pol", rotacao=180))
    arq.write_text(json.dumps(d), encoding="utf-8")
    vistas = {
        v.nome: d.doc
        for v, d in desenhar_vistas(carregar(tmp_path / "casa"), "terreo", "quarto", DATA)
    }
    assert "h1650 (elev. 1000)" in _textos(vistas["elevacao-p7"], "MOVEL")


def test_planta_mostra_paredes_e_cortes(casa: ProjetoCarregado) -> None:
    textos = _textos(desenhar_planta(casa, "terreo", "quarto", DATA).doc, "TEXTO")
    assert {"p1", "p2", "p3", "p6", "p7", "p8"} <= set(textos)
    assert textos.count("A") == 2 and textos.count("B") == 2


def test_erros(casa: ProjetoCarregado) -> None:
    with pytest.raises(KeyError):
        desenhar_vistas(casa, "superior", "quarto")
    with pytest.raises(KeyError):
        desenhar_vistas(casa, "terreo", "cozinha")


def test_gerar_vistas_com_cache(casa: ProjetoCarregado, tmp_path: Path) -> None:
    situacao, arquivos = gerar_vistas(casa, tmp_path, "terreo", "quarto", data=DATA)
    assert situacao is Situacao.GERADO and len(arquivos) == 16
    assert all(a.exists() for a in arquivos)
    assert (tmp_path / "casa/terreo/quarto/base/elevacao-p1.pdf") in arquivos
    situacao, de_novo = gerar_vistas(casa, tmp_path, "terreo", "quarto", data=DATA)
    assert situacao is Situacao.INALTERADO and de_novo == arquivos
    (tmp_path / "casa/terreo/quarto/base/corte-aa.pdf").unlink()  # arquivo some: regera
    assert gerar_vistas(casa, tmp_path, "terreo", "quarto", data=DATA)[0] is Situacao.GERADO
