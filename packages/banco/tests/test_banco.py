"""Banco como fonte da verdade: ida e volta, versões, histórico, sincronização."""

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from interiores_banco import arquivos, repositorio
from interiores_banco import tabelas as t
from interiores_banco.conexao import url_do_ambiente
from interiores_banco.mapear import Conteudo
from interiores_core import edicao
from interiores_core.carregar import carregar
from interiores_core.medidas import Medida, Origem
from interiores_core.modelo import Movel
from interiores_core.planejado import construcao_sugerida


def _completa(pasta: Path) -> Path:
    """Acrescenta à casa o que a cópia congelada não tem: variação, regras.toml e
    um planejado com construção (medidas aninhadas)."""
    var = {"schema_version": 1, "comodo": "quarto", "nome": "Escura",
           "cores": {"parede": "#334455", "moveis": {"cama": "#aa0000"}}}  # fmt: skip
    (pasta / "variacoes" / "quarto").mkdir(parents=True)
    (pasta / "variacoes" / "quarto" / "escura.json").write_text(json.dumps(var))
    (pasta / "regras.toml").write_text("[gerais]\npassagem_min = 750\n")
    arq = pasta / "comodos" / "quarto.json"
    dados = json.loads(arq.read_text())
    gr = next(m for m in dados["moveis"] if m["id"] == "guarda-roupa")
    gr["construcao"] = construcao_sugerida(Movel.model_validate(gr))
    arq.write_text(json.dumps(dados))
    return pasta


def test_ida_e_volta_sem_perder_nada(sessao: Session, casa: Path) -> None:
    original = Conteudo.de_carregado(carregar(_completa(casa)))
    gravado = repositorio.gravar(sessao, original, fonte="teste")
    assert gravado.versao == 1
    sessao.expire_all()
    de_volta, versao = repositorio.ler(sessao, "casa")
    assert versao == 1
    assert de_volta == original
    assert de_volta.como_dict() == original.como_dict()


def test_tabelas_pesquisaveis(sessao: Session, casa: Path) -> None:
    repositorio.gravar(sessao, Conteudo.de_carregado(carregar(casa)), fonte="teste")
    portas_banheiro = sessao.scalars(
        select(t.Abertura.codigo).where(t.Abertura.tipo == "porta", t.Abertura.para == "banheiro")
    ).all()
    assert portas_banheiro == ["porta-banheiro"]
    estimadas = sessao.scalars(
        select(t.Medida.caminho).where(t.Medida.origem == "estimada", t.Medida.entidade == "parede")
    ).all()
    assert "pavimentos[terreo].paredes[p1].espessura" in estimadas
    cama = sessao.scalars(
        select(t.Medida).where(t.Medida.caminho.like("%moveis[cama].largura"))
    ).one()
    assert (cama.comodo, cama.valor) == ("quarto", 1380)
    tomadas = sessao.scalars(select(t.Instalacao).where(t.Instalacao.tipo == "tomada")).all()
    assert {i.parede for i in tomadas} == {"p2"}


def test_edicao_vira_versao_com_historico(sessao: Session, casa: Path) -> None:
    base = Conteudo.de_carregado(carregar(casa))
    repositorio.gravar(sessao, base, fonte="importacao")
    ed = edicao.alterar_parede(
        base.projeto, "terreo", "p1", {"espessura": Medida(valor=140, origem=Origem.TRENA)}
    )
    novo = Conteudo(ed.projeto, base.comodos, base.variacoes, base.regras_toml)
    gravado = repositorio.gravar(
        sessao, novo, fonte="api", operacao="alterar_parede", versao_esperada=1,
        alteracoes=ed.alteracoes,
    )  # fmt: skip
    assert gravado.versao == 2
    hist = sessao.scalars(select(t.Historico).where(t.Historico.versao == 2)).one()
    assert (hist.operacao, hist.caminho) == (
        "alterar_parede",
        "pavimentos[terreo].paredes[p1].espessura",
    )
    assert (hist.antes["valor"], hist.depois["valor"]) == (150, 140)
    assert repositorio.snapshot(sessao, "casa", 1) == base
    assert repositorio.ler(sessao, "casa")[0] == novo

    with pytest.raises(repositorio.ConflitoDeVersaoError):  # edição em cima da versão velha
        repositorio.gravar(sessao, base, fonte="api", versao_esperada=1)
    assert repositorio.gravar(sessao, novo, fonte="api").alteracoes == []  # nada mudou
    assert repositorio.ler(sessao, "casa")[1] == 2


def test_diferenca_calculada_sem_edicao(sessao: Session, casa: Path) -> None:
    base = Conteudo.de_carregado(carregar(casa))
    repositorio.gravar(sessao, base, fonte="teste")
    ed = edicao.remover_abertura(base.projeto, "terreo", "basculante-banheiro")
    g = repositorio.gravar(sessao, Conteudo(ed.projeto, base.comodos), fonte="teste")
    assert [a.caminho for a in g.alteracoes] == [
        "projeto.pavimentos[terreo].aberturas[basculante-banheiro]"
    ]


def test_importar_e_exportar(sessao: Session, casa: Path, tmp_path: Path) -> None:
    r = arquivos.importar(sessao, casa)
    assert (r.versao, r.mudou) == (1, True)
    assert not arquivos.importar(sessao, casa).mudou  # arquivos iguais: nada a fazer

    destino = tmp_path / "exportado"
    assert arquivos.exportar(sessao, "casa", destino).mudou
    assert carregar(destino).projeto == carregar(casa).projeto
    assert carregar(destino).dados_comodos == carregar(casa).dados_comodos


def test_sincronizacao_nao_atropela(sessao: Session, casa: Path) -> None:
    arquivos.importar(sessao, casa)
    # 1) editado no banco → exportar atualiza os arquivos
    conteudo, _ = repositorio.ler(sessao, "casa")
    ed = edicao.alterar_comodo(conteudo.projeto, "terreo", "quarto", {"nome": "Suíte"})
    repositorio.gravar(sessao, Conteudo(ed.projeto, conteudo.comodos), fonte="api")
    assert arquivos.exportar(sessao, "casa", casa).versao == 2
    assert carregar(casa).projeto.pavimentos[0].comodo("quarto").nome == "Suíte"  # type: ignore[union-attr]

    # 2) editado nos arquivos → importar vira versão 3
    p = edicao.alterar_comodo(edicao.ler_projeto(casa), "terreo", "quarto", {"piso": "taco"})
    edicao.gravar_projeto(casa, p.projeto)
    assert arquivos.importar(sessao, casa).versao == 3

    # 3) editado nos dois lados → conflito, nos dois sentidos
    conteudo, _ = repositorio.ler(sessao, "casa")
    ed = edicao.alterar_comodo(conteudo.projeto, "terreo", "quarto", {"teto": "gesso"})
    repositorio.gravar(sessao, Conteudo(ed.projeto, conteudo.comodos), fonte="api")
    p = edicao.alterar_comodo(edicao.ler_projeto(casa), "terreo", "quarto", {"teto": "laje"})
    edicao.gravar_projeto(casa, p.projeto)
    with pytest.raises(arquivos.ConflitoDeSincronizacaoError):
        arquivos.importar(sessao, casa)
    with pytest.raises(arquivos.ConflitoDeSincronizacaoError):
        arquivos.exportar(sessao, "casa", casa)
    assert arquivos.importar(sessao, casa, forcar=True).versao == 5


def test_exportar_remove_comodo_que_saiu(sessao: Session, casa: Path) -> None:
    arquivos.importar(sessao, _completa(casa))
    conteudo, _ = repositorio.ler(sessao, "casa")
    ed = edicao.remover_comodo(conteudo.projeto, "terreo", "quarto")
    repositorio.gravar(sessao, Conteudo(ed.projeto), fonte="api")
    arquivos.exportar(sessao, "casa", casa)
    assert not (casa / "comodos" / "quarto.json").exists()
    assert not (casa / "variacoes" / "quarto" / "escura.json").exists()
    assert not (casa / "regras.toml").exists()


def test_dados_de_comodo_inexistente_recusa(sessao: Session, casa: Path) -> None:
    base = Conteudo.de_carregado(carregar(casa))
    ed = edicao.remover_comodo(base.projeto, "terreo", "quarto")
    with pytest.raises(ValueError, match="cômodo inexistente"):
        repositorio.gravar(sessao, Conteudo(ed.projeto, base.comodos), fonte="teste")


def test_url_do_ambiente() -> None:
    env = {
        "POSTGRES_USER": "u",
        "POSTGRES_PASSWORD": "s",
        "POSTGRES_DB": "d",
        "POSTGRES_PORT": "5433",
    }
    assert url_do_ambiente(env) == "postgresql+psycopg://u:s@localhost:5433/d"
    assert url_do_ambiente({"INTERIORES_BANCO_URL": "x://y"}) == "x://y"
    with pytest.raises(RuntimeError, match="POSTGRES_DB"):
        url_do_ambiente({"POSTGRES_USER": "u", "POSTGRES_PASSWORD": "s"})


def test_migracoes_batem_com_as_tabelas(sessao: Session) -> None:
    """Mudou ``tabelas.py`` sem criar migração? Este teste quebra.

    Crie com: ``uv run python -c "from interiores_banco.migrar import criar_revisao;
    criar_revisao('<url de um banco atualizado>', '<mensagem>')"``.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    contexto = MigrationContext.configure(
        sessao.connection(), opts={"compare_type": True, "compare_server_default": True}
    )
    assert compare_metadata(contexto, t.Base.metadata) == []
