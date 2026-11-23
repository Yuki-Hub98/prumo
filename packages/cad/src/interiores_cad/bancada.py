"""Desenho técnico da bancada/mesa planejada: vista superior e vista de frente de cada
trecho (costas e, no L, o braço), cotadas.

Coordenadas do DXF em mm (1 unidade = 1 mm). As vistas de frente ficam embaixo, lado a
lado, com o piso em y = 0; a vista superior fica em cima delas, com a frente para baixo
(do jeito que se olha a bancada de frente) e o x da esquerda de quem olha.
"""

from __future__ import annotations

import itertools
from datetime import date

from interiores_cad.estilo import TRACEJADO, Texto, novo_documento
from interiores_cad.folha import DadosCarimbo, desenhar_folha, escolher_folha
from interiores_cad.movel import COR_CHAPA, VERSAO_MOVEL, _Vistas
from interiores_cad.planta import Desenho
from interiores_core import bancada, geometria
from interiores_core.carregar import ProjetoCarregado
from interiores_core.medidas import medidas_estimadas
from interiores_core.modelo import Movel
from interiores_core.planejado import Retangulo
from interiores_core.regras import checar

CHEIO = {"tampo", "perna", "painel", "lateral", "base", "divisoria", "rodape", "prateleira"}
NOME_TRECHO = {"costas": "TRECHO DAS COSTAS", "braco": "BRAÇO DO L"}


class _VistasBancada(_Vistas):
    calc: bancada.BancadaCalculada

    def chapa(self, x: float, y: float, w: float, h: float) -> None:
        pts = self.ret(x, y, w, h)
        hachura = self.msp.add_hatch(dxfattribs={"layer": "MOVEL"})
        hachura.rgb = COR_CHAPA
        hachura.paths.add_polyline_path(pts, is_closed=True)

    def frente_trecho(self, nome: str, x0: float) -> float:
        """Vista de frente do trecho a partir de ``x0``; devolve a largura dela."""
        t = next(t for t in self.calc.trechos if t.nome == nome)
        vista = self.calc.vistas[nome]
        for r in vista:
            movido = Retangulo(r.tipo, x0 + r.x, r.y, r.largura, r.altura, r.rotulo, r.vao)
            if r.tipo in CHEIO:
                self.chapa(movido.x, movido.y, movido.largura, movido.altura)
            elif r.tipo in ("gaveta", "nicho", "cabideiro"):
                self.espaco(movido)
            elif r.tipo == "porta":
                self.ret(movido.x, movido.y, movido.largura, movido.altura, linetype=TRACEJADO)
        alt = self.alt
        self.titulo(f"FRENTE — {NOME_TRECHO[nome]}", "módulos sem portas; portas tracejadas",
                    x0 + t.comprimento / 2)  # fmt: skip
        self.cota((x0, 0), (x0 + t.comprimento, 0), (x0, -self.mm(8)))
        self.cota((x0, 0), (x0, alt), (x0 - self.mm(8), 0))
        # posição de cada módulo e de cada perna, em cadeia, em cima do tampo
        bordas: set[float] = set()
        for r in vista:
            if r.tipo in ("perna", "painel"):
                bordas |= {round(x0 + r.x, 1), round(x0 + r.x + r.largura, 1)}
        for m in self.calc.modulos:
            if m.trecho == nome:
                ini = x0 + bancada.x_da_vista(t, m.u0, m.u1)
                bordas |= {round(ini, 1), round(ini + m.u1 - m.u0, 1)}
        marcas = sorted(bordas)
        pontos = [x0, *(m for m in marcas if x0 < m < x0 + t.comprimento), x0 + t.comprimento]
        for a, b in itertools.pairwise(pontos):
            if b - a > 1:
                self.cota((a, alt), (b, alt), (a, alt + self.mm(6)))
        return t.comprimento

    def superior(self, y0: float) -> None:
        """Vista de cima: tampo, módulos (tracejados, sob o tampo) e pernas, com a frente
        para baixo; x da esquerda de quem olha (x local invertido)."""
        m = self.calc.movel
        w, d = m.largura.valor / 2, m.profundidade.valor / 2

        def para_folha(x: float, y: float) -> tuple[float, float]:
            return (w - x, y0 + d - y)  # frente (+y) para baixo, esquerda de quem olha = +x

        contorno = [para_folha(x, y) for x, y in geometria.contorno_local(m).exterior.coords[:-1]]
        self.msp.add_lwpolyline(contorno, close=True, dxfattribs={"layer": "MOVEL"})
        trechos = {t.nome: t for t in self.calc.trechos}
        for mod in self.calc.modulos:
            t = trechos[mod.trecho]
            pts = [
                para_folha(*t.ponto(u, v))
                for u, v in (
                    (mod.u0, 0),
                    (mod.u1, 0),
                    (mod.u1, mod.profundidade),
                    (mod.u0, mod.profundidade),
                )
            ]
            self.msp.add_lwpolyline(
                pts, close=True, dxfattribs={"layer": "MOVEL", "linetype": TRACEJADO}
            )
            cx = sum(p[0] for p in pts) / 4
            cy = sum(p[1] for p in pts) / 4
            self.texto(mod.modulo.id, (cx, cy), Texto.MOVEL, "MOVEL")
        assert m.bancada is not None
        e = m.bancada.tampo.espessura.valor
        for p in self.calc.pernas:
            t = trechos[p.trecho]
            u, v = t.uv(p.x, p.y)
            du, dv = (e / 2, p.comprimento / 2) if p.painel else (bancada.PERNA / 2,) * 2
            pts = [
                para_folha(*t.ponto(a, b))
                for a, b in (
                    (u - du, v - dv),
                    (u + du, v - dv),
                    (u + du, v + dv),
                    (u - du, v + dv),
                )
            ]
            self.msp.add_lwpolyline(
                pts, close=True, dxfattribs={"layer": "MOVEL", "linetype": TRACEJADO}
            )
        larg, prof = 2 * w, 2 * d
        self.cota((0, y0), (larg, y0), (0, y0 - self.mm(6)))
        self.cota((larg, y0), (larg, y0 + prof), (larg + self.mm(8), y0))
        if m.forma == "L":
            b = bancada.braco(m)
            self.cota((0, y0 + prof - b), (0, y0 + prof), (-self.mm(8), y0))
        self.texto("VISTA SUPERIOR", (larg / 2, y0 + prof + self.mm(8)), Texto.CARIMBO)
        self.texto(
            "frente para baixo · módulos e pernas tracejados (sob o tampo)",
            (larg / 2, y0 + prof + self.mm(4)),
            Texto.CARIMBO_PEQUENO,
        )


def desenhar_bancada(
    carregado: ProjetoCarregado, comodo: str, movel: Movel, data: date | None = None
) -> Desenho:
    """Folha da bancada: vista superior e frentes cotadas, carimbo, estimadas e checagens.

    Levanta ``BancadaInvalidaError`` se a bancada não fechar.
    """
    calc = bancada.calcular(movel)
    pav = carregado.projeto.pavimento_do_comodo(comodo)
    assert pav is not None and movel.bancada is not None
    larg, prof, alt = movel.largura.valor, movel.profundidade.valor, movel.altura.valor
    entre = max(500.0, 0.25 * larg)
    largura_frentes = sum(t.comprimento for t in calc.trechos) + entre * (len(calc.trechos) - 1)
    y_superior = alt + entre
    folha = escolher_folha((-entre / 2, -entre / 3, max(larg, largura_frentes) + entre / 2,
                            y_superior + prof + entre / 2))  # fmt: skip
    doc = novo_documento(folha.escala)
    msp = doc.modelspace()
    vistas = _VistasBancada(calc, folha, msp)
    x = 0.0
    for t in calc.trechos:
        x += vistas.frente_trecho(t.nome, x) + entre
    vistas.superior(y_superior)

    estimadas = medidas_estimadas(movel, f"comodos/{comodo}.moveis[{movel.id}]")
    problemas = [
        p
        for p in checar(carregado.projeto, carregado.dados_comodos, carregado.regras, comodo)
        if p.elemento == movel.id
    ]
    chapas = " · ".join(f"{ch.chapas} {ch.material} {ch.espessura}" for ch in calc.chapas)
    pernas = {"metal": "perna metálica 50 × 50", "madeira": "pé de madeira", "painel": "painel"}
    nome = movel.nome or movel.id
    titulo = f"Bancada planejada — {nome}"
    tampo = movel.bancada.tampo
    desenhar_folha(
        msp,
        folha,
        DadosCarimbo(
            projeto=carregado.projeto.projeto,
            apelido=carregado.projeto.imovel.endereco_apelido,
            desenho=titulo,
            pavimento=pav.nome or pav.id,
            escopo=f"móvel {movel.id} · cômodo {comodo}",
            data=(data or date.today()).isoformat(),
            hash_curto=carregado.hash_curto,
            gerador=VERSAO_MOVEL,
            estimadas=estimadas,
            legenda=(
                f"{larg} × {prof} × {alt} mm · {'em L' if movel.forma == 'L' else 'reta'} · "
                f"{len(calc.modulos)} módulo(s)",
                f"tampo {tampo.material} {tampo.espessura.valor} mm · "
                f"{pernas[movel.bancada.pernas]} ({len(calc.pernas)})",
                f"chapas (estimativa): {chapas}",
                "cotas de cima = posição de pernas e módulos (mm)",
            ),
            checagens=[f"{i}. [{p.severidade}] {p.mensagem}" for i, p in enumerate(problemas, 1)],
        ),
    )
    return Desenho(doc, folha, titulo, estimadas)
