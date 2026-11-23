"""Bancada/mesa planejada: trechos, pernas, módulos, peças e checagens."""

from typing import Any

import pytest

from interiores_core import bancada, catalogo, geometria
from interiores_core.modelo import Movel
from interiores_core.partes import partes_do_movel


def nova(modelo: str = "reta", **extra: Any) -> Movel:
    dados = catalogo.novo_movel("bancada", "b", (2000, 2000), modelo)
    return Movel.model_validate({**dados, **extra})


def com(m: Movel, **campos: Any) -> Movel:
    dados = m.model_dump(mode="json", exclude_none=True)
    assert "bancada" in dados
    dados["bancada"].update(campos)
    return Movel.model_validate(dados)


def test_mesa_reta_so_pernas() -> None:
    c = bancada.calcular(nova())
    assert len(c.pernas) == 4 and not c.modulos
    assert [p.nome for p in c.pecas] == ["Tampo"]
    assert any("Perna metálica" in f.nome and f.quantidade == 4 for f in c.ferragens)
    assert partes_do_movel(nova()) == ("tampo", "pes")


def test_gaveteiro_tira_as_pernas_da_ponta() -> None:
    m = nova("reta_gaveteiro")
    c = bancada.calcular(m)
    assert len(c.pernas) == 2 and len(c.modulos) == 1
    # gaveteiro na ponta direita de quem olha (-x no referencial do móvel)
    assert all(p.x > 0 for p in c.pernas)
    assert any(p.nome.startswith("gaveteiro: Frente de gaveta") for p in c.pecas)
    assert {"gavetas", "puxadores"} <= set(partes_do_movel(m))


@pytest.mark.parametrize("lado", ["esquerda", "direita"])
def test_l_com_pernas_a_vista_no_canto(lado: str) -> None:
    m = nova("l_gaveteiro", lado_l=lado)
    m = Movel.model_validate(
        {
            **m.model_dump(mode="json", exclude_none=True),
            "bancada": bancada.bancada_sugerida(m),
        }
    )
    c = bancada.calcular(m)
    contorno = geometria.contorno_local(m)
    assert all(contorno.contains(geometria.Point(p.x, p.y)) for p in c.pernas)
    s = 1 if lado == "esquerda" else -1
    canto_de_fora = (s * 745, -695)  # canto de trás do lado do braço
    assert any(
        abs(p.x - canto_de_fora[0]) < 1 and abs(p.y - canto_de_fora[1]) < 1 for p in c.pernas
    )
    assert {p.trecho for p in c.pernas} == {"costas", "braco"}
    # o gaveteiro fica longe do braço do L
    assert c.modulos[0].centro_local[0] * s < 0
    assert set(c.vistas) == {"costas", "braco"}
    assert [p.nome for p in c.pecas[:2]] == ["Tampo (trecho das costas)", "Tampo (braço do L)"]


def test_vao_longo_ganha_perna_no_meio_e_painel_nas_pontas() -> None:
    m = nova(largura={"valor": 4000, "origem": "projeto"})
    c = bancada.calcular(m)
    assert len(c.pernas) == 6 and sum(1 for p in c.pernas if abs(p.x) < 1) == 2
    c = bancada.calcular(com(m, pernas="painel"))
    paineis = [p for p in c.pernas if p.painel]
    assert len(paineis) == 2 and len(c.pernas) == 4
    assert sum(p.quantidade for p in c.pecas if p.nome == "Pé painel") == 2


def test_modulo_que_nao_cabe_ou_se_sobrepoe() -> None:
    m = nova("reta_gaveteiro")
    mod = m.model_dump(mode="json", exclude_none=True)["bancada"]["modulos"][0]
    fora = {**mod, "distancia": {"valor": 1200, "origem": "projeto"}}
    with pytest.raises(bancada.BancadaInvalidaError, match="sai do tampo"):
        bancada.calcular(com(m, modulos=[fora]))
    outro = {**mod, "id": "outro", "distancia": {"valor": 900, "origem": "projeto"}}
    with pytest.raises(bancada.BancadaInvalidaError, match="se sobrepõem"):
        bancada.calcular(com(m, modulos=[mod, outro]))
    no_braco = {**mod, "trecho": "braco"}
    with pytest.raises(bancada.BancadaInvalidaError, match="tampo é reto"):
        bancada.calcular(com(m, modulos=[no_braco]))


def test_bancada_so_reta_ou_l_e_sem_construcao() -> None:
    with pytest.raises(ValueError, match="reta ou em L"):
        nova(forma="redondo")
    assert geometria.formas_possiveis(nova()) == ("retangular", "L")


def test_modulo_vira_movel_planejado_virado_para_dentro_do_l() -> None:
    m = nova("cozinha_l")
    dados = m.model_dump(mode="json", exclude_none=True)
    mod = bancada.modulo_pronto("arm", "armario", 30, 600, trecho="braco")
    dados["bancada"]["modulos"] = [mod]
    c = bancada.calcular(Movel.model_validate(dados))
    sint = c.modulos[0].movel
    assert sint.construcao is not None and sint.portas == "abrir"
    assert sint.altura.valor == m.altura.valor - 30  # sob o tampo de granito
    assert sint.rotacao == 90  # braço à esquerda (+x): frente para -x, o lado de dentro


def test_vista_do_braco_espelhada_com_braco_a_direita() -> None:
    """Na vista de frente, x é da esquerda de quem olha: com o braço à direita, a ponta do
    braço fica à direita (u = 0 do trecho vai para o fim da vista)."""
    m = nova("l_gaveteiro", lado_l="direita")
    t = bancada.trechos(m)[1]
    assert not bancada.esquerda_no_inicio(t)
    assert bancada.x_da_vista(t, 0, 100) == pytest.approx(t.comprimento - 100)


def test_modulo_montado_do_zero() -> None:
    """Módulo com construção livre (dois vãos: gavetas e nicho com prateleira) entra nas
    peças, nas partes e na vista dele para a tela."""
    from interiores_core.tela import planejado_para_tela

    m = nova("reta_gaveteiro")
    dados = m.model_dump(mode="json", exclude_none=True)
    mod = dados["bancada"]["modulos"][0]
    mod["largura"] = {"valor": 800, "origem": "projeto"}
    mod["distancia"] = {"valor": 670, "origem": "projeto"}
    mod["construcao"]["vaos"] = [
        {"espacos": [{"tipo": "gaveta"}, {"tipo": "gaveta"}]},
        {"espacos": [{"tipo": "nicho"}, {"tipo": "nicho"}], "porta": False},
    ]
    m = Movel.model_validate(dados)
    c = bancada.calcular(m)
    nomes = {p.nome for p in c.pecas}
    assert {"gaveteiro: Divisória", "gaveteiro: Prateleira"} <= nomes
    assert {"gavetas", "prateleiras"} <= set(partes_do_movel(m))
    tela = planejado_para_tela(m)
    assert len(tela.modulos["gaveteiro"].larguras_vaos) == 2
