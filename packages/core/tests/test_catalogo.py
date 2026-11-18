"""Catálogo de móveis e edição do mobiliário."""

import json
import shutil
from pathlib import Path

import pytest
from apoio import CASA
from pydantic import ValidationError

from interiores_core import catalogo, editar
from interiores_core.carregar import carregar
from interiores_core.modelo import DadosComodo, Movel
from interiores_core.validacao import validar


def test_catalogo_cobre_os_moveis_pedidos() -> None:
    for tipo in (
        "cama",
        "guarda_roupa",
        "armario",
        "sofa",
        "tv",
        "mesa",
        "cadeira",
        "comoda",
        "criado_mudo",
        "escrivaninha",
        "estante",
        "rack",
        "poltrona",
    ):
        item = catalogo.item_do_tipo(tipo)
        assert item is not None, tipo
        assert item.modelo() is not None, f"{tipo}: modelo padrão inexistente"
        for m in item.modelos:
            assert m.largura > 0 and m.profundidade > 0 and m.altura > 0


def test_lados_de_uso() -> None:
    assert catalogo.lados_de_uso("cama") == ("esquerda", "direita", "frente")
    assert catalogo.lados_de_uso("tv") == ()
    assert catalogo.lados_de_uso("disco_voador") == ("frente",)


def test_novo_movel_vem_estimado_do_catalogo() -> None:
    d = catalogo.novo_movel("cama", "cama-2", (1000, 2000), "queen", rotacao=90)
    m = Movel.model_validate(d)
    assert (m.largura.valor, m.profundidade.valor, m.modelo) == (1580, 1980, "queen")
    assert m.largura.estimada and "padrão do catálogo" in (m.largura.obs or "")
    assert m.nome == "Cama" and m.rotacao == 90


def test_novo_movel_com_medidas_informadas() -> None:
    d = catalogo.novo_movel(
        "guarda_roupa", "gr", (0, 0), medidas={"largura": 2000}, origem_medidas="trena"
    )
    m = Movel.model_validate(d)
    assert m.largura.valor == 2000 and m.largura.origem == "trena"
    assert m.profundidade.estimada  # o resto continua do catálogo
    assert m.portas == "correr"  # modelo padrão do guarda-roupa


def test_novo_movel_tv_e_aereo() -> None:
    tv = Movel.model_validate(catalogo.novo_movel("tv", "tv", (0, 0), "65pol"))
    assert tv.polegadas == 65 and tv.elevacao is not None and not tv.ocupa_piso
    aereo = Movel.model_validate(catalogo.novo_movel("armario", "a", (0, 0), "aereo"))
    assert not aereo.ocupa_piso and aereo.largura_porta is not None


def test_novo_movel_erros() -> None:
    with pytest.raises(KeyError, match="não está no catálogo"):
        catalogo.novo_movel("foguete", "f", (0, 0))
    with pytest.raises(KeyError, match="modelo 'x' não existe"):
        catalogo.novo_movel("cama", "c", (0, 0), "x")
    with pytest.raises(KeyError, match="desconhecida"):
        catalogo.novo_movel("cama", "c", (0, 0), medidas={"cor": 1})


def test_exportar_catalogo() -> None:
    dados = catalogo.exportar()
    assert dados["versao"] == 1
    tipos = {i["tipo"] for i in dados["itens"]}
    assert tipos == set(catalogo.CATALOGO)
    json.dumps(dados)  # serializável


def test_validacao_do_catalogo() -> None:
    dados = json.loads((CASA / "comodos" / "quarto.json").read_text(encoding="utf-8"))
    dados["moveis"] += [
        {**catalogo.novo_movel("cama", "x1", (0, 0)), "tipo": "rede"},
        {**catalogo.novo_movel("cama", "x2", (0, 0)), "modelo": "imperial"},
        {k: v for k, v in catalogo.novo_movel("tv", "x3", (0, 0)).items() if k != "polegadas"},
    ]
    carregado = carregar(CASA)
    problemas = validar(carregado.projeto, {"quarto": DadosComodo.model_validate(dados)})
    codigos = {(p.codigo, p.elemento) for p in problemas}
    assert ("movel_fora_do_catalogo", "x1") in codigos
    assert ("modelo_desconhecido", "x2") in codigos
    assert ("tela_sem_polegadas", "x3") in codigos


# ---------------------------------------------------------------- edição


@pytest.fixture
def copia(tmp_path: Path) -> Path:
    destino = tmp_path / "casa"
    shutil.copytree(CASA, destino)
    return destino


def test_adicionar_mover_remover(copia: Path) -> None:
    arq = copia / "comodos" / "quarto.json"
    antes = arq.read_text(encoding="utf-8")
    novo = catalogo.novo_movel(
        "criado_mudo", editar.id_livre(copia, "quarto", "criado_mudo"), (3200, 375), rotacao=90
    )
    assert novo["id"] == "criado-mudo"
    dados = editar.adicionar_movel(copia, "quarto", novo)
    assert dados.moveis[-1].id == "criado-mudo"
    assert editar.id_livre(copia, "quarto", "criado-mudo") == "criado-mudo-2"

    editar.mover_movel(copia, "quarto", "criado-mudo", (3200, 2275), 270)
    m = carregar(copia).dados_comodos["quarto"].moveis[-1]
    assert (m.centro, m.rotacao) == ((3200, 2275), 270)
    editar.mover_movel(copia, "quarto", "criado-mudo", rotacao=90)
    assert carregar(copia).dados_comodos["quarto"].moveis[-1].centro == (3200, 2275)

    editar.remover_movel(copia, "quarto", "criado-mudo")
    assert arq.read_text(encoding="utf-8") == antes  # formatação preservada


def test_encostar_na_parede(copia: Path) -> None:
    movel = catalogo.novo_movel("criado_mudo", "criado", (0, 0))
    editar.encostar(copia, "quarto", movel, "p2", 100)
    assert (movel["centro"], movel["rotacao"]) == ([3225, 325], 90)
    editar.adicionar_movel(copia, "quarto", movel)
    editar.mover_movel(copia, "quarto", "criado", parede="p1", distancia=200)
    m = carregar(copia).dados_comodos["quarto"].moveis[-1]
    assert (m.centro, m.rotacao) == ((425, 275), 0)
    with pytest.raises(KeyError, match="cozinha"):
        editar.encostar(copia, "cozinha", movel, "p1", 0)
    with pytest.raises(ValueError, match="não delimita"):
        editar.mover_movel(copia, "quarto", "criado", parede="p4")


def test_edicao_cria_arquivo_do_comodo(copia: Path) -> None:
    editar.adicionar_movel(
        copia, "banheiro", catalogo.novo_movel("armario", "gabinete", (1000, 2900), "baixo")
    )
    dados = carregar(copia).dados_comodos["banheiro"]
    assert dados.comodo == "banheiro" and dados.moveis[0].id == "gabinete"


def test_edicao_erros(copia: Path) -> None:
    arq = copia / "comodos" / "quarto.json"
    antes = arq.read_text(encoding="utf-8")
    with pytest.raises(KeyError, match="cômodo 'cozinha'"):
        editar.adicionar_movel(copia, "cozinha", catalogo.novo_movel("cama", "c", (0, 0)))
    with pytest.raises(ValueError, match="já existe"):
        editar.adicionar_movel(copia, "quarto", catalogo.novo_movel("cama", "cama", (0, 0)))
    with pytest.raises(KeyError, match="não existe neste cômodo"):
        editar.mover_movel(copia, "quarto", "nada", (0, 0))
    with pytest.raises(KeyError):
        editar.remover_movel(copia, "quarto", "nada")
    with pytest.raises(ValidationError):  # rotação inválida não chega a ser gravada
        editar.mover_movel(copia, "quarto", "cama", rotacao=45)
    assert arq.read_text(encoding="utf-8") == antes
    assert editar.id_livre(copia, "quarto", "Cômoda Grande!") == "c-moda-grande"
