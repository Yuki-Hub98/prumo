"""Móveis planejados: cálculo, construções sugeridas, checagens e edição."""

import shutil
from pathlib import Path
from typing import Any

import pytest
from apoio import CASA

from interiores_core import catalogo, editar, planejado
from interiores_core.carregar import carregar
from interiores_core.modelo import DadosComodo, Movel
from interiores_core.regras import checar


def M(v: int) -> dict[str, Any]:  # noqa: N802 - atalho de Medida nos testes
    return {"valor": v, "origem": "projeto"}


def guarda_roupa(portas: str | None = "correr", **extra: Any) -> dict[str, Any]:
    """1800 × 600 × 2300, MDF 18, rodapé 100: altura interna 2164, vãos de 873."""
    construcao = {
        "chapa": {"material": "MDF branco", "espessura": M(18)},
        "fundo": {"material": "HDF branco", "espessura": M(6)},
        "rodape": M(100),
        "vaos": [
            {
                "espacos": [
                    {"tipo": "gaveta", "altura": M(200)},
                    {"tipo": "gaveta", "altura": M(200)},
                    {"tipo": "cabideiro"},
                    {"tipo": "nicho", "altura": M(400)},
                ]
            },
            {"espacos": [{"tipo": "nicho"}] * 4 + [{"tipo": "nicho", "altura": M(400)}]},
        ],
    }
    construcao.update(extra)
    d: dict[str, Any] = {
        "id": "gr",
        "tipo": "guarda_roupa",
        "centro": [0, 0],
        "largura": M(1800),
        "profundidade": M(600),
        "altura": M(2300),
        "construcao": construcao,
    }
    if portas:
        d["portas"] = portas
    return d


def pecas(calc: planejado.Planejado) -> dict[str, tuple[float, float, int]]:
    return {p.nome: (p.comprimento, p.largura, p.quantidade) for p in calc.pecas}


def test_caixa_vaos_e_alturas() -> None:
    calc = planejado.calcular(Movel.model_validate(guarda_roupa()))
    assert [round(w) for w in calc.larguras_vaos] == [873, 873]
    # vão 1: 2 prateleiras (gaveta-cabideiro e cabideiro-nicho) → 2164 - 36 - 800 = 1328
    assert [round(h) for h in calc.alturas[0]] == [200, 200, 1328, 400]
    assert [round(h) for h in calc.alturas[1]] == [423, 423, 423, 423, 400]
    p = pecas(calc)
    assert p["Lateral"] == (2300, 600, 2)
    assert p["Base"] == p["Tampo"] == (1764, 600, 1)
    assert p["Divisória"] == (2164, 600, 1)
    assert p["Fundo"] == (1800, 2200, 1)
    assert p["Prateleira"] == (873, 520, 6)  # recuada 80 pelo trilho da porta de correr


def test_gavetas_e_portas_de_correr() -> None:
    calc = planejado.calcular(Movel.model_validate(guarda_roupa()))
    p = pecas(calc)
    assert p["Frente de gaveta"] == (869, 196, 2)
    assert p["Lateral de gaveta"] == (450, 150, 4)  # corrediça de 450 (600 - 80 - 50 → 470)
    assert p["Fundo de gaveta"] == (848, 450, 2)  # 873 - 2 × 12,5
    assert p["Porta de correr"] == (2124, 907, 2)  # (1764 / 2) + 25 de transpasse
    ferr = {f.nome: f.quantidade for f in calc.ferragens}
    assert ferr["Corrediça telescópica 450 mm (par)"] == 2
    assert ferr["Tubo de cabideiro oblongo 871 mm"] == 1
    assert ferr["Roldana de porta de correr"] == 4
    assert ferr["Pino/suporte de prateleira"] == 24
    assert "Sapata niveladora" not in ferr  # tem rodapé


def test_portas_de_abrir() -> None:
    d = guarda_roupa("abrir")
    d["construcao"]["vaos"][1]["porta"] = False
    calc = planejado.calcular(Movel.model_validate(d))
    p = pecas(calc)
    # vão 1 de 0 a 900 (lateral + vão + meia divisória) → 2 folhas de 447
    assert p["Porta de abrir"] == (2197, 447, 2)
    assert p["Prateleira"][1] == 580  # recuo de 20 sem trilho
    ferr = {f.nome: f.quantidade for f in calc.ferragens}
    assert ferr["Dobradiça 35 mm com amortecedor"] == 10  # 5 por folha acima de 2100
    assert ferr["Puxador de porta"] == 2
    portas = [r for r in calc.layout if r.tipo == "porta"]
    assert len(portas) == 2 and all(r.vao == 0 for r in portas)


def test_fita_area_e_chapas() -> None:
    calc = planejado.calcular(Movel.model_validate(guarda_roupa()))
    lateral = next(p for p in calc.pecas if p.nome == "Lateral")
    assert lateral.fita_metros == pytest.approx(4.6) and lateral.area_m2 == pytest.approx(2.76)
    porta = next(p for p in calc.pecas if p.nome == "Porta de correr")
    assert porta.fita_metros == pytest.approx(2 * (2 * 2124 + 2 * 907) / 1000)
    chapas = {c.material: c for c in calc.chapas}
    assert chapas["MDF branco"].chapas == 4 and chapas["HDF branco"].chapas == 2
    assert chapas["HDF branco"].fita_metros == 0


def test_construcao_que_nao_cabe() -> None:
    d = guarda_roupa()
    d["construcao"]["vaos"][0]["largura"] = M(2000)
    with pytest.raises(planejado.ConstrucaoInvalidaError, match="largura dos vãos"):
        planejado.calcular(Movel.model_validate(d))
    d = guarda_roupa()
    d["construcao"]["vaos"][0]["espacos"][2]["altura"] = M(2000)
    with pytest.raises(planejado.ConstrucaoInvalidaError, match="vão 1"):
        planejado.calcular(Movel.model_validate(d))
    d = guarda_roupa(rodape=M(2300))
    with pytest.raises(planejado.ConstrucaoInvalidaError, match="espaço interno"):
        planejado.calcular(Movel.model_validate(d))
    d = guarda_roupa()
    d["profundidade"] = M(250)
    with pytest.raises(planejado.ConstrucaoInvalidaError, match="corrediça"):
        planejado.calcular(Movel.model_validate(d))
    with pytest.raises(ValueError, match="não tem construção"):
        planejado.calcular(Movel.model_validate({**guarda_roupa(), "construcao": None}))


@pytest.mark.parametrize("tipo", planejado.TIPOS_PLANEJAVEIS)
def test_sugestoes_cabem_em_todos_os_modelos(tipo: str) -> None:
    for mod in catalogo.CATALOGO[tipo].modelos:
        m = Movel.model_validate(catalogo.novo_movel(tipo, "x", (0, 0), mod.id))
        sugerida = planejado.construcao_sugerida(m)
        calc = planejado.calcular(Movel.model_validate({**m.model_dump(), "construcao": sugerida}))
        assert calc.pecas and all(p.comprimento > 0 and p.largura > 0 for p in calc.pecas)


def test_sugestao_e_estimada_e_aereo_sem_rodape() -> None:
    m = Movel.model_validate(catalogo.novo_movel("armario", "a", (0, 0), "aereo"))
    sugerida = planejado.construcao_sugerida(m)
    assert "rodape" not in sugerida
    assert sugerida["chapa"]["espessura"]["origem"] == "estimada"  # type: ignore[index]
    with pytest.raises(KeyError, match="não é planejável"):
        planejado.construcao_sugerida(Movel.model_validate(catalogo.novo_movel("tv", "t", (0, 0))))


# ---------------------------------------------------------------- checagens


def checar_gr(d: dict[str, Any], regras: dict[str, object] | None = None) -> list[str]:
    d = {**d, "centro": [2800, 3600], "rotacao": 90}  # num canto do quarto, sem incomodar
    dados = {
        "quarto": DadosComodo.model_validate(
            {"schema_version": 1, "comodo": "quarto", "moveis": [d]}
        )
    }
    return sorted(
        p.codigo
        for p in checar(carregar(CASA).projeto, dados, regras)
        if p.elemento == "gr"
        and p.codigo not in ("passagem_livre", "movel_fora_do_comodo", "moveis_sobrepostos")
    )


def test_checagens_do_planejado() -> None:
    assert checar_gr(guarda_roupa()) == []
    assert checar_gr(guarda_roupa(), {"geral": {"prateleira_vao_max": 800}}) == [
        "prateleira_longa",
        "prateleira_longa",
    ]
    d = guarda_roupa()
    d["construcao"]["vaos"][0]["espacos"][3]["altura"] = M(800)  # cabideiro fica com 928
    assert checar_gr(d) == ["cabideiro_baixo"]
    d = guarda_roupa()
    d["profundidade"] = M(450)
    assert checar_gr(d) == ["cabideiro_raso"]
    d = guarda_roupa()
    d["construcao"]["vaos"][0]["largura"] = M(250)
    assert "gaveta_estreita" in checar_gr(d)
    d = guarda_roupa()
    d["construcao"]["vaos"][0]["largura"] = M(2000)
    assert checar_gr(d) == ["construcao_invalida"]


# ---------------------------------------------------------------- edição


def test_definir_construcao(tmp_path: Path) -> None:
    pasta = tmp_path / "casa"
    shutil.copytree(CASA, pasta)
    m = carregar(pasta).dados_comodos["quarto"].moveis[1]
    sugerida = planejado.construcao_sugerida(m)
    editar.definir_construcao(pasta, "quarto", m.id, sugerida)
    assert carregar(pasta).dados_comodos["quarto"].moveis[1].construcao is not None
    with pytest.raises(ValueError, match="já tem construção"):
        editar.definir_construcao(pasta, "quarto", m.id, sugerida)
    editar.definir_construcao(pasta, "quarto", m.id, sugerida, substituir=True)
    editar.definir_construcao(pasta, "quarto", m.id, None)
    assert carregar(pasta).dados_comodos["quarto"].moveis[1].construcao is None
