"""Camadas, cores, espessuras de traço, tamanhos de texto e estilo de cota.

Tamanhos são dados em **mm de papel**; no DXF viram unidades de modelo
multiplicando pela escala (1 unidade = 1 mm do imóvel).
"""

from __future__ import annotations

from dataclasses import dataclass

from ezdxf import units
from ezdxf.document import Drawing
from ezdxf.filemanagement import new as novo_dxf

AVISO_OBRA = "PRELIMINAR — NÃO USAR PARA OBRA"
"""Texto obrigatório quando alguma medida usada é estimada (CLAUDE.md §5.1)."""


@dataclass(frozen=True)
class Camada:
    nome: str
    cor: tuple[int, int, int]
    espessura: int
    """Espessura de traço em centésimos de mm (padrão DXF)."""


CAMADAS = (
    Camada("PAREDE", (0, 0, 0), 50),
    Camada("ABERTURA", (0, 80, 150), 25),
    Camada("MOVEL", (105, 105, 105), 18),
    Camada("ELETRICA", (190, 100, 0), 18),
    Camada("HIDRAULICA", (0, 135, 135), 18),
    Camada("COTA", (50, 50, 50), 13),
    Camada("TEXTO", (0, 0, 0), 18),
    Camada("RESTRICAO", (210, 0, 0), 25),
    Camada("AVISO", (192, 43, 34), 35),  # --erro da identidade visual
)
"""Camadas padronizadas (CLAUDE.md §5.4). Todas existem em todo DXF, mesmo vazias.

HIDRAULICA (água fria/quente, esgoto, ralo) foi incluída a pedido do usuário em
2026-11-17. Gás não é desenhado.
"""

NOMES_CAMADAS = frozenset(c.nome for c in CAMADAS)

COR_PREENCHIMENTO_PAREDE = (90, 90, 90)
ESTILO_TEXTO = "PRUMO"
ESTILO_COTA = "PRUMO"
FONTE = "DejaVuSans.ttf"
TRACEJADO = "TRACEJADO"
"""Tipo de linha para o que está acima do plano de corte (móvel elevado)."""


class Texto:
    """Alturas de texto em mm de papel."""

    TITULO_COMODO = 3.5
    INFO_COMODO = 2.2
    MOVEL = 2.0
    ABERTURA = 1.8
    INSTALACAO = 1.6
    COTA = 2.0
    CARIMBO_TITULO = 3.0
    CARIMBO = 2.2
    CARIMBO_PEQUENO = 1.7
    AVISO = 4.5


def novo_documento(escala: int) -> Drawing:
    """DXF R2018 em milímetros, com as camadas, o estilo de texto e o de cota."""
    doc = novo_dxf("R2018", setup=False)
    doc.units = units.MM
    doc.header["$MEASUREMENT"] = 1  # métrico
    doc.header["$LUNITS"] = 2  # decimal
    doc.header["$INSUNITS"] = units.MM

    for camada in CAMADAS:
        layer = doc.layers.add(camada.nome)
        layer.rgb = camada.cor
        layer.dxf.lineweight = camada.espessura

    doc.styles.add(ESTILO_TEXTO, font=FONTE)
    # traço de 3 mm e espaço de 1,5 mm no papel
    doc.linetypes.add(
        TRACEJADO,
        pattern=[4.5 * escala, 3.0 * escala, -1.5 * escala],
        description="Tracejado __ __ __",
    )

    cota = doc.dimstyles.add(ESTILO_COTA)
    cota.dxf.dimscale = escala
    cota.dxf.dimtxt = Texto.COTA
    cota.dxf.dimtxsty = ESTILO_TEXTO
    cota.dxf.dimtsz = 1.2  # traço oblíquo no lugar de seta
    cota.dxf.dimasz = 1.2
    cota.dxf.dimexe = 1.2  # extensão além da linha de cota
    cota.dxf.dimexo = 1.0  # folga entre o objeto e a linha de chamada
    cota.dxf.dimgap = 0.8
    cota.dxf.dimtad = 1  # texto acima da linha
    cota.dxf.dimtih = 0  # texto alinhado com a cota
    cota.dxf.dimtoh = 0
    cota.dxf.dimdec = 0
    cota.dxf.dimrnd = 1
    cota.dxf.dimzin = 8
    cota.dxf.dimlunit = 2
    cota.dxf.dimclrd = 256  # cor da camada
    cota.dxf.dimclre = 256
    cota.dxf.dimclrt = 256
    return doc
