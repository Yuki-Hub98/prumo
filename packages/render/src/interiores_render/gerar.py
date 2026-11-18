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
import shutil
import subprocess
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


class BlenderIndisponivelError(RuntimeError):
    """Nem Blender local nem a imagem Docker estão disponíveis."""


class RenderFalhouError(RuntimeError):
    """O Blender terminou com erro ou não gravou as saídas esperadas."""


@dataclass(frozen=True)
class ResultadoRender:
    variacao: str
    gerado: bool
    arquivos: tuple[Path, ...]
    preliminar: bool


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
) -> ResultadoRender:
    """Renderiza uma variação do cômodo (pula se a entrada e o gerador não mudaram)."""
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
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TEMPO_MAXIMO, check=False)
    faltando = [a.name for a in esperados if not a.exists()]
    if proc.returncode != 0 or faltando:
        fim = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-15:])
        raise RenderFalhouError(
            f"Blender saiu com {proc.returncode}; faltando: {faltando or 'nada'}\n{fim}"
        )
    meta.write_text(
        json.dumps(
            {
                "chave": chave,
                "gerador": VERSAO_RENDER,
                "hash_entrada": carregado.hash_entrada,
                "preliminar": preliminar,
                "arquivos": [a.name for a in esperados],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return ResultadoRender(variacao, True, esperados, preliminar)
