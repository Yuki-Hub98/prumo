"""Desenho técnico do móvel planejado: vista frontal (sem portas) e vista lateral.

Coordenadas do DXF em mm (1 unidade = 1 mm). A vista frontal fica com o canto
inferior esquerdo da caixa na origem; a lateral, à direita, com o fundo do móvel
do lado esquerdo e a frente do lado direito.
"""

from __future__ import annotations

from datetime import date

from ezdxf.enums import TextEntityAlignment
from ezdxf.layouts.layout import Modelspace

from interiores_cad import __version__
from interiores_cad.estilo import ESTILO_COTA, ESTILO_TEXTO, TRACEJADO, Texto, novo_documento
from interiores_cad.folha import DadosCarimbo, Folha, desenhar_folha, escolher_folha
from interiores_cad.planta import Desenho
from interiores_core.carregar import ProjetoCarregado
from interiores_core.medidas import medidas_estimadas
from interiores_core.modelo import Movel
from interiores_core.planejado import Planejado, Retangulo, calcular
from interiores_core.regras import VERSAO_REGRAS, checar

VERSAO_MOVEL = f"interiores-cad {__version__} · planejado v2 · {VERSAO_REGRAS}"
"""Entra na chave de cache: mudou o desenho do móvel, suba o ``planejado vN``."""

ESTRUTURA = {"lateral", "base", "tampo", "divisoria", "rodape", "prateleira"}
COR_CHAPA = (215, 215, 215)


def achar_movel(carregado: ProjetoCarregado, comodo: str, movel_id: str) -> Movel:
    dados = carregado.dados_comodos.get(comodo)
    movel = next((m for m in dados.moveis if m.id == movel_id), None) if dados else None
    if movel is None:
        raise KeyError(f"móvel '{movel_id}' não existe no cômodo '{comodo}'")
    if movel.construcao is None and movel.bancada is None:
        raise ValueError(f"'{movel_id}' não tem construção; crie com `interiores planejado criar`")
    return movel


class _Vistas:
    def __init__(self, calc: Planejado, folha: Folha, msp: Modelspace) -> None:
        self.calc = calc
        self.folha = folha
        self.msp = msp
        m = calc.movel
        self.larg, self.prof, self.alt = (
            m.largura.valor,
            m.profundidade.valor,
            m.altura.valor,
        )

    def mm(self, papel: float) -> float:
        return self.folha.mm(papel)

    def texto(
        self,
        texto: str,
        ponto: tuple[float, float],
        altura: float,
        camada: str = "TEXTO",
        rotacao: float = 0,
        alinhamento: TextEntityAlignment = TextEntityAlignment.MIDDLE_CENTER,
    ) -> None:
        self.msp.add_text(
            texto,
            height=self.mm(altura),
            rotation=rotacao,
            dxfattribs={"layer": camada, "style": ESTILO_TEXTO},
        ).set_placement(ponto, align=alinhamento)

    def ret(
        self, x: float, y: float, w: float, h: float, **attrs: object
    ) -> list[tuple[float, float]]:
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        self.msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "MOVEL", **attrs})
        return pts

    def cota(
        self, p1: tuple[float, float], p2: tuple[float, float], base: tuple[float, float]
    ) -> None:
        angulo = 0 if abs(p2[1] - p1[1]) < 1e-6 else 90
        dim = self.msp.add_linear_dim(
            base=base,
            p1=p1,
            p2=p2,
            angle=angulo,
            dimstyle=ESTILO_COTA,
            dxfattribs={"layer": "COTA"},
        )
        dim.render()

    def titulo(self, nome: str, detalhe: str, x: float) -> None:
        """Nome da vista e, embaixo e menor, o que ela mostra (cabe em móvel estreito)."""
        self.texto(nome, (x, -self.mm(15)), Texto.CARIMBO)
        self.texto(detalhe, (x, -self.mm(19)), Texto.CARIMBO_PEQUENO)

    # ------------------------------------------------------------ frente

    def frente(self) -> None:
        for r in self.calc.layout:
            if r.tipo in ESTRUTURA:
                pts = self.ret(r.x, r.y, r.largura, r.altura)
                hachura = self.msp.add_hatch(dxfattribs={"layer": "MOVEL"})
                hachura.rgb = COR_CHAPA
                hachura.paths.add_polyline_path(pts, is_closed=True)
            elif r.tipo in ("gaveta", "nicho", "cabideiro"):
                self.espaco(r)
        for r in self.calc.layout:
            if r.tipo == "porta":
                self.ret(r.x, r.y, r.largura, r.altura, linetype=TRACEJADO)
        self.titulo("VISTA FRONTAL", "sem portas; portas tracejadas", self.larg / 2)

    def espaco(self, r: Retangulo) -> None:
        cx, cy = r.x + r.largura / 2, r.y + r.altura / 2
        if r.tipo == "gaveta":
            k = 2.0
            self.ret(r.x + k, r.y + k, r.largura - 2 * k, r.altura - 2 * k)
            puxador = min(150.0, r.largura / 3)
            ypux = r.y + r.altura - min(40.0, r.altura / 4)
            self.msp.add_line(
                (cx - puxador / 2, ypux), (cx + puxador / 2, ypux), dxfattribs={"layer": "MOVEL"}
            )
        elif r.tipo == "cabideiro":
            ytubo = r.y + r.altura - 60
            self.msp.add_line(
                (r.x + 10, ytubo),
                (r.x + r.largura - 10, ytubo),
                dxfattribs={"layer": "MOVEL", "lineweight": 50},
            )
        rotulo = f"{r.rotulo} {r.altura:.0f}"
        altura_txt = min(Texto.MOVEL, r.altura / self.folha.escala * 0.45)
        self.texto(rotulo, (cx, cy), max(altura_txt, 1.2), "MOVEL")

    def cotas_frente(self) -> None:
        larg, alt = self.larg, self.alt
        self.cota((0, 0), (larg, 0), (0, -self.mm(8)))
        self.cota((0, 0), (0, alt), (-self.mm(8), 0))
        # larguras livres dos vãos, em cadeia, em cima
        vaos = sorted(
            {
                (r.vao, r.x, r.largura)
                for r in self.calc.layout
                if r.vao is not None and r.tipo in ("gaveta", "nicho", "cabideiro")
            }
        )
        topo = alt + self.mm(6)
        vistos: set[int] = set()
        for vao, x, w in vaos:
            if vao in vistos:
                continue
            vistos.add(vao)
            self.cota((x, alt), (x + w, alt), (x, topo))
        # alturas livres de cada espaço, por vão, junto à esquerda do vão
        for vao in sorted(vistos):
            espacos = [
                r
                for r in self.calc.layout
                if r.vao == vao and r.tipo in ("gaveta", "nicho", "cabideiro")
            ]
            x = espacos[0].x + min(self.mm(5), espacos[0].largura * 0.2)
            for r in espacos:
                self.cota((x, r.y), (x, r.y + r.altura), (x, r.y))

    # ------------------------------------------------------------ lateral

    def lateral(self, x0: float) -> None:
        c = self.calc.movel.construcao
        assert c is not None
        prof, alt = self.prof, self.alt
        e, f = c.chapa.espessura.valor, c.fundo.espessura.valor
        rodape = c.rodape.valor if c.rodape else 0
        self.ret(x0, rodape, prof, alt - rodape)  # caixa acima do rodapé
        self.ret(x0, rodape, f, alt - rodape)  # fundo
        self.ret(x0 + f, rodape, prof - f, e)  # base
        self.ret(x0 + f, alt - e, prof - f, e)  # tampo
        if rodape:
            self.ret(x0 + prof - 50 - e, 0, e, rodape)  # rodapé recuado
            self.ret(x0 + f + 50, 0, e, rodape)  # apoio traseiro
        self.titulo("VISTA LATERAL", "fundo à esquerda", x0 + prof / 2)
        self.cota((x0, 0), (x0 + prof, 0), (x0, -self.mm(8)))
        self.cota((x0 + prof, 0), (x0 + prof, alt), (x0 + prof + self.mm(8), 0))
        if rodape:
            self.cota((x0 + prof, 0), (x0 + prof, rodape), (x0 + prof + self.mm(4), 0))


def desenhar_movel(
    carregado: ProjetoCarregado, comodo: str, movel_id: str, data: date | None = None
) -> Desenho:
    """Folha com as vistas cotadas, carimbo, estimadas e checagens do móvel.

    Levanta ``KeyError`` (móvel inexistente), ``ValueError`` (sem construção) ou
    ``ConstrucaoInvalidaError`` (não cabe).
    """
    movel = achar_movel(carregado, comodo, movel_id)
    if movel.bancada is not None:
        from interiores_cad.bancada import desenhar_bancada

        return desenhar_bancada(carregado, comodo, movel, data)
    calc = calcular(movel)
    pav = carregado.projeto.pavimento_do_comodo(comodo)
    assert pav is not None
    larg, prof, alt = movel.largura.valor, movel.profundidade.valor, movel.altura.valor
    vao_entre = max(600.0, 0.35 * larg)
    folha = escolher_folha((0, 0, larg + vao_entre + prof, alt))
    doc = novo_documento(folha.escala)
    msp = doc.modelspace()
    vistas = _Vistas(calc, folha, msp)
    vistas.frente()
    vistas.cotas_frente()
    vistas.lateral(larg + vao_entre)

    estimadas = medidas_estimadas(movel, f"comodos/{comodo}.moveis[{movel.id}]")
    problemas = [
        p
        for p in checar(carregado.projeto, carregado.dados_comodos, carregado.regras, comodo)
        if p.elemento == movel.id
    ]
    c = movel.construcao
    assert c is not None
    chapas = " · ".join(
        f"{ch.chapas} chapa(s) {ch.material} {ch.espessura} mm" for ch in calc.chapas
    )
    nome = movel.nome or movel.id
    titulo = f"Móvel planejado — {nome}"
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
                f"{larg} × {prof} × {alt} mm · portas: {movel.portas or 'sem portas'}",
                f"chapa {c.chapa.material} {c.chapa.espessura.valor} mm · fundo "
                f"{c.fundo.material} {c.fundo.espessura.valor} mm",
                f"estimativa: {chapas}",
                "cotas dos vãos e espaços = medidas livres internas (mm)",
            ),
            checagens=[f"{i}. [{p.severidade}] {p.mensagem}" for i, p in enumerate(problemas, 1)],
        ),
    )
    return Desenho(doc, folha, titulo, estimadas)
