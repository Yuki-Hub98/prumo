"""Orquestra o render: monta a cena, chama o Blender e guarda as saídas com cache.

O Blender roda do jeito que estiver disponível:

1. ``INTERIORES_BLENDER`` (caminho de um executável) ou ``blender`` no PATH;
2. senão, a imagem Docker ``INTERIORES_BLENDER_IMAGEM`` (padrão
   ``interiores-blender:4.5.16``; construa com ``make blender-imagem``).

Saídas em ``out/<projeto>/<pavimento>/<cômodo>/<variação>/``: ``render-perspectiva.png``,
``render-superior.png``, ``<cômodo>.glb``, ``cena.json`` e ``render.json`` (cache).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from interiores_core.carregar import ProjetoCarregado
from interiores_render import __version__
from interiores_render.cena import VERSAO_CENA, montar_cena

log = logging.getLogger(__name__)

IMAGEM_PADRAO = "interiores-blender:4.5.16"
SCRIPT = Path(__file__).with_name("bpy_cena.py")
VERSAO_RENDER = f"interiores-render {__version__} · cena v{VERSAO_CENA}"
VARIACAO_BASE = "base"
"""Cores padrão; sempre existe, mesmo sem arquivos em ``variacoes/``."""
TEMPO_MAXIMO = 1800

QUALIDADES: dict[str, tuple[int, int, int]] = {
    "rascunho": (800, 500, 16),
    "final": (1600, 1000, 96),
}
"""Largura, altura e amostras de cada qualidade. Rascunho: segundos, para conferir;
final: ~2 min por variação (medido em 2026-11-18, 16 núcleos)."""
IMAGENS_POR_RENDER = 2
"""Perspectiva + vista de cima."""


class BlenderIndisponivelError(RuntimeError):
    """Nem Blender local nem a imagem Docker estão disponíveis."""


class RenderFalhouError(RuntimeError):
    """O Blender terminou com erro ou não gravou as saídas esperadas."""


@dataclass(frozen=True)
class Progresso:
    """Andamento do render, lido da saída do Blender enquanto ele trabalha."""

    imagem: int
    """Imagem atual (1 = perspectiva, 2 = vista de cima)."""
    imagens: int
    amostra: int
    amostras: int
    restante_s: float | None
    """Tempo que o Cycles estima para terminar a imagem atual."""

    @property
    def fracao(self) -> float:
        """0 a 1, contando as imagens já feitas."""
        if not self.imagens:
            return 0.0
        dentro = self.amostra / self.amostras if self.amostras else 0.0
        return min(1.0, ((self.imagem - 1) + dentro) / self.imagens)


_IMAGEM = re.compile(r"^PROGRESSO imagem (\d+) (\d+)")
_AMOSTRA = re.compile(r"Sample (\d+)/(\d+)")
_RESTANTE = re.compile(r"Remaining:(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)")


def ler_progresso(linha: str, atual: Progresso) -> Progresso | None:
    """Novo progresso se a linha do Blender trouxer informação; senão ``None``."""
    m = _IMAGEM.search(linha)
    if m:
        return Progresso(int(m[1]), int(m[2]), 0, atual.amostras, None)
    a = _AMOSTRA.search(linha)
    if not a:
        return None
    r = _RESTANTE.search(linha)
    restante = None
    if r:
        restante = int(r[1] or 0) * 3600 + int(r[2]) * 60 + float(r[3])
    return Progresso(atual.imagem, atual.imagens, int(a[1]), int(a[2]), restante)


def _rodar(
    cmd: list[str], amostras: int, progresso: Callable[[Progresso], None] | None
) -> tuple[int, str]:
    """Roda o Blender lendo a saída linha a linha (progresso ao vivo)."""
    atual = Progresso(1, 2, 0, amostras, None)
    linhas: list[str] = []
    limite = time.monotonic() + TEMPO_MAXIMO
    with subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    ) as proc:
        assert proc.stdout is not None
        for linha in proc.stdout:
            linhas.append(linha)
            del linhas[:-200]
            novo = ler_progresso(linha, atual)
            if novo is not None:
                atual = novo
                if progresso is not None:
                    progresso(atual)
            if time.monotonic() > limite:
                proc.kill()
                break
        codigo = proc.wait()
    return codigo, "".join(linhas)


@dataclass(frozen=True)
class ResultadoRender:
    variacao: str
    gerado: bool
    arquivos: tuple[Path, ...]
    preliminar: bool
    duracao_s: float | None = None
    """Quanto o Blender levou (None se veio do cache)."""


def comando_blender(cena: Path, pasta: Path) -> list[str]:
    """Linha de comando para renderizar ``cena`` gravando em ``pasta``."""
    local = os.environ.get("INTERIORES_BLENDER") or shutil.which("blender")
    if local:
        return [
            local,
            "--background",
            "--factory-startup",
            "--python",
            str(SCRIPT),
            "--",
            str(cena),
            str(pasta),
        ]
    imagem = os.environ.get("INTERIORES_BLENDER_IMAGEM", IMAGEM_PADRAO)
    if not shutil.which("docker"):
        raise BlenderIndisponivelError(
            "Blender não encontrado: instale o Blender, defina INTERIORES_BLENDER ou use Docker "
            "(make blender-imagem)"
        )
    existe = (
        subprocess.run(
            ["docker", "image", "inspect", imagem], capture_output=True, check=False
        ).returncode
        == 0
    )
    if not existe:
        raise BlenderIndisponivelError(
            f"imagem Docker '{imagem}' não existe: rode make blender-imagem"
        )
    usuario = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "0:0"
    return [
        "docker",
        "run",
        "--rm",
        # terminal (-t): sem ele a saída do Blender chega em blocos e a barra de
        # progresso pula; com ele vem linha a linha
        "-t",
        "--user",
        usuario,
        "-v",
        f"{SCRIPT.parent}:/script:ro",
        "-v",
        f"{pasta.resolve()}:/trabalho",
        imagem,
        "--python",
        f"/script/{SCRIPT.name}",
        "--",
        f"/trabalho/{cena.name}",
        "/trabalho",
    ]


def variacoes_do_comodo(carregado: ProjetoCarregado, comodo: str) -> list[str]:
    """``base`` e as variações em ``variacoes/<comodo>/``, em ordem."""
    return [VARIACAO_BASE, *sorted(carregado.variacoes.get(comodo, {}))]


def renderizar(
    carregado: ProjetoCarregado,
    saida: Path,
    comodo: str,
    variacao: str = VARIACAO_BASE,
    forcar: bool = False,
    largura: int = 1600,
    altura: int = 1000,
    amostras: int = 96,
    progresso: Callable[[Progresso], None] | None = None,
    subpasta: str | None = None,
) -> ResultadoRender:
    """Renderiza uma variação do cômodo (pula se a entrada e o gerador não mudaram).

    ``progresso`` é chamado a cada linha útil do Blender (imagem, amostra, tempo
    restante) — a fila usa para a barra de progresso da tela. ``subpasta`` separa
    saídas que não podem sobrescrever a principal (ex.: ``rascunho``).
    """
    pav = carregado.projeto.pavimento_do_comodo(comodo)
    if pav is None:
        raise KeyError(f"cômodo '{comodo}' não existe no projeto")
    cena = montar_cena(
        carregado,
        comodo,
        None if variacao == VARIACAO_BASE else variacao,
        largura,
        altura,
        amostras,
    )
    pasta = saida / carregado.projeto.projeto / pav.id / comodo / variacao
    if subpasta:
        pasta = pasta / subpasta
    esperados = (
        pasta / "render-perspectiva.png",
        pasta / "render-superior.png",
        pasta / f"{comodo}.glb",
    )
    texto_cena = json.dumps(cena, ensure_ascii=False, sort_keys=True, indent=1)
    # o próprio script do Blender entra na chave: mudou o script, regera
    chave = hashlib.sha256(
        f"{VERSAO_RENDER}\0{texto_cena}\0".encode() + SCRIPT.read_bytes()
    ).hexdigest()
    meta = pasta / "render.json"
    preliminar = cena["aviso"] is not None
    atual = (
        not forcar
        and meta.exists()
        and all(a.exists() for a in esperados)
        and json.loads(meta.read_text(encoding="utf-8")).get("chave") == chave
    )
    if atual:
        return ResultadoRender(variacao, False, esperados, preliminar)

    pasta.mkdir(parents=True, exist_ok=True)
    arquivo_cena = pasta / "cena.json"
    arquivo_cena.write_text(texto_cena + "\n", encoding="utf-8")
    for velho in esperados:
        velho.unlink(missing_ok=True)
    cmd = comando_blender(arquivo_cena, pasta)
    log.info("renderizando %s/%s com %s", comodo, variacao, cmd[0])
    inicio = time.monotonic()
    codigo, saida_blender = _rodar(cmd, amostras, progresso)
    duracao = round(time.monotonic() - inicio, 1)
    faltando = [a.name for a in esperados if not a.exists()]
    if codigo != 0 or faltando:
        fim = "\n".join(saida_blender.strip().splitlines()[-15:])
        raise RenderFalhouError(f"Blender saiu com {codigo}; faltando: {faltando or 'nada'}\n{fim}")
    meta.write_text(
        json.dumps(
            {
                "chave": chave,
                "gerador": VERSAO_RENDER,
                "hash_entrada": carregado.hash_entrada,
                "preliminar": preliminar,
                "arquivos": [a.name for a in esperados],
                "duracao_s": duracao,
                "largura": largura,
                "altura": altura,
                "amostras": amostras,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    log.info("render %s/%s em %.1f s", comodo, variacao, duracao)
    return ResultadoRender(variacao, True, esperados, preliminar, duracao)
