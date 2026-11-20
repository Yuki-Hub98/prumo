"""PDF da folha em escala exata, com marca d'água PRELIMINAR quando houver estimada."""

from __future__ import annotations

from pathlib import Path

import matplotlib
from ezdxf.addons.drawing.config import (
    BackgroundPolicy,
    Configuration,
    LineweightPolicy,
)
from ezdxf.addons.drawing.frontend import Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.properties import RenderContext
from matplotlib.figure import Figure

from interiores_cad.estilo import AVISO_OBRA
from interiores_cad.folha import MARGEM
from interiores_cad.planta import Desenho

POL = 25.4


def montar_figura(desenho: Desenho) -> Figure:
    """Figura do tamanho da folha; 1 mm de papel = ``escala`` mm do modelo."""
    folha = desenho.folha
    fig = Figure(figsize=(folha.formato.largura / POL, folha.formato.altura / POL))
    ax = fig.add_axes((0, 0, 1, 1))
    config = Configuration(
        background_policy=BackgroundPolicy.WHITE,
        lineweight_policy=LineweightPolicy.ABSOLUTE,
        min_lineweight=0.1,
    )
    Frontend(
        RenderContext(desenho.doc), MatplotlibBackend(ax, adjust_figure=False), config=config
    ).draw_layout(desenho.doc.modelspace(), finalize=True)
    xmin, ymin, xmax, ymax = folha.limites
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("auto")  # a figura já tem a proporção da folha
    ax.set_axis_off()
    if desenho.preliminar:
        # centro da área de desenho (à esquerda do painel)
        cx = (MARGEM + folha.area_desenho[0] / 2) / folha.formato.largura
        fig.text(
            cx,
            0.5,
            AVISO_OBRA,
            fontsize=folha.formato.largura / 420 * 40,
            color=(192 / 255, 43 / 255, 34 / 255),  # --erro da identidade visual
            alpha=0.16,
            rotation=32,
            ha="center",
            va="center",
            weight="bold",
            gid="aviso-obra",
        )
    return fig


def salvar_pdf(desenho: Desenho, caminho: Path) -> None:
    """Grava o PDF sem data de criação, para a mesma entrada dar o mesmo arquivo."""
    fig = montar_figura(desenho)
    with matplotlib.rc_context({"pdf.fonttype": 42}):
        fig.savefig(
            caminho,
            format="pdf",
            metadata={
                "Title": desenho.titulo,
                "Creator": "interiores-cad",
                "Producer": None,
                "CreationDate": None,
            },
        )
