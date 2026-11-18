"""Regras do quarto (CLAUDE.md §6, "Por tipo de cômodo")."""

from __future__ import annotations

from interiores_core.regras.contexto import Contexto, Regra, de_tipo, lado_local, onde_na_planta
from interiores_core.validacao import Severidade

LIMITES = {"lateral_cama": 600, "frente_guarda_roupa": 900, "largura_cama_casal": 1200}
"""Padrões em mm; o ``regras.toml`` do projeto pode sobrescrever (seção ``[quarto]``).

``largura_cama_casal``: a partir dela a cama precisa de circulação dos dois lados;
abaixo (solteiro), basta um.
"""


def lateral_cama(ctx: Contexto) -> None:
    """Circulação ao lado da cama: os dois lados na de casal, ao menos um na de solteiro."""
    limite = ctx.limites["lateral_cama"]
    for cama in de_tipo(ctx.moveis, "cama"):
        nome = cama.nome or cama.id
        medidas = []
        for qual in ("esquerda", "direita"):
            lado, direcao = lado_local(cama, qual)
            medidas.append((ctx.folga(lado, direcao, exceto=cama.id), lado, direcao))
        casal = cama.largura.valor >= ctx.limites["largura_cama_casal"]
        curtas = [m for m in medidas if m[0] < limite]
        if not casal and len(curtas) < len(medidas):
            continue  # solteiro com um lado livre basta
        for folga, lado, direcao in curtas:
            ctx.add(
                Severidade.AVISO,
                "lateral_cama",
                f"lateral de '{nome}' {onde_na_planta(direcao)} tem {folga:.0f} mm livres; "
                f"mínimo {limite}" + ("" if casal else " (nenhum lado livre)"),
                elemento=cama.id,
                regiao=ctx.faixa(lado, direcao, limite),
            )


def frente_guarda_roupa(ctx: Contexto) -> None:
    """Espaço à frente de guarda-roupa com porta de abrir: limite ou folha + 100."""
    for gr in de_tipo(ctx.moveis, "guarda_roupa"):
        if gr.portas == "correr":
            continue  # porta de correr: vale só a passagem livre geral
        nome = gr.nome or gr.id
        limite = ctx.limites["frente_guarda_roupa"]
        if gr.largura_porta is not None:
            limite = max(limite, gr.largura_porta.valor + 100)
        if gr.portas is None:
            ctx.add(
                Severidade.INFO,
                "portas_nao_informadas",
                f"tipo de porta de '{nome}' não informado; considerado de abrir "
                f"(informe `portas`: abrir ou correr)",
                elemento=gr.id,
            )
        lado, direcao = lado_local(gr, "frente")
        folga = ctx.folga(lado, direcao, exceto=gr.id)
        if folga < limite:
            ctx.add(
                Severidade.AVISO,
                "frente_guarda_roupa",
                f"frente de '{nome}' tem {folga:.0f} mm livres; mínimo {limite} (porta de abrir)",
                elemento=gr.id,
                regiao=ctx.faixa(lado, direcao, limite),
            )


REGRAS: list[Regra] = [lateral_cama, frente_guarda_roupa]
