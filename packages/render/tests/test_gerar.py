"""Orquestração do render com um "Blender falso" (e o de verdade, sob demanda)."""

import os
import shutil
import stat
from pathlib import Path

import pytest

from interiores_core.carregar import carregar
from interiores_render import gerar

DADOS = Path(__file__).resolve().parents[2] / "core" / "tests" / "dados" / "casa"

FALSO = """#!/usr/bin/env python3
import json, sys
from pathlib import Path
args = sys.argv[sys.argv.index("--") + 1:]
cena = json.loads(Path(args[0]).read_text())
pasta = Path(args[1])
(pasta / "chamadas.txt").open("a").write("x\\n")
for i, cam in ((1, "perspectiva"), (2, "superior")):
    print(f"PROGRESSO imagem {i} 2 {cam}", flush=True)
    print("Fra:1 Mem:12M | Time:00:01.00 | Remaining:00:03.50 | Sample 48/96", flush=True)
if cena["comodo"] == "banheiro":
    sys.exit(3)
for nome in ("render-perspectiva.png", "render-superior.png", cena["comodo"] + ".glb"):
    (pasta / nome).write_bytes(b"ok")
"""


@pytest.fixture
def blender_falso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    exe = tmp_path / "blender-falso"
    exe.write_text(FALSO, encoding="utf-8")  # shebang sem caminho: o do venv tem espaço
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("INTERIORES_BLENDER", str(exe))
    return exe


def test_render_com_cache(blender_falso: Path, tmp_path: Path) -> None:
    c = carregar(DADOS)
    r = gerar.renderizar(c, tmp_path / "out", "quarto")
    pasta = tmp_path / "out/casa/terreo/quarto/base"
    assert r.gerado and r.preliminar and r.arquivos[0] == pasta / "render-perspectiva.png"
    assert (pasta / "cena.json").exists() and (pasta / "render.json").exists()
    assert not gerar.renderizar(c, tmp_path / "out", "quarto").gerado
    assert (pasta / "chamadas.txt").read_text().count("x") == 1
    assert gerar.renderizar(c, tmp_path / "out", "quarto", forcar=True).gerado
    assert gerar.renderizar(c, tmp_path / "out", "quarto", amostras=8).gerado  # cena mudou


def test_rascunho_nao_sobrescreve_o_final(blender_falso: Path, tmp_path: Path) -> None:
    c = carregar(DADOS)
    final = gerar.renderizar(c, tmp_path, "quarto")
    rascunho = gerar.renderizar(c, tmp_path, "quarto", amostras=16, subpasta="rascunho")
    assert rascunho.arquivos[0].parent == final.arquivos[0].parent / "rascunho"
    assert all(a.exists() for a in (*final.arquivos, *rascunho.arquivos))


def test_progresso_ao_vivo(blender_falso: Path, tmp_path: Path) -> None:
    vistos: list[gerar.Progresso] = []
    r = gerar.renderizar(carregar(DADOS), tmp_path, "quarto", progresso=vistos.append)
    assert [(p.imagem, p.amostra) for p in vistos] == [(1, 0), (1, 48), (2, 0), (2, 48)]
    assert vistos[1].restante_s == 3.5 and vistos[-1].fracao == 0.75
    assert r.duracao_s is not None and r.duracao_s >= 0


def test_ler_progresso() -> None:
    p0 = gerar.Progresso(1, 2, 0, 96, None)
    linha = "Fra:1 Mem:80M | Time:00:12.40 | Remaining:01:05.25 | Mem:9M | Sample 32/96"
    p = gerar.ler_progresso(linha, p0)
    assert p is not None and (p.amostra, p.amostras, p.restante_s) == (32, 96, 65.25)
    assert round(p.fracao, 3) == round(32 / 96 / 2, 3)
    assert gerar.ler_progresso("Fra:1 Mem | Sample 1/16", p0).restante_s is None  # type: ignore[union-attr]
    longa = gerar.ler_progresso("Remaining:1:02:03.5 | Sample 5/96", p0)
    assert longa is not None and longa.restante_s == 3723.5
    assert gerar.ler_progresso("Read blend: /tmp/x", p0) is None
    assert gerar.Progresso(0, 0, 0, 0, None).fracao == 0.0


def test_render_que_falha(blender_falso: Path, tmp_path: Path) -> None:
    with pytest.raises(gerar.RenderFalhouError, match="saiu com 3"):
        gerar.renderizar(carregar(DADOS), tmp_path, "banheiro")
    with pytest.raises(KeyError):
        gerar.renderizar(carregar(DADOS), tmp_path, "cozinha")


def test_variacoes_do_comodo(tmp_path: Path) -> None:
    shutil.copytree(DADOS, tmp_path / "casa")
    pasta = tmp_path / "casa/variacoes/quarto"
    pasta.mkdir(parents=True)
    for nome in ("b", "a"):
        (pasta / f"{nome}.json").write_text('{"schema_version": 1, "comodo": "quarto"}', "utf-8")
    assert gerar.variacoes_do_comodo(carregar(tmp_path / "casa"), "quarto") == ["base", "a", "b"]


def test_comando_docker_e_indisponivel(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("INTERIORES_BLENDER", raising=False)
    caminhos = {"docker": "/usr/bin/docker"}
    monkeypatch.setattr(gerar.shutil, "which", lambda nome: caminhos.get(nome))

    class Feito:
        returncode = 0

    monkeypatch.setattr(gerar.subprocess, "run", lambda *a, **k: Feito())
    cmd = gerar.comando_blender(tmp_path / "cena.json", tmp_path)
    assert cmd[:3] == ["docker", "run", "--rm"] and gerar.IMAGEM_PADRAO in cmd
    assert f"{tmp_path.resolve()}:/trabalho" in cmd

    Feito.returncode = 1  # imagem não construída
    with pytest.raises(gerar.BlenderIndisponivelError, match="make blender-imagem"):
        gerar.comando_blender(tmp_path / "cena.json", tmp_path)
    caminhos.clear()  # nem docker
    with pytest.raises(gerar.BlenderIndisponivelError, match="Blender não encontrado"):
        gerar.comando_blender(tmp_path / "cena.json", tmp_path)


def _blender_disponivel() -> bool:
    if os.environ.get("PRUMO_TESTAR_BLENDER") != "1":
        return False
    try:
        gerar.comando_blender(Path("x"), Path())
    except gerar.BlenderIndisponivelError:
        return False
    return True


@pytest.mark.blender
@pytest.mark.skipif(not _blender_disponivel(), reason="defina PRUMO_TESTAR_BLENDER=1 (lento)")
def test_render_de_verdade(tmp_path: Path) -> None:
    r = gerar.renderizar(carregar(DADOS), tmp_path, "quarto", largura=320, altura=200, amostras=4)
    assert r.gerado
    png = r.arquivos[0].read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert r.arquivos[2].read_bytes()[:4] == b"glTF"
