from collections.abc import Callable
from typing import Any

import pytest
from apoio import item, pav

from interiores_core.modelo import DadosComodo, Projeto
from interiores_core.validacao import Severidade, validar


def codigos(projeto: Projeto, **kw: Any) -> set[str]:
    return {p.codigo for p in validar(projeto, **kw)}


def test_casa_sem_erros(montar: Callable[[], Projeto]) -> None:
    problemas = validar(montar())
    assert [p.codigo for p in problemas] == ["sem_estrutura"]
    assert problemas[0].severidade is Severidade.INFO


def par(d: dict[str, Any], id_: str) -> dict[str, Any]:
    return item(pav(d)["paredes"], id_)


def abe(d: dict[str, Any], id_: str) -> dict[str, Any]:
    return item(pav(d)["aberturas"], id_)


def com(d: dict[str, Any], id_: str) -> dict[str, Any]:
    return item(pav(d)["comodos"], id_)


CASOS: list[tuple[str, Callable[[dict[str, Any]], Any]]] = [
    ("id_duplicado", lambda d: pav(d)["paredes"].append(dict(par(d, "p1")))),
    ("id_duplicado", lambda d: pav(d)["comodos"].append(dict(com(d, "banheiro")))),
    (
        "id_duplicado",
        lambda d: d["pavimentos"].append(dict(pav(d), comodos=[], paredes=[], aberturas=[])),
    ),
    ("parede_inexistente", lambda d: com(d, "quarto")["paredes"].append("p99")),
    ("parede_repetida", lambda d: com(d, "quarto")["paredes"].append("p1")),
    ("lado_inexistente", lambda d: par(d, "p1").update(lado_b="varanda")),
    ("parede_lados_iguais", lambda d: par(d, "p7").update(lado_b="banheiro")),
    ("parede_nula", lambda d: par(d, "p1").update(fim=[0, 0])),
    ("lado_inconsistente", lambda d: par(d, "p1").update(lado_a="externo", lado_b="externo2")),
    ("lado_inconsistente", lambda d: par(d, "p4").update(lado_b="quarto")),
    ("lado_trocado", lambda d: par(d, "p1").update(lado_a="externo", lado_b="quarto")),
    ("comodo_nao_fechado", lambda d: com(d, "banheiro")["paredes"].remove("p4")),
    (
        "paredes_sobrepostas",
        lambda d: pav(d)["paredes"].append(
            dict(par(d, "p1"), id="p1b", inicio=[3000, 0], fim=[4000, 0])
        ),
    ),
    ("espessura_divergente", lambda d: par(d, "p4")["espessura"].update(valor=200)),
    ("abertura_fora_da_parede", lambda d: abe(d, "janela-quarto")["largura"].update(valor=3000)),
    ("abertura_acima_do_teto", lambda d: abe(d, "janela-quarto")["peitoril"].update(valor=1500)),
    (
        "aberturas_sobrepostas",
        lambda d: (
            abe(d, "porta-quarto")["distancia_inicio"].update(valor=1000)
            or abe(d, "porta-quarto").update(parede="p1", de="quarto", para="externo")
        ),
    ),
    ("parede_inexistente", lambda d: abe(d, "janela-quarto").update(parede="p99")),
    ("porta_lados", lambda d: abe(d, "porta-banheiro").update(para="externo")),
    ("porta_sentido", lambda d: abe(d, "porta-banheiro").update(abre_para="externo")),
    ("porta_dobradica", lambda d: abe(d, "porta-banheiro").pop("dobradica")),
    ("comodo_sem_porta", lambda d: pav(d)["aberturas"].remove(abe(d, "porta-banheiro"))),
    (
        "instalacao_acima_do_teto",
        lambda d: item(pav(d)["instalacoes"], "chuveiro")["altura"].update(valor=3000),
    ),
    ("parede_inexistente", lambda d: item(pav(d)["instalacoes"], "chuveiro").update(parede="p99")),
    ("sem_rodape", lambda d: pav(d).pop("rodape")),
]


@pytest.mark.parametrize(
    ("codigo", "mutacao"), CASOS, ids=[f"{c}-{i}" for i, (c, _) in enumerate(CASOS)]
)
def test_detecta(
    casa_dict: dict[str, Any],
    montar: Callable[[], Projeto],
    codigo: str,
    mutacao: Callable[[dict[str, Any]], Any],
) -> None:
    mutacao(casa_dict)
    assert codigo in codigos(montar())


def test_porta_de_correr_dispensa_sentido(
    casa_dict: dict[str, Any], montar: Callable[[], Projeto]
) -> None:
    porta = abe(casa_dict, "porta-banheiro")
    porta.update(folha="correr")
    porta.pop("abre_para")
    porta.pop("dobradica")
    assert codigos(montar()) == {"sem_estrutura"}


def test_erros_vem_primeiro_e_tem_local(
    casa_dict: dict[str, Any], montar: Callable[[], Projeto]
) -> None:
    par(casa_dict, "p1").update(lado_a="externo", lado_b="quarto")
    problemas = validar(montar())
    assert problemas[0].severidade is Severidade.ERRO
    texto = str(problemas[0])
    assert "terreo" in texto and "quarto" in texto and "(1750, 0)" in texto


def test_dados_de_comodo(montar: Callable[[], Projeto]) -> None:
    alt = {"valor": 500, "origem": "estimada"}
    movel = {
        "id": "m",
        "tipo": "cama",
        "centro": [0, 0],
        "largura": alt,
        "profundidade": alt,
        "altura": alt,
    }
    dados = {
        "cozinha": DadosComodo.model_validate({"schema_version": 1, "comodo": "cozinha"}),
        "quarto": DadosComodo.model_validate(
            {"schema_version": 1, "comodo": "quarto", "moveis": [movel, movel]}
        ),
    }
    assert {"dados_de_comodo_inexistente", "id_duplicado"} <= codigos(montar(), dados_comodos=dados)


def test_instalacao_usa_pe_direito_do_comodo(
    casa_dict: dict[str, Any], montar: Callable[[], Projeto]
) -> None:
    """Banheiro tem pé-direito próprio (2620) maior que o do pavimento (2600)."""
    luz = item(pav(casa_dict)["instalacoes"], "luz-banheiro")
    luz["altura"]["valor"] = 2620
    assert "instalacao_acima_do_teto" not in codigos(montar())
    luz.update(posicao=[1750, 1300])  # mesma altura, mas no quarto
    assert "instalacao_acima_do_teto" in codigos(montar())
