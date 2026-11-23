"""Checagens de uso (regras gerais + quarto) sobre o projeto de exemplo."""

import json
import math
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from apoio import CASA, item, pav
from shapely import Point

from interiores_core import catalogo, geometria
from interiores_core.carregar import carregar
from interiores_core.modelo import DadosComodo, Porta, Projeto
from interiores_core.regras import checar, limites_do_tipo, validar_regras
from interiores_core.regras.contexto import lado_local, onde_na_planta
from interiores_core.tipos import modulo_do_tipo
from interiores_core.validacao import Problema, Severidade

Checar = Callable[..., list[Problema]]


@pytest.fixture
def moveis() -> dict[str, Any]:
    """comodos/quarto.json como dict — cópia, pode mutar à vontade.

    O tipo de porta do guarda-roupa é removido: os testes partem de "não
    informado" (considerado de abrir) e definem o que precisarem.
    """
    dados: dict[str, Any] = json.loads(
        (CASA / "comodos" / "quarto.json").read_text(encoding="utf-8")
    )
    item(dados["moveis"], "guarda-roupa").pop("portas", None)
    return dados


@pytest.fixture
def rodar(montar: Callable[[], Projeto], moveis: dict[str, Any]) -> Checar:
    """Checa o quarto com os dicts (depois de mutados pelo teste)."""

    def _rodar(regras: dict[str, object] | None = None) -> list[Problema]:
        dados = {"quarto": DadosComodo.model_validate(moveis)}
        return checar(montar(), dados, regras)

    return _rodar


def codigos(problemas: list[Problema], elemento: str | None = None) -> list[str]:
    return sorted(p.codigo for p in problemas if elemento is None or p.elemento == elemento)


def movel(moveis: dict[str, Any], id_: str) -> dict[str, Any]:
    return item(moveis["moveis"], id_)


def _novo_movel(id_: str, centro: list[int], largura: int, prof: int, alt: int = 800) -> Any:
    m = {"valor": 0, "origem": "projeto"}
    return {
        "id": id_,
        "tipo": "comoda",
        "centro": centro,
        "largura": {**m, "valor": largura},
        "profundidade": {**m, "valor": prof},
        "altura": {**m, "valor": alt},
    }


# ---------------------------------------------------------------- exemplo


def test_exemplo_da_casa(rodar: Checar) -> None:
    """Com as medidas estimadas, a cama fica a 560 mm das paredes nas laterais."""
    problemas = rodar()
    assert codigos(problemas) == [
        "lateral_cama",
        "lateral_cama",
        "passagem_livre",
        "portas_nao_informadas",
    ]
    laterais = [p for p in problemas if p.codigo == "lateral_cama"]
    assert all("560 mm livres; mínimo 600" in p.mensagem for p in laterais)
    assert all(p.regiao and p.posicao and p.comodo == "quarto" for p in laterais)
    # passagem bloqueada pelo vão de 560 mm entre a cama e a parede do banheiro
    passagem = next(p for p in problemas if p.codigo == "passagem_livre")
    assert passagem.elemento == "guarda-roupa"
    assert problemas[-1].severidade is Severidade.INFO  # ordenado por severidade


# ---------------------------------------------------------------- quarto


def test_lateral_cama_respeita_regras_toml(rodar: Checar) -> None:
    assert "lateral_cama" not in codigos(rodar({"quarto": {"lateral_cama": 550}}))
    # limite do quarto não se configura na seção geral: ignorado e acusado
    problemas = rodar({"geral": {"lateral_cama": 999}})
    assert "regra_desconhecida" in codigos(problemas)
    assert all("mínimo 600" in p.mensagem for p in problemas if p.codigo == "lateral_cama")


def test_cama_de_solteiro_basta_um_lado(rodar: Checar, moveis: dict[str, Any]) -> None:
    """A parte de baixo do quarto vai de y=75 a y=2575 (2500 mm) na faixa da cama."""
    cama = movel(moveis, "cama")
    cama["largura"]["valor"] = 880  # solteiro
    cama["centro"] = [2485, 515]  # y 75..955: encostada embaixo, 1620 livres em cima
    assert "lateral_cama" not in codigos(rodar())


def test_solteiro_sem_nenhum_lado_livre(rodar: Checar, moveis: dict[str, Any]) -> None:
    cama = movel(moveis, "cama")
    cama["largura"]["valor"] = 1100  # solteiro, y 775..1875: 700 livres de cada lado
    assert "lateral_cama" not in codigos(rodar())
    msgs = [
        p.mensagem for p in rodar({"quarto": {"lateral_cama": 800}}) if p.codigo == "lateral_cama"
    ]
    assert len(msgs) == 2 and all("nenhum lado livre" in m for m in msgs)


def test_casal_precisa_dos_dois_lados(rodar: Checar, moveis: dict[str, Any]) -> None:
    movel(moveis, "cama")["centro"] = [2485, 2015]  # sobe: 1250 embaixo, 0 em cima
    ps = [p for p in rodar() if p.codigo == "lateral_cama"]
    assert len(ps) == 1 and "acima na planta" in ps[0].mensagem


def test_frente_do_guarda_roupa(rodar: Checar, moveis: dict[str, Any]) -> None:
    gr = movel(moveis, "guarda-roupa")
    assert "frente_guarda_roupa" not in codigos(rodar())  # 920 livres ≥ 900
    gr["largura_porta"] = {"valor": 900, "origem": "estimada"}  # exige 1000
    assert "frente_guarda_roupa" in codigos(rodar())
    gr["portas"] = "correr"
    problemas = rodar()
    assert "frente_guarda_roupa" not in codigos(problemas)
    assert "portas_nao_informadas" not in codigos(problemas)
    gr["portas"] = "abrir"
    del gr["largura_porta"]
    movel(moveis, "cama")["centro"] = [2400, 1325]  # cama a 835 da frente
    p = next(p for p in rodar() if p.codigo == "frente_guarda_roupa")
    assert "835 mm livres; mínimo 900" in p.mensagem


# ---------------------------------------------------------------- gerais


def test_porta_colide_movel(rodar: Checar, moveis: dict[str, Any]) -> None:
    moveis["moveis"].append(_novo_movel("comoda", [2800, 4400], 600, 400))
    erro = next(p for p in rodar() if p.codigo == "porta_colide_movel")
    assert erro.severidade is Severidade.ERRO and erro.elemento == "porta-quarto"
    assert erro.regiao


def test_porta_do_banheiro_abre_para_o_banheiro(rodar: Checar, moveis: dict[str, Any]) -> None:
    """Móvel do quarto atrás da porta do banheiro não colide: ela gira para o outro lado."""
    moveis["moveis"].append(_novo_movel("cesto", [2300, 3700], 200, 200, 400))
    assert "porta_colide_movel" not in codigos(rodar())


def test_porta_sem_passagem(rodar: Checar, moveis: dict[str, Any]) -> None:
    moveis["moveis"].append(_novo_movel("estante", [2405, 3285], 400, 700))
    ps = [p for p in rodar() if p.codigo == "passagem_livre"]
    assert any(p.elemento == "porta-banheiro" for p in ps)


def test_instalacao_obstruida(rodar: Checar, moveis: dict[str, Any]) -> None:
    assert "instalacao_obstruida" not in codigos(rodar())
    movel(moveis, "cama")["centro"] = [2485, 1000]  # cama passa na frente da tomada em y=400
    p = next(p for p in rodar() if p.codigo == "instalacao_obstruida")
    assert p.elemento == "tomada-cama-esq" and "h300" in p.mensagem
    movel(moveis, "cama")["altura"]["valor"] = 250  # cama mais baixa que a tomada: ok
    assert "instalacao_obstruida" not in codigos(rodar())


def test_tomada_de_outro_comodo_nao_conta(
    rodar: Checar, casa_dict: dict[str, Any], moveis: dict[str, Any]
) -> None:
    pav(casa_dict)["instalacoes"].append(
        {
            "id": "tomada-banho",
            "forma": "ponto",
            "tipo": "tomada",
            "posicao": [1000, 2635],
            "altura": {"valor": 300, "origem": "projeto"},
            "parede": "p7",
            "comodo": "banheiro",
        }
    )
    moveis["moveis"].append(_novo_movel("bau", [1000, 2400], 400, 300, 500))
    assert "instalacao_obstruida" not in codigos(rodar())
    item(pav(casa_dict)["instalacoes"], "tomada-banho")["comodo"] = "quarto"
    assert "instalacao_obstruida" in codigos(rodar())


def test_comodo_que_nao_fecha_e_pulado(
    rodar: Checar, casa_dict: dict[str, Any], montar: Callable[[], Projeto]
) -> None:
    item(pav(casa_dict)["comodos"], "quarto")["paredes"].remove("p1")
    assert all(p.comodo != "quarto" for p in rodar())


def test_so_um_comodo(montar: Callable[[], Projeto]) -> None:
    problemas = checar(montar(), {}, {"xyz": {}}, comodo="banheiro")
    assert all(p.comodo == "banheiro" for p in problemas)  # regras.toml só no escopo total


# ---------------------------------------------------------------- limites e registro


def test_limites_do_tipo() -> None:
    limites, problemas = limites_do_tipo(
        "quarto", {"geral": {"passagem_livre": 800}, "quarto": {"passagem_livre": 900}}
    )
    assert limites["passagem_livre"] == 900 and limites["lateral_cama"] == 600
    assert not problemas
    limites, _ = limites_do_tipo("banheiro", {"geral": {"passagem_livre": 800}})
    assert limites["passagem_livre"] == 800 and "lateral_cama" not in limites
    _, problemas = limites_do_tipo("quarto", {"quarto": {"lateral_cama": "60 cm"}})
    assert [p.codigo for p in problemas] == ["regra_invalida"]
    _, problemas = limites_do_tipo("quarto", {"quarto": {"lateral_cama": True}})
    assert [p.codigo for p in problemas] == ["regra_invalida"]


def test_validar_regras() -> None:
    problemas = validar_regras(
        {"geral": {"passagem": 700}, "quartos": {}, "quarto": {"lateral_cama": 600}, "x": 1}
    )
    assert [p.codigo for p in problemas] == ["regra_desconhecida"] * 3
    assert validar_regras({"cozinha": {"passagem_livre": 800}, "quarto": 5}) == []


def test_regra_invalida_aparece_uma_vez(rodar: Checar) -> None:
    problemas = rodar({"geral": {"passagem_livre": -1}})
    assert codigos(problemas).count("regra_invalida") == 1


def test_registro_por_tipo() -> None:
    quarto = modulo_do_tipo("quarto")
    assert quarto is not None and "lateral_cama" in quarto.LIMITES and quarto.REGRAS
    cozinha = modulo_do_tipo("cozinha")
    assert cozinha is not None and "triangulo_min" in cozinha.LIMITES and cozinha.REGRAS
    assert modulo_do_tipo("lavabo") is None


def test_regras_toml_no_carregamento(tmp_path: Path) -> None:
    destino = tmp_path / "casa"
    shutil.copytree(CASA, destino)
    sem = carregar(destino)
    assert sem.regras == {}
    (destino / "regras.toml").write_text("[quarto]\nlateral_cama = 550\n", encoding="utf-8")
    com = carregar(destino)
    assert com.regras == {"quarto": {"lateral_cama": 550}}
    assert com.hash_entrada != sem.hash_entrada
    assert "lateral_cama" not in codigos(checar(com.projeto, com.dados_comodos, com.regras))


# ---------------------------------------------------------------- geometria auxiliar


def test_giro_de_porta(montar: Callable[[], Projeto]) -> None:
    p = montar().pavimentos[0]
    porta = next(a for a in p.aberturas if a.id == "porta-quarto")
    assert isinstance(porta, Porta)
    giro = geometria.giro_porta(p, porta)
    assert giro is not None
    assert giro.area == pytest.approx(math.pi * 800**2 / 4, rel=0.02)
    assert giro.contains(Point(3000, 4300))  # dentro do quarto, junto à dobradiça
    assert not giro.contains(Point(3000, 4900))  # fora (corredor)
    fim = porta.model_copy(update={"dobradica": "fim"})
    g2 = geometria.giro_porta(p, fim)
    assert g2 is not None and g2.contains(Point(2500, 4300))
    assert geometria.giro_porta(p, porta.model_copy(update={"folha": "correr"})) is None


def test_lados_do_movel(moveis: dict[str, Any]) -> None:
    dados = DadosComodo.model_validate(moveis)
    cama = next(m for m in dados.moveis if m.id == "cama")  # rotação 90: frente para -x
    (a, b), d = lado_local(cama, "frente")
    assert d == (-1, 0) and round(a[0]) == round(b[0]) == 1545
    _, d = lado_local(cama, "costas")
    assert d == (1, 0)
    assert onde_na_planta((0, -1)) == "abaixo na planta"
    assert onde_na_planta((0, 1)) == "acima na planta"
    assert onde_na_planta((1, 0)) == "à direita na planta"
    assert onde_na_planta((-1, 0)) == "à esquerda na planta"


# ---------------------------------------------------------------- catálogo nas regras


def test_distancia_da_tela(rodar: Checar, moveis: dict[str, Any]) -> None:
    # TV de 43" na parede oeste, de frente para a cama (pés a 1545): distância 1345
    moveis["moveis"].append(catalogo.novo_movel("tv", "tv", (160, 1325), "43pol", rotacao=270))
    movel(moveis, "guarda-roupa")["centro"] = [2800, 3800]  # tira o guarda-roupa da parede
    movel(moveis, "guarda-roupa")["rotacao"] = 90
    p = next(p for p in rodar() if p.codigo == "distancia_tela")
    assert "1345 mm" in p.mensagem and "mínimo 1638" in p.mensagem and p.regiao
    assert "distancia_tela" not in codigos(rodar({"geral": {"distancia_tela_pct": 100}}))
    moveis["moveis"][-1]["rotacao"] = 90  # tela virada para a parede: ninguém assiste
    assert "distancia_tela" not in codigos(rodar())
    del moveis["moveis"][-1]["polegadas"]
    assert "distancia_tela" not in codigos(rodar())


def test_movel_elevado_nao_ocupa_piso(rodar: Checar, moveis: dict[str, Any]) -> None:
    """Armário aéreo sobre a passagem da porta não bloqueia nem colide com a porta."""
    base = codigos(rodar())
    moveis["moveis"].append(
        catalogo.novo_movel("armario", "aereo", (2800, 4475), "aereo", rotacao=180)
    )
    assert codigos(rodar()) == base
    moveis["moveis"][-1]["elevacao"]["valor"] = 0  # no chão: bate na porta
    assert "porta_colide_movel" in codigos(rodar())


def test_moveis_fora_do_lugar(rodar: Checar, moveis: dict[str, Any]) -> None:
    moveis["moveis"].append(catalogo.novo_movel("comoda", "comoda", (2485, 1325)))
    assert ("moveis_sobrepostos", "cama") in {(p.codigo, p.elemento) for p in rodar()}
    moveis["moveis"][-1]["centro"] = [3400, 1325]  # metade dentro da parede leste
    erro = next(p for p in rodar() if p.codigo == "movel_fora_do_comodo")
    assert erro.severidade is Severidade.ERRO and erro.elemento == "comoda"


def test_tv_acima_do_rack_nao_colide(rodar: Checar, moveis: dict[str, Any]) -> None:
    moveis["moveis"] += [
        catalogo.novo_movel("rack", "rack", (1300, 2375), "pequeno", rotacao=180),
        catalogo.novo_movel("tv", "tv", (1300, 2535), "43pol", rotacao=180),
    ]
    moveis["moveis"][-1]["centro"] = [1300, 2400]  # TV sobre o rack, em projeção
    assert "moveis_sobrepostos" not in codigos(rodar())
    moveis["moveis"][-1]["elevacao"]["valor"] = 300  # desce até a altura do rack
    assert "moveis_sobrepostos" in codigos(rodar())


def test_escritorio_na_mesa_e_embaixo_dela(rodar: Checar, moveis: dict[str, Any]) -> None:
    """Monitor, notebook e teclado sobre a escrivaninha e gabinete embaixo dela não colidem;
    uma cômoda alta no mesmo lugar colide."""
    moveis["moveis"] = [
        catalogo.novo_movel("escrivaninha", "mesa", (1500, 2400), "escritorio_160"),
        catalogo.novo_movel("monitor", "monitor", (1400, 2300), "27pol"),
        catalogo.novo_movel("notebook", "notebook", (1900, 2400)),
        catalogo.novo_movel("teclado", "teclado", (1400, 2600)),
        catalogo.novo_movel("computador", "pc", (2100, 2400)),
    ]
    assert "moveis_sobrepostos" not in codigos(rodar())
    moveis["moveis"].append(catalogo.novo_movel("comoda", "comoda", (1000, 2400)))
    assert ("moveis_sobrepostos", "mesa") in {(p.codigo, p.elemento) for p in rodar()}


def test_tomada_acima_de_movel_baixo_nao_e_obstruida(rodar: Checar, moveis: dict[str, Any]) -> None:
    """Rack de 500 na frente da tomada a 300: tapa. TV elevada a 1000: não tapa."""
    moveis["moveis"].append(catalogo.novo_movel("tv", "tv", (3380, 400), "32pol", rotacao=90))
    assert "instalacao_obstruida" not in codigos(rodar())
    moveis["moveis"].append(
        catalogo.novo_movel("rack", "rack", (3225, 1000), "pequeno", rotacao=90)
    )
    p = next(p for p in rodar() if p.codigo == "instalacao_obstruida")
    assert "de 0 a 500 do piso" in p.mensagem


def test_bancada_com_modulo_fora_do_tampo(rodar: Checar, moveis: dict[str, Any]) -> None:
    mesa = catalogo.novo_movel("bancada", "mesa", (1500, 2400), "reta_gaveteiro")
    moveis["moveis"] = [mesa]
    assert "construcao_invalida" not in codigos(rodar())
    mesa["bancada"]["modulos"][0]["distancia"]["valor"] = 1400
    erro = next(p for p in rodar() if p.codigo == "construcao_invalida")
    assert erro.elemento == "mesa" and "sai do tampo" in erro.mensagem
