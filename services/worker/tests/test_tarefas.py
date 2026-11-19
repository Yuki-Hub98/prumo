"""Job de render (sem Blender: um renderizador falso)."""

from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from interiores_banco import renders
from interiores_banco.conexao import sessao
from interiores_render import gerar
from interiores_worker import tarefas


def _pedir(engine: Engine, variacao: str = "base") -> int:
    with sessao(engine) as s:
        r, _ = renders.pedir(
            s, "casa", "quarto", variacao, "rascunho", (800, 500, 16), ["perspectiva", "superior"]
        )
        return r.id


def test_render_pronto_com_progresso(banco: Engine, tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(tarefas, "INTERVALO_S", 0.0)
    vistos: list[float] = []

    def falso(carregado: Any, saida: Path, comodo: str, variacao: str, **kw: Any) -> Any:
        assert carregado.projeto.projeto == "casa" and kw["largura"] == 800
        assert kw["subpasta"] == "rascunho"
        for i in (1, 2):
            kw["progresso"](gerar.Progresso(i, 2, 8, 16, 1.5))
            with sessao(banco) as s:
                vistos.append(renders.obter(s, rid).progresso)
        pasta = saida / "casa" / "terreo" / comodo / variacao
        pasta.mkdir(parents=True)
        arqs = tuple(pasta / n for n in ("render-perspectiva.png", "render-superior.png", "q.glb"))
        for a in arqs:
            a.write_bytes(b"png")
        return gerar.ResultadoRender(variacao, True, arqs, True, 3.2)

    rid = _pedir(banco)
    assert tarefas.executar_render(banco, rid, tmp_path / "out", falso) == "pronto"
    assert vistos == [0.25, 0.75]
    with sessao(banco) as s:
        r = renders.obter(s, rid)
        assert (r.status, r.progresso, r.duracao_s, r.em_cache) == ("pronto", 1.0, 3.2, False)
        assert r.arquivos == ["render-perspectiva.png", "render-superior.png", "q.glb"]
        assert r.inicio is not None and r.fim is not None
    assert tarefas.executar_render(banco, rid, tmp_path / "out", falso) == "pronto"  # já feito


def test_render_que_falha_guarda_o_erro(banco: Engine, tmp_path: Path) -> None:
    def quebra(*_: Any, **__: Any) -> Any:
        raise gerar.RenderFalhouError("Blender saiu com 3")

    rid = _pedir(banco)
    assert tarefas.executar_render(banco, rid, tmp_path, quebra) == "erro"
    with sessao(banco) as s:
        r = renders.obter(s, rid)
        assert r.status == "erro" and r.erro is not None and "saiu com 3" in r.erro


def test_render_da_versao_pedida(banco: Engine, tmp_path: Path) -> None:
    """Editar o projeto depois do pedido não muda o que é renderizado."""
    from interiores_banco import repositorio
    from interiores_banco.mapear import Conteudo
    from interiores_core.edicao import alterar_comodo

    rid = _pedir(banco)
    with sessao(banco) as s:
        c, _ = repositorio.ler(s, "casa")
        ed = alterar_comodo(c.projeto, "terreo", "quarto", {"nome": "Mudou"})
        repositorio.gravar(s, Conteudo(ed.projeto, c.comodos), fonte="teste")
    nomes: list[str] = []

    def falso(carregado: Any, *_: Any, **__: Any) -> Any:
        nomes.append(carregado.projeto.pavimentos[0].comodo("quarto").nome)
        raise gerar.RenderFalhouError("parar aqui")

    tarefas.executar_render(banco, rid, tmp_path, falso)
    assert nomes == ["Quarto (suíte)"]
