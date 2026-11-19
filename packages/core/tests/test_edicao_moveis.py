"""Edição do mobiliário (funções puras)."""

import pytest
from apoio import CASA

from interiores_core import edicao_moveis as em
from interiores_core.carregar import carregar
from interiores_core.edicao import EdicaoInvalidaError
from interiores_core.medidas import Medida, Origem
from interiores_core.modelo import DadosComodo, Projeto


@pytest.fixture
def casa() -> tuple[Projeto, DadosComodo]:
    c = carregar(CASA)
    return c.projeto, c.dados_comodos["quarto"]


def _m(ed: em.EdicaoMoveis, id_: str):  # type: ignore[no-untyped-def]
    return next(m for m in ed.dados.moveis if m.id == id_)


def test_tv_presa_na_parede(casa: tuple[Projeto, DadosComodo]) -> None:
    projeto, dados = casa
    ed = em.adicionar_movel(projeto, "quarto", dados, "tv", modelo="50pol", parede="p2",
                            distancia=1000)  # fmt: skip
    tv = _m(ed, "tv")
    assert tv.rotacao == 90  # frente para -x, de frente para o quarto
    assert tv.centro[0] == 3500 - 75 - tv.profundidade.valor // 2
    assert [a.caminho for a in ed.alteracoes] == ["comodos.quarto.moveis[tv]"]
    assert len(dados.moveis) == 2  # original intacto


def test_medidas_informadas_com_origem(casa: tuple[Projeto, DadosComodo]) -> None:
    projeto, dados = casa
    ed = em.adicionar_movel(
        projeto, "quarto", dados, "sofa", centro=(1700, 800),
        medidas={"largura": Medida(valor=1800, origem=Origem.TRENA)},
    )  # fmt: skip
    sofa = _m(ed, "sofa")
    assert (sofa.largura.valor, sofa.largura.origem) == (1800, Origem.TRENA)
    assert sofa.largura.obs and sofa.largura.obs.startswith("antes:")
    assert sofa.altura.origem == Origem.ESTIMADA  # o resto vem do catálogo


def test_posicao_obrigatoria_e_unica(casa: tuple[Projeto, DadosComodo]) -> None:
    projeto, dados = casa
    with pytest.raises(EdicaoInvalidaError, match="informe a posição"):
        em.adicionar_movel(projeto, "quarto", dados, "tv")
    with pytest.raises(EdicaoInvalidaError, match="informe a posição"):
        em.adicionar_movel(projeto, "quarto", dados, "tv", centro=(0, 0), parede="p2")
    with pytest.raises(EdicaoInvalidaError, match="não está no catálogo"):
        em.adicionar_movel(projeto, "quarto", dados, "foguete", centro=(0, 0))
    with pytest.raises(EdicaoInvalidaError, match="desconhecida"):
        em.adicionar_movel(projeto, "quarto", dados, "tv", centro=(0, 0),
                           medidas={"peso": {"valor": 1, "origem": "trena"}})  # fmt: skip
    with pytest.raises(KeyError):
        em.adicionar_movel(projeto, "cozinha", dados, "tv", centro=(0, 0))


def test_ids(casa: tuple[Projeto, DadosComodo]) -> None:
    projeto, dados = casa
    ed = em.adicionar_movel(projeto, "quarto", dados, "cama", centro=(1700, 3000))
    assert _m(ed, "cama-2")
    with pytest.raises(EdicaoInvalidaError, match="id_duplicado"):
        em.adicionar_movel(projeto, "quarto", dados, "tv", id_="cama", centro=(0, 0))
    vazio = em.adicionar_movel(projeto, "banheiro", None, "banco", centro=(1000, 3700))
    assert vazio.dados.comodo == "banheiro" and _m(vazio, "banco")


def test_mover_girar_e_prender(casa: tuple[Projeto, DadosComodo]) -> None:
    projeto, dados = casa
    ed = em.mover_movel(projeto, "quarto", dados, "cama", centro=(2000, 1300), rotacao=180)
    assert (_m(ed, "cama").centro, _m(ed, "cama").rotacao) == ((2000, 1300), 180)
    assert {a.caminho for a in ed.alteracoes} == {
        "comodos.quarto.moveis[cama].centro",
        "comodos.quarto.moveis[cama].rotacao",
    }
    presa = em.mover_movel(projeto, "quarto", dados, "cama", parede="p1", distancia=500)
    assert _m(presa, "cama").rotacao == 0  # costas na parede de baixo, frente para +y
    with pytest.raises(EdicaoInvalidaError, match="calculados"):
        em.mover_movel(projeto, "quarto", dados, "cama", parede="p1", rotacao=90)
    with pytest.raises(EdicaoInvalidaError, match="não delimita"):
        em.mover_movel(projeto, "quarto", dados, "cama", parede="p4")
    with pytest.raises(KeyError):
        em.mover_movel(projeto, "quarto", dados, "nao-existe", centro=(0, 0))


def test_checagens_apontam_o_problema(casa: tuple[Projeto, DadosComodo]) -> None:
    projeto, dados = casa
    ed = em.mover_movel(projeto, "quarto", dados, "cama", centro=(900, 1325))  # em cima do GR
    assert ed.novos, "mover a cama para cima do guarda-roupa deveria gerar problema"
    assert all(p.comodo == "quarto" for p in ed.problemas)


def test_alterar_e_remover(casa: tuple[Projeto, DadosComodo]) -> None:
    projeto, dados = casa
    campos = {"largura": Medida(valor=1580, origem=Origem.TRENA), "nome": "Queen"}
    ed = em.alterar_movel(projeto, "quarto", dados, "cama", campos)
    cama = _m(ed, "cama")
    assert cama.largura.valor == 1580 and cama.nome == "Queen"
    assert cama.largura.obs == "antes: 1380 mm (estimada)"
    with pytest.raises(EdicaoInvalidaError, match="mover"):
        em.alterar_movel(projeto, "quarto", dados, "cama", {"centro": (0, 0)})
    with pytest.raises(EdicaoInvalidaError, match="dados inválidos"):
        em.alterar_movel(projeto, "quarto", dados, "cama", {"largura": {"valor": 1}})
    fora = em.remover_movel(projeto, "quarto", dados, "cama")
    assert [m.id for m in fora.dados.moveis] == ["guarda-roupa"]
    assert [a.caminho for a in fora.alteracoes] == ["comodos.quarto.moveis[cama]"]
