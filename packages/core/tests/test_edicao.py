"""Edição da planta: paredes, aberturas, cômodos e pavimento (funções puras)."""

from pathlib import Path

import pytest
from apoio import CASA

from interiores_core import edicao
from interiores_core.edicao import EdicaoInvalidaError
from interiores_core.geometria import area_util_m2
from interiores_core.medidas import Medida, Origem
from interiores_core.modelo import Projeto


@pytest.fixture
def casa() -> Projeto:
    return edicao.ler_projeto(CASA)


def _codigos(ed: edicao.Edicao) -> set[str]:
    return {p.codigo for p in ed.novos}


def _pav(p: Projeto):  # type: ignore[no-untyped-def]
    return p.pavimentos[0]


# ---------------------------------------------------------------- paredes


def test_medida_de_trena_guarda_a_estimada(casa: Projeto) -> None:
    ed = edicao.alterar_parede(
        casa, "terreo", "p1", {"espessura": Medida(valor=140, origem=Origem.TRENA)}
    )
    esp = _pav(ed.projeto).parede("p1").espessura
    assert (esp.valor, esp.origem) == (140, Origem.TRENA)
    assert esp.obs == "antes: 150 mm (estimada)"
    assert [str(a) for a in ed.alteracoes] == [
        "pavimentos[terreo].paredes[p1].espessura: 150 (estimada) → 140 (trena)"
    ]
    assert _pav(casa).parede("p1").espessura.valor == 150  # original intacto


def test_mover_canto_arrasta_vizinhas_e_instalacoes(casa: Projeto) -> None:
    ed = edicao.alterar_parede(casa, "terreo", "p2", {"inicio": (3600, 0), "fim": (3600, 4750)})
    pav = _pav(ed.projeto)
    assert pav.parede("p1").fim == (3600, 0)
    assert pav.parede("p3").inicio == (3600, 4750)
    assert next(i for i in pav.instalacoes if i.id == "tomada-cama-esq").posicao == (3600, 400)
    assert "comodo_nao_fechado" not in _codigos(ed)
    assert area_util_m2(pav, pav.comodo("quarto")) > area_util_m2(  # type: ignore[arg-type,operator]
        _pav(casa), _pav(casa).comodo("quarto")
    )


def test_mover_so_a_parede_abre_o_comodo_sem_bloquear(casa: Projeto) -> None:
    ed = edicao.alterar_parede(
        casa, "terreo", "p2", {"inicio": (3600, 0), "fim": (3600, 4750)}, arrastar_vizinhas=False
    )
    assert _pav(ed.projeto).parede("p1").fim == (3500, 0)
    assert "comodo_nao_fechado" in _codigos(ed)


def test_mover_vertice(casa: Projeto) -> None:
    ed = edicao.mover_vertice(casa, "terreo", (3500, 0), (3500, -100))
    pav = _pav(ed.projeto)
    assert pav.parede("p1").fim == (3500, -100) and pav.parede("p2").inicio == (3500, -100)
    with pytest.raises(KeyError):
        edicao.mover_vertice(casa, "terreo", (1, 1), (2, 2))


def test_dividir_parede_leva_a_janela(casa: Projeto) -> None:
    ed = edicao.dividir_parede(casa, "terreo", "p1", 600)
    pav = _pav(ed.projeto)
    assert pav.parede("p1").fim == (600, 0) and pav.parede("p9").inicio == (600, 0)
    janela = next(a for a in pav.aberturas if a.id == "janela-quarto")
    assert (janela.parede, janela.distancia_inicio.valor) == ("p9", 400)
    assert pav.comodo("quarto").paredes[:2] == ["p1", "p9"]  # type: ignore[union-attr]
    assert "comodo_nao_fechado" not in _codigos(ed)


def test_dividir_parede_no_vao_recusa(casa: Projeto) -> None:
    with pytest.raises(EdicaoInvalidaError, match="janela-quarto"):
        edicao.dividir_parede(casa, "terreo", "p1", 2000)
    with pytest.raises(EdicaoInvalidaError, match="fora da parede"):
        edicao.dividir_parede(casa, "terreo", "p1", 9000)


def test_remover_parede_em_uso(casa: Projeto) -> None:
    with pytest.raises(EdicaoInvalidaError, match="em uso"):
        edicao.remover_parede(casa, "terreo", "p8")
    ed = edicao.remover_parede(casa, "terreo", "p8", cascata=True)
    pav = _pav(ed.projeto)
    assert pav.parede("p8") is None
    assert all(a.parede != "p8" for a in pav.aberturas)
    assert "comodo_nao_fechado" in _codigos(ed)  # aponta, não bloqueia
    removidas = [a.caminho for a in ed.alteracoes if a.depois is None]
    assert "pavimentos[terreo].paredes[p8]" in removidas


def test_parede_com_lado_inexistente_recusa(casa: Projeto) -> None:
    with pytest.raises(EdicaoInvalidaError, match="lado_inexistente"):
        edicao.alterar_parede(casa, "terreo", "p1", {"lado_b": "cozinha"})


def test_campo_nao_editavel(casa: Projeto) -> None:
    with pytest.raises(EdicaoInvalidaError, match="id"):
        edicao.alterar_parede(casa, "terreo", "p1", {"id": "x"})


def test_dados_invalidos_viram_edicao_invalida(casa: Projeto) -> None:
    with pytest.raises(EdicaoInvalidaError, match="dados inválidos"):
        edicao.alterar_parede(
            casa, "terreo", "p1", {"espessura": {"valor": 1.5, "origem": "trena"}}
        )


# ---------------------------------------------------------------- aberturas


def test_adicionar_e_remover_janela(casa: Projeto) -> None:
    janela = {
        "id": "janela-2",
        "tipo": "janela",
        "parede": "p2",
        "distancia_inicio": {"valor": 500, "origem": "projeto"},
        "largura": {"valor": 1000, "origem": "projeto"},
        "altura": {"valor": 1000, "origem": "projeto"},
        "peitoril": {"valor": 1100, "origem": "projeto"},
    }
    ed = edicao.adicionar_abertura(casa, "terreo", janela)
    assert [a.caminho for a in ed.alteracoes] == ["pavimentos[terreo].aberturas[janela-2]"]
    with pytest.raises(EdicaoInvalidaError, match="id_duplicado"):
        edicao.adicionar_abertura(ed.projeto, "terreo", janela)
    with pytest.raises(KeyError):
        edicao.adicionar_abertura(casa, "terreo", {**janela, "parede": "p99"})
    de_volta = edicao.remover_abertura(ed.projeto, "terreo", "janela-2")
    assert de_volta.projeto == casa


def test_alterar_porta(casa: Projeto) -> None:
    ed = edicao.alterar_abertura(
        casa,
        "terreo",
        "porta-quarto",
        {"largura": Medida(valor=900, origem=Origem.TRENA), "dobradica": "fim"},
    )
    porta = next(a for a in _pav(ed.projeto).aberturas if a.id == "porta-quarto")
    assert porta.largura.valor == 900 and porta.dobradica == "fim"
    with pytest.raises(EdicaoInvalidaError, match="porta_sentido"):
        edicao.alterar_abertura(casa, "terreo", "porta-quarto", {"abre_para": None})
    with pytest.raises(EdicaoInvalidaError, match="peitoril"):
        edicao.alterar_abertura(
            casa, "terreo", "porta-quarto", {"peitoril": Medida(valor=1, origem=Origem.TRENA)}
        )


# ---------------------------------------------------------------- cômodos


def _vazio() -> Projeto:
    m = {"valor": 2600, "origem": "projeto"}
    return Projeto.model_validate(
        {
            "schema_version": 1,
            "projeto": "nova",
            "imovel": {"tipo": "casa"},
            "pavimentos": [{"id": "terreo", "cota_piso": {"valor": 0, "origem": "projeto"},
                            "pe_direito": m}],
        }
    )  # fmt: skip


def _parede(id_: str, ini: tuple[int, int], fim: tuple[int, int]) -> dict[str, object]:
    return {
        "id": id_,
        "inicio": ini,
        "fim": fim,
        "espessura": {"valor": 150, "origem": "projeto"},
        "lado_a": "externo",
        "lado_b": "externo",
    }


def test_casa_do_zero(tmp_path: Path) -> None:
    p = _vazio()
    # desenhado no sentido horário: o cômodo fica à direita (lado_b)
    cantos = [(0, 0), (0, 3000), (4000, 3000), (4000, 0)]
    for n, (a, b) in enumerate(zip(cantos, [*cantos[1:], cantos[0]], strict=True), 1):
        p = edicao.adicionar_parede(p, "terreo", _parede(f"p{n}", a, b)).projeto
    ed = edicao.adicionar_comodo(
        p,
        "terreo",
        {"id": "sala", "nome": "Sala", "tipo": "sala", "paredes": ["p1", "p2", "p3", "p4"]},
    )
    pav = _pav(ed.projeto)
    assert all((w.lado_a, w.lado_b) == ("externo", "sala") for w in pav.paredes)
    assert area_util_m2(pav, pav.comodo("sala")) == round(3.85 * 2.85, 2)  # type: ignore[arg-type]
    assert {"comodo_nao_fechado", "lado_inconsistente"}.isdisjoint(_codigos(ed))

    # parede no meio divide a sala; a cozinha usa o lado livre dela
    p = edicao.dividir_parede(
        ed.projeto, "terreo", "p2", 2000
    ).projeto  # p5: (2000,3000)→(4000,3000)
    p = edicao.dividir_parede(p, "terreo", "p4", 2000).projeto  # p6: (2000,0)→(0,0)
    p = edicao.adicionar_parede(p, "terreo", _parede("p7", (2000, 0), (2000, 3000))).projeto
    p = edicao.alterar_comodo(p, "terreo", "sala", {"paredes": ["p1", "p2", "p7", "p6"]}).projeto
    ed = edicao.adicionar_comodo(
        p, "terreo", {"id": "cozinha", "nome": "Cozinha", "tipo": "cozinha",
                      "paredes": ["p5", "p3", "p4", "p7"]},
    )  # fmt: skip
    pav = _pav(ed.projeto)
    assert (pav.parede("p7").lado_a, pav.parede("p7").lado_b) == ("sala", "cozinha")
    assert (pav.parede("p5").lado_b, pav.parede("p4").lado_b) == ("cozinha", "cozinha")
    assert not [x for x in ed.problemas if x.severidade == "erro"]

    # um terceiro cômodo não cabe na parede que já separa dois
    with pytest.raises(EdicaoInvalidaError, match="ocupado"):
        edicao.adicionar_comodo(
            ed.projeto, "terreo",
            {"id": "x", "nome": "X", "tipo": "outro", "paredes": ["p5", "p3", "p4", "p7"]},
        )  # fmt: skip
    with pytest.raises(EdicaoInvalidaError, match="já existe"):
        edicao.adicionar_comodo(
            ed.projeto, "terreo",
            {"id": "sala", "nome": "S", "tipo": "sala", "paredes": ["p1", "p2", "p7", "p6"]},
        )  # fmt: skip

    edicao.gravar_projeto(tmp_path, ed.projeto)
    assert edicao.ler_projeto(tmp_path) == ed.projeto


def test_remover_comodo(casa: Projeto) -> None:
    ed = edicao.remover_comodo(casa, "terreo", "banheiro")
    pav = _pav(ed.projeto)
    assert pav.comodo("banheiro") is None
    assert "banheiro" not in {w.lado_a for w in pav.paredes} | {w.lado_b for w in pav.paredes}
    porta = next(a for a in pav.aberturas if a.id == "porta-banheiro")
    assert (porta.para, porta.abre_para) == ("externo", "externo")  # type: ignore[union-attr]
    assert next(i for i in pav.instalacoes if i.id == "agua-pia").comodo is None  # type: ignore[union-attr]


def test_alterar_comodo_e_pavimento(casa: Projeto) -> None:
    ed = edicao.alterar_comodo(casa, "terreo", "quarto", {"nome": "Suíte", "piso": "porcelanato"})
    assert _pav(ed.projeto).comodo("quarto").nome == "Suíte"  # type: ignore[union-attr]
    ed = edicao.alterar_pavimento(
        casa, "terreo", {"pe_direito": Medida(valor=2650, origem=Origem.TRENA)}
    )
    assert _pav(ed.projeto).pe_direito.obs == "antes: 2600 mm (estimada)"
    with pytest.raises(KeyError):
        edicao.alterar_pavimento(casa, "superior", {"nome": "x"})


def test_diferencas_casam_por_id() -> None:
    antes = {"paredes": [{"id": "a", "x": 1}, {"id": "b", "x": 2}]}
    depois = {"paredes": [{"id": "b", "x": 3}, {"id": "c", "x": 4}]}
    assert [str(a) for a in edicao.diferencas(antes, depois)] == [
        'paredes[a]: {"id": "a", "x": 1} → —',
        "paredes[b].x: 2 → 3",
        'paredes[c]: — → {"id": "c", "x": 4}',
    ]


# ---------------------------------------------------------------- instalações


def _tomada(**extra: object) -> dict[str, object]:
    return {
        "id": "tomada-nova",
        "forma": "ponto",
        "tipo": "tomada",
        "altura": {"valor": 300, "origem": "projeto"},
        **extra,
    }


def _inst(p: Projeto, id_: str):  # type: ignore[no-untyped-def]
    return next(i for i in _pav(p).instalacoes if i.id == id_)


def test_tomada_pela_distancia_na_parede(casa: Projeto) -> None:
    ed = edicao.adicionar_instalacao(casa, "terreo", _tomada(parede="p2"), distancia=1000)
    assert _inst(ed.projeto, "tomada-nova").posicao == (3500, 1000)
    assert [a.caminho for a in ed.alteracoes] == ["pavimentos[terreo].instalacoes[tomada-nova]"]
    with pytest.raises(EdicaoInvalidaError, match="id_duplicado"):
        edicao.adicionar_instalacao(ed.projeto, "terreo", _tomada(parede="p2"), distancia=10)


def test_posicao_e_levada_para_o_eixo_da_parede(casa: Projeto) -> None:
    ed = edicao.adicionar_instalacao(casa, "terreo", _tomada(parede="p2", posicao=(3420, 2000)))
    assert _inst(ed.projeto, "tomada-nova").posicao == (3500, 2000)
    ed = edicao.adicionar_instalacao(casa, "terreo", _tomada(parede="p2", posicao=(3500, 9000)))
    assert _inst(ed.projeto, "tomada-nova").posicao == (3500, 4750)  # limitada à ponta


def test_ponto_sem_parede_fica_onde_mandar(casa: Projeto) -> None:
    ralo = {**_tomada(posicao=(700, 4000)), "id": "ralo-2", "tipo": "ralo"}
    ed = edicao.adicionar_instalacao(casa, "terreo", ralo)
    assert _inst(ed.projeto, "ralo-2").posicao == (700, 4000)
    with pytest.raises(EdicaoInvalidaError, match="só vale"):
        edicao.adicionar_instalacao(casa, "terreo", ralo, distancia=100)
    with pytest.raises(EdicaoInvalidaError, match="informe a posição"):
        edicao.adicionar_instalacao(casa, "terreo", _tomada(parede="p2"))


def test_ponto_em_parede_interna_pede_o_lado(casa: Projeto) -> None:
    agua = {**_tomada(parede="p7"), "id": "agua-2", "tipo": "agua_fria"}
    ed = edicao.adicionar_instalacao(casa, "terreo", agua, distancia=500)
    assert "instalacao_lado_indefinido" in _codigos(ed)  # aviso, não bloqueia
    ed = edicao.adicionar_instalacao(casa, "terreo", {**agua, "comodo": "banheiro"}, distancia=500)
    assert "instalacao_lado_indefinido" not in _codigos(ed)
    with pytest.raises(EdicaoInvalidaError, match="instalacao_comodo_invalido"):
        edicao.adicionar_instalacao(casa, "terreo", {**agua, "comodo": "cozinha"}, distancia=500)


def test_alterar_e_remover_ponto(casa: Projeto) -> None:
    ed = edicao.alterar_instalacao(
        casa,
        "terreo",
        "tomada-cama-esq",
        {"altura": Medida(valor=350, origem=Origem.TRENA)},
        distancia=200,
    )
    tomada = _inst(ed.projeto, "tomada-cama-esq")
    assert tomada.posicao == (3500, 200)
    assert tomada.altura.obs == "antes: 300 mm (estimada)"
    solta = edicao.alterar_instalacao(casa, "terreo", "tomada-cama-esq", {"parede": None})
    assert _inst(solta.projeto, "tomada-cama-esq").parede is None
    alta = edicao.alterar_instalacao(
        casa, "terreo", "tomada-cama-esq", {"altura": {"valor": 3000, "origem": "projeto"}}
    )
    assert "instalacao_acima_do_teto" in _codigos(alta)  # erro geométrico: aponta
    with pytest.raises(EdicaoInvalidaError, match="caminho"):
        edicao.alterar_instalacao(casa, "terreo", "tomada-cama-esq", {"caminho": [(0, 0), (1, 1)]})
    ed = edicao.remover_instalacao(casa, "terreo", "tomada-cama-esq")
    assert all(i.id != "tomada-cama-esq" for i in _pav(ed.projeto).instalacoes)
    with pytest.raises(KeyError):
        edicao.remover_instalacao(casa, "terreo", "nao-existe")


def test_trecho_de_tubulacao(casa: Projeto) -> None:
    trecho = {
        "id": "af-banheiro",
        "forma": "trecho",
        "tipo": "agua_fria",
        "caminho": [(1000, 2635), (1000, 4000)],
        "altura": {"valor": 600, "origem": "estimada"},
    }
    ed = edicao.adicionar_instalacao(casa, "terreo", trecho)
    ed = edicao.alterar_instalacao(
        ed.projeto, "terreo", "af-banheiro", {"caminho": [(1000, 2635), (1600, 4400)]}
    )
    assert _inst(ed.projeto, "af-banheiro").caminho == [(1000, 2635), (1600, 4400)]
    assert [str(a) for a in ed.alteracoes] == [
        "pavimentos[terreo].instalacoes[af-banheiro].caminho: "
        "[[1000, 2635], [1000, 4000]] → [[1000, 2635], [1600, 4400]]"
    ]


# ---------------------------------------------------------------- pavimentos, imóvel, projeto


def _superior() -> dict[str, object]:
    return {"id": "superior", "cota_piso": {"valor": 2900, "origem": "projeto"},
            "pe_direito": {"valor": 2600, "origem": "projeto"}}  # fmt: skip


def test_adicionar_e_remover_pavimento(casa: Projeto) -> None:
    ed = edicao.adicionar_pavimento(casa, _superior())
    assert [p.id for p in ed.projeto.pavimentos] == ["terreo", "superior"]
    with pytest.raises(EdicaoInvalidaError, match="já existe"):
        edicao.adicionar_pavimento(ed.projeto, _superior())
    meio = edicao.adicionar_pavimento(ed.projeto, {**_superior(), "id": "mezanino"}, "terreo")
    assert [p.id for p in meio.projeto.pavimentos] == ["terreo", "mezanino", "superior"]
    vazio = edicao.remover_pavimento(ed.projeto, "superior")
    assert [p.id for p in vazio.projeto.pavimentos] == ["terreo"]
    with pytest.raises(EdicaoInvalidaError, match="não está vazio"):
        edicao.remover_pavimento(ed.projeto, "terreo")
    so_superior = edicao.remover_pavimento(ed.projeto, "terreo", cascata=True)
    assert [p.id for p in so_superior.projeto.pavimentos] == ["superior"]
    with pytest.raises(EdicaoInvalidaError, match="pelo menos um"):
        edicao.remover_pavimento(casa, "terreo", cascata=True)
    assert edicao.comodos_do_pavimento(casa, "terreo") == ["quarto", "banheiro"]
    with pytest.raises(KeyError):
        edicao.comodos_do_pavimento(casa, "superior")


def test_imovel_e_codigo(casa: Projeto) -> None:
    ed = edicao.alterar_imovel(casa, {"tipo": "apartamento", "endereco_apelido": "apê"})
    assert (ed.projeto.imovel.tipo, ed.projeto.imovel.endereco_apelido) == ("apartamento", "apê")
    with pytest.raises(EdicaoInvalidaError, match="dados inválidos"):
        edicao.alterar_imovel(casa, {"tipo": "barco"})
    assert edicao.renomear_projeto(casa, "casa-praia").projeto.projeto == "casa-praia"
    with pytest.raises(EdicaoInvalidaError, match="dados inválidos"):
        edicao.renomear_projeto(casa, "Casa Praia")
