"""Comparação lado a lado das variações de um cômodo (.png), com Pillow.

Junta a imagem pronta de cada variação (``out/<p>/<pav>/<cômodo>/<variação>/render-<vista>.png``;
sem o render final, o rascunho) numa grade com o nome de cada uma em cima. As imagens já
trazem a faixa PRELIMINAR quando há medida estimada; a montagem não esconde nada delas.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from interiores_core.carregar import ProjetoCarregado

LARGURA_QUADRO = 800
"""px de cada imagem na montagem (as maiores são reduzidas)."""
FAIXA = 44
MARGEM = 16
FUNDO = (245, 245, 244)
TEXTO = (28, 25, 23)
CINZA = (120, 113, 108)


def imagem_da_variacao(pasta_comodo: Path, variacao: str, vista: str) -> Path | None:
    """O render final da variação nessa vista ou, se não houver, o rascunho."""
    for sub in ("", "rascunho"):
        arq = pasta_comodo / variacao / sub / f"render-{vista}.png"
        if arq.is_file():
            return arq
    return None


def colunas_para(n: int) -> int:
    """2 lado a lado; de 5 em diante, 3 por linha."""
    return 1 if n <= 1 else 2 if n <= 4 else 3


def montar(
    quadros: Sequence[tuple[str, Image.Image]], titulo: str, rodape: str = ""
) -> Image.Image:
    """Grade com o nome de cada quadro em cima, o título no topo e um rodapé opcional."""
    if not quadros:
        raise ValueError("nada para comparar")
    cols = colunas_para(len(quadros))
    linhas = math.ceil(len(quadros) / cols)
    reduzidos = []
    for rotulo, img in quadros:
        escala = LARGURA_QUADRO / img.width
        reduzidos.append(
            (rotulo, img.convert("RGB").resize((LARGURA_QUADRO, round(img.height * escala))))
        )
    alto = max(i.height for _, i in reduzidos)
    largura = MARGEM + cols * (LARGURA_QUADRO + MARGEM)
    altura = FAIXA + MARGEM + linhas * (FAIXA + alto + MARGEM) + (FAIXA if rodape else 0)
    tela = Image.new("RGB", (largura, altura), FUNDO)
    d = ImageDraw.Draw(tela)
    fonte_titulo = ImageFont.load_default(size=24)
    fonte = ImageFont.load_default(size=20)
    d.text((MARGEM, FAIXA / 2 + 4), titulo, fill=TEXTO, font=fonte_titulo, anchor="lm")
    for k, (rotulo, img) in enumerate(reduzidos):
        x = MARGEM + (k % cols) * (LARGURA_QUADRO + MARGEM)
        y = FAIXA + MARGEM + (k // cols) * (FAIXA + alto + MARGEM)
        d.text((x, y + FAIXA / 2), rotulo, fill=TEXTO, font=fonte, anchor="lm")
        tela.paste(img, (x, y + FAIXA))
    if rodape:
        d.text((MARGEM, altura - FAIXA / 2), rodape, fill=CINZA, font=fonte, anchor="lm")
    return tela


def gerar_comparacao(
    carregado: ProjetoCarregado,
    saida: Path,
    comodo: str,
    variacoes: Sequence[str],
    vista: str = "perspectiva",
    data: date | None = None,
) -> tuple[Path, list[str]]:
    """Grava ``out/<p>/<pav>/<cômodo>/_comparacao/comparacao-<vista>.png``.

    Devolve (caminho, variações sem imagem). Levanta ``ValueError`` se menos de duas
    variações tiverem imagem nessa vista (rode o render antes).
    """
    pav = carregado.projeto.pavimento_do_comodo(comodo)
    if pav is None:
        raise KeyError(f"cômodo '{comodo}' não existe no projeto")
    c = pav.comodo(comodo)
    assert c is not None
    pasta_comodo = saida / carregado.projeto.projeto / pav.id / comodo
    quadros, faltando = [], []
    for v in variacoes:
        arq = imagem_da_variacao(pasta_comodo, v, vista)
        if arq is None:
            faltando.append(v)
            continue
        var = carregado.variacoes.get(comodo, {}).get(v)
        nome = "base (cores padrão)" if v == "base" else (var.nome if var and var.nome else v)
        rascunho = " · rascunho" if arq.parent.name == "rascunho" else ""
        with Image.open(arq) as img:
            quadros.append((f"{nome}{rascunho}", img.copy()))
    if len(quadros) < 2:
        raise ValueError(
            f"preciso de pelo menos duas variações com imagem '{vista}' "
            f"(sem imagem: {', '.join(faltando) or 'nenhuma'}); rode o render antes"
        )
    data = data or date.today()
    titulo = f"{carregado.projeto.projeto} · {c.nome} · {vista}"
    rodape = f"{data.isoformat()} · hash {carregado.hash_curto}"
    destino = pasta_comodo / "_comparacao" / f"comparacao-{vista}.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    montar(quadros, titulo, rodape).save(destino)
    return destino, faltando
