import { maiuscula } from "../texto";
import { useEffect, useRef, useState } from "react";
import type { Cores, MovelTela, PavimentoTela, Problema } from "../api/cliente";

type EstruturaTela = NonNullable<PavimentoTela["estrutura"]>[number];
import { PADRAO } from "./PainelCores";
import { formatar, type Unidade } from "../unidades";
import { encaixar, vertices, type Pt } from "../editor/geometria";

/** Aba Estruturas aberta: pilar e viga clicáveis, laje contornada, pilar arrastável. */
export type ModoEstrutura = {
  sel: string | null;
  aoSelecionar: (id: string | null) => void;
  /** Soltou o arrastado: pilar ganha ``centro`` novo (grudado num canto de parede ou na
   * grade); escada, ``inicio`` novo (na grade). */
  aoMover: (id: string, campo: "centro" | "inicio", ponto: Pt) => void;
};

/** Quanto o ponteiro anda (px na tela) antes de um clique num móvel virar arrasto. */
export const FOLGA_PX = 4;

export type Item = { tipo: "parede" | "abertura" | "instalacao" | "comodo"; id: string };

/** Modo editor de planta: o que está selecionado e os callbacks de edição. */
export type ModoEditor = {
  item: Item | null;
  /** Paredes marcadas (ex.: escolhendo as paredes de um cômodo novo). */
  destacadas: string[];
  desenhando: boolean;
  aoItem: (i: Item | null) => void;
  aoMoverVertice: (de: Pt, para: Pt) => void;
  aoNovaParede: (a: Pt, b: Pt) => void;
};

// identidade visual: amarelo trena = selecionado; azul "projeto" = guia de desenho;
// traço em px de tela (non-scaling-stroke), não em mm
const SEL = "var(--trena)";
const GUIA = "var(--projeto)";

/** y do pavimento é para cima; no SVG é para baixo: inverte só aqui. */
const xy = ([x, y]: Pt | readonly number[]) => `${x},${-y}`;
const pontos = (lista: (Pt | readonly number[])[]) => lista.map(xy).join(" ");

const PASSO = 10; // arrastar anda de 1 em 1 cm


export type LadoMovel = "esquerda" | "direita" | "frente" | "costas";
/** Cantos de cada lado (cantos: costas-esq., costas-dir., frente-dir., frente-esq.). */
const LADOS: Record<LadoMovel, [number, number]> = { costas: [0, 1], direita: [1, 2], frente: [2, 3], esquerda: [3, 0] };
const TAMANHO_MIN = 100;

const COR_GRAV: Record<string, string> = { erro: "var(--erro)", aviso: "var(--aviso)", info: "var(--info)" };

/** Cor de cada instalação (identidade visual). */
const COR_INST: Record<string, string> = {
  tomada: "var(--tinta)",
  interruptor: "var(--tinta)",
  ponto_luz: "var(--tinta)",
  agua_fria: "var(--projeto)",
  agua_quente: "var(--erro)",
  gas: "var(--aviso)",
  esgoto: "var(--tinta-suave)",
  ralo: "var(--tinta-suave)",
};

const LETRA: Record<string, string> = {
  tomada: "T",
  interruptor: "S",
  ponto_luz: "L",
  agua_fria: "AF",
  agua_quente: "AQ",
  esgoto: "ES",
  ralo: "R",
  gas: "G",
};

export function Planta({
  geometria,
  unidade,
  problemas,
  selecionado,
  aoSelecionar,
  aoMover,
  aoRedimensionar,
  comodoSelecionado,
  aoSelecionarComodo,
  cores,
  editor,
  fundo = null,
  destaque = null,
  estrutura,
}: {
  /** Aba Estruturas aberta (sem ela, pilar e viga só aparecem, sem clique). */
  estrutura?: ModoEstrutura;
  /** Problema escolhido em "Ver na planta": pisca 2× na cor da gravidade (``vez`` reinicia). */
  destaque?: { p: Problema; vez: number } | null;
  editor?: ModoEditor;
  /** Andar de baixo, apagado ao fundo: referência para desenhar o de cima (os cantos dele
   * também atraem o ponto ao desenhar). */
  fundo?: PavimentoTela | null;
  comodoSelecionado: string | null;
  aoSelecionarComodo: (id: string) => void;
  /** Cores (rascunho da variação) do cômodo selecionado; os outros ficam no padrão. */
  cores: Cores | null;
  geometria: PavimentoTela;
  unidade: Unidade;
  problemas: Problema[];
  selecionado: string | null;
  aoSelecionar: (id: string | null) => void;
  aoMover: (movel: MovelTela, centro: [number, number]) => void;
  /** Puxar um lado do móvel selecionado: o lado oposto fica parado. */
  aoRedimensionar?: (movel: MovelTela, lado: LadoMovel, tamanho: number) => void;
}) {
  const svg = useRef<SVGSVGElement>(null);
  // ``tela``: onde o clique começou (px); ``solto``: já passou da folga e está arrastando
  const [arrasto, setArrasto] = useState<{ id: string; ini: Pt; d: Pt; tela: Pt; solto: boolean } | null>(null);
  const [canto, setCanto] = useState<{ de: Pt; para: Pt } | null>(null);
  const [trilha, setTrilha] = useState<Pt | null>(null);
  const [cursor, setCursor] = useState<Pt | null>(null);
  const [arrastoPilar, setArrastoPilar] = useState<{ id: string; ini: Pt; d: Pt; tela: Pt; solto: boolean } | null>(null);
  // cantos deste andar (alças de arrastar) e, para o ímã ao desenhar, também os do andar de baixo
  const cantos = vertices(geometria.paredes.map((p) => p.eixo));
  const ima = fundo ? vertices([...geometria.paredes, ...fundo.paredes].map((p) => p.eixo)) : cantos;
  const desenhando = editor?.desenhando ?? false;
  useEffect(() => {
    if (!desenhando) setTrilha(null); // parou de desenhar: a próxima sequência começa do zero
  }, [desenhando]);
  // halo nos elementos com problema: o pior (erro > aviso) de cada um
  const HALO: Record<string, string> = {};
  for (const p of problemas) {
    if (!p.elemento || (p.severidade !== "erro" && p.severidade !== "aviso")) continue;
    if (HALO[p.elemento] !== "var(--erro)") HALO[p.elemento] = COR_GRAV[p.severidade];
  }
  const ehSel = (tipo: Item["tipo"], id: string) => editor?.item?.tipo === tipo && editor.item.id === id;

  const lim = geometria.limites ?? fundo?.limites ?? [
    [0, 0],
    [4000, 3000],
  ];
  const margem = 600;
  const [x0, y0] = lim[0];
  const [x1, y1] = lim[1];
  const viewBox = `${x0 - margem} ${-y1 - margem} ${x1 - x0 + 2 * margem} ${y1 - y0 + 2 * margem}`;

  /** Ponto do mouse em mm no sistema do pavimento. */
  function emMm(ev: React.PointerEvent): Pt {
    const s = svg.current!;
    const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(s.getScreenCTM()!.inverse());
    return [p.x, -p.y];
  }

  const arredonda = (v: number) => Math.round(v / PASSO) * PASSO;
  // puxando um lado do móvel selecionado (alças no meio de cada lado)
  const [puxando, setPuxando] = useState<{ id: string; lado: LadoMovel; ini: Pt; normal: Pt; t0: number; t: number } | null>(null);

  /** Pilar, viga, laje ou escada na planta (com a aba Estruturas: clique, arrasto, laje). */
  const desenharEstrutura = (e: EstruturaTela) => {
    if (e.tipo === "escada_abaixo") {
      // a escada do andar de baixo chegando: o vão no piso (tracejado com X), os degraus
      // apagados e "DESCE"
      const xs = e.contorno.map((q) => q[0]);
      const ys = e.contorno.map((q) => q[1]);
      const [a, b, c, d] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      return (
        <g key={`abaixo-${e.id}`} pointerEvents="none">
          {e.escada?.degraus.map((g, i) => (
            <polygon key={i} points={pontos(g)} fill="none" stroke="var(--tinta-suave)" strokeOpacity={0.45} strokeWidth={1} vectorEffect="non-scaling-stroke" />
          ))}
          <g stroke="var(--tinta-suave)" strokeWidth={1.2} strokeDasharray="8 5" fill="none">
            <polygon points={pontos(e.contorno)} vectorEffect="non-scaling-stroke" />
            <line x1={a} y1={-c} x2={b} y2={-d} vectorEffect="non-scaling-stroke" />
            <line x1={a} y1={-d} x2={b} y2={-c} vectorEffect="non-scaling-stroke" />
          </g>
          <text x={(a + b) / 2} y={-(c + d) / 2} fontSize={150} textAnchor="middle" dominantBaseline="middle" fill="var(--tinta-suave)">
            DESCE
          </text>
        </g>
      );
    }
    const marcada = estrutura?.sel === e.id;
    const cor = marcada ? SEL : e.estimada ? "var(--chute)" : HALO[e.id] ?? "var(--tinta-suave)";
    const clicar = (ev: React.PointerEvent) => {
      if (!estrutura) return;
      ev.stopPropagation();
      estrutura.aoSelecionar(e.id);
      if (e.tipo === "pilar" || e.tipo === "escada") {
        (ev.target as Element).setPointerCapture?.(ev.pointerId);
        setArrastoPilar({ id: e.id, ini: emMm(ev), d: [0, 0], solto: false, tela: [ev.clientX, ev.clientY] });
      }
    };
    const furos = (e.furos ?? []).map((f, i) => {
      const xs = f.map((q) => q[0]);
      const ys = f.map((q) => q[1]);
      const [a, b] = [Math.min(...xs), Math.max(...xs)];
      const [c, d] = [Math.min(...ys), Math.max(...ys)];
      return (
        <g key={i} pointerEvents="none" stroke={marcada ? SEL : "var(--tinta-suave)"} strokeWidth={1.2} strokeDasharray="8 5" vectorEffect="non-scaling-stroke">
          <polygon points={pontos(f)} fill="none" vectorEffect="non-scaling-stroke" />
          <line x1={a} y1={-c} x2={b} y2={-d} vectorEffect="non-scaling-stroke" />
          <line x1={a} y1={-d} x2={b} y2={-c} vectorEffect="non-scaling-stroke" />
        </g>
      );
    });
    if (e.tipo === "laje")
      return (
        <g key={e.id}>
          {estrutura && (
            <polygon
              points={pontos(e.contorno)}
              fill={marcada ? SEL : "none"}
              fillOpacity={0.08}
              stroke={cor}
              strokeWidth={marcada ? 3 : 1.2}
              strokeDasharray="14 6"
              vectorEffect="non-scaling-stroke"
              pointerEvents="none"
            />
          )}
          {furos}
        </g>
      );
    const d = arrastoPilar?.id === e.id ? arrastoPilar.d : [0, 0];
    const moverArrasto = (ev: React.PointerEvent) => {
      const a = arrastoPilar;
      if (!a || a.id !== e.id) return;
      const solto = a.solto || Math.hypot(ev.clientX - a.tela[0], ev.clientY - a.tela[1]) > FOLGA_PX;
      const m = emMm(ev);
      setArrastoPilar({ ...a, solto, d: solto ? [m[0] - a.ini[0], m[1] - a.ini[1]] : [0, 0] });
    };
    const soltarArrasto = () => {
      const a = arrastoPilar;
      setArrastoPilar(null);
      if (!a?.solto || !estrutura) return;
      if (e.tipo === "escada" && e.escada) {
        const [x, y] = e.escada.inicio;
        estrutura.aoMover(e.id, "inicio", [Math.round((x + a.d[0]) / PASSO) * PASSO, Math.round((y + a.d[1]) / PASSO) * PASSO]);
        return;
      }
      const pts = e.contorno;
      const cx = (Math.min(...pts.map((q) => q[0])) + Math.max(...pts.map((q) => q[0]))) / 2;
      const cy = (Math.min(...pts.map((q) => q[1])) + Math.max(...pts.map((q) => q[1]))) / 2;
      const novo = encaixar([cx + a.d[0], cy + a.d[1]], cantos);
      estrutura.aoMover(e.id, "centro", [Math.round(novo[0]), Math.round(novo[1])]);
    };
    if (e.tipo === "escada" && e.escada) {
      const esc = e.escada;
      const cam = esc.caminho;
      const [xa, ya] = cam[cam.length - 2];
      const [xb, yb] = cam[cam.length - 1];
      const ang = Math.atan2(yb - ya, xb - xa);
      const ponta = 180;
      const seta = [-1, 1].map((l) => [xb - ponta * Math.cos(ang + (l * Math.PI) / 7), yb - ponta * Math.sin(ang + (l * Math.PI) / 7)]);
      return (
        <g
          key={e.id}
          transform={`translate(${d[0]},${-d[1]})`}
          className={estrutura ? "cursor-move" : undefined}
          pointerEvents={estrutura ? "auto" : "none"}
          onPointerDown={clicar}
          onPointerMove={moverArrasto}
          onPointerUp={soltarArrasto}
        >
          <title>{`Escada ${e.id}: ${esc.espelhos} espelhos de ${Math.round(esc.espelho)} mm`}</title>
          {esc.degraus.map((g, i) => (
            <polygon
              key={i}
              points={pontos(g)}
              fill={esc.patamares?.includes(i) ? "var(--superficie-2)" : "var(--superficie)"}
              stroke={marcada ? SEL : e.estimada ? "var(--chute)" : HALO[e.id] ?? "var(--tinta-suave)"}
              strokeWidth={marcada ? 2 : 1}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <polyline points={pontos(cam)} fill="none" stroke="var(--tinta)" strokeWidth={1.2} vectorEffect="non-scaling-stroke" pointerEvents="none" />
          <polygon points={pontos([[xb, yb], ...seta])} fill="var(--tinta)" pointerEvents="none" />
          <circle cx={cam[0][0]} cy={-cam[0][1]} r={45} fill="var(--tinta)" pointerEvents="none" />
          <text x={cam[0][0]} y={-cam[0][1] + 260} fontSize={150} textAnchor="middle" fill="var(--tinta-suave)" pointerEvents="none">
            SOBE
          </text>
          {furos}
        </g>
      );
    }
    return (
      <polygon
        key={e.id}
        points={pontos(e.contorno.map(([x, y]) => [x + d[0], y + d[1]]))}
        fill={e.tipo === "pilar" ? "var(--tinta)" : "transparent"}
        stroke={e.tipo === "pilar" && !marcada && !e.estimada && !HALO[e.id] ? "none" : cor}
        strokeWidth={marcada ? 3 : 1.5}
        strokeDasharray={e.tipo === "viga" || (!marcada && e.estimada) ? "8 5" : undefined}
        vectorEffect="non-scaling-stroke"
        pointerEvents={estrutura ? (e.tipo === "viga" ? "stroke" : "auto") : "none"}
        className={estrutura ? (e.tipo === "pilar" ? "cursor-move" : "cursor-pointer") : undefined}
        onPointerDown={clicar}
        onPointerMove={moverArrasto}
        onPointerUp={soltarArrasto}
      >
        <title>{`${e.tipo === "pilar" ? "Pilar" : "Viga"} ${e.id}`}</title>
      </polygon>
    );
  };

  return (
    <svg
      ref={svg}
      viewBox={viewBox}
      className="h-full w-full touch-none select-none bg-papel"
      onPointerDown={(e) => {
        if (editor?.desenhando) {
          if (e.button !== 0) return;
          const p = encaixar(emMm(e), ima, trilha);
          if (trilha && (p[0] !== trilha[0] || p[1] !== trilha[1])) editor.aoNovaParede(trilha, p);
          setTrilha(p);
          return;
        }
        if (e.target === svg.current) {
          aoSelecionar(null);
          editor?.aoItem(null);
          estrutura?.aoSelecionar(null);
        }
      }}
      onContextMenu={(e) => {
        if (editor?.desenhando) {
          e.preventDefault();
          setTrilha(null); // botão direito: termina a sequência de paredes
        }
      }}
      onPointerMove={(e) => {
        if (editor?.desenhando) {
          setCursor(encaixar(emMm(e), ima, trilha));
          return;
        }
        if (canto) {
          setCanto({ ...canto, para: encaixar(emMm(e), ima, null, canto.de) });
          return;
        }
        if (puxando) {
          const [x, y] = emMm(e);
          const delta = (x - puxando.ini[0]) * puxando.normal[0] + (y - puxando.ini[1]) * puxando.normal[1];
          setPuxando({ ...puxando, t: Math.max(TAMANHO_MIN, arredonda(puxando.t0 + delta)) });
          return;
        }
        if (!arrasto) return;
        // clicar para selecionar treme a mão: só vira arrasto depois de 4 px na tela
        const solto = arrasto.solto || Math.hypot(e.clientX - arrasto.tela[0], e.clientY - arrasto.tela[1]) >= FOLGA_PX;
        if (!solto) return;
        const [x, y] = emMm(e);
        setArrasto({ ...arrasto, solto, d: [arredonda(x - arrasto.ini[0]), arredonda(y - arrasto.ini[1])] });
      }}
      onPointerUp={() => {
        if (canto) {
          if (canto.para[0] !== canto.de[0] || canto.para[1] !== canto.de[1])
            editor?.aoMoverVertice(canto.de, canto.para);
          setCanto(null);
          return;
        }
        if (puxando) {
          const m = geometria.moveis.find((x) => x.id === puxando.id);
          if (m && puxando.t !== puxando.t0) aoRedimensionar?.(m, puxando.lado, puxando.t);
          setPuxando(null);
          return;
        }
        if (!arrasto) return;
        const m = geometria.moveis.find((x) => x.id === arrasto.id);
        if (m && (arrasto.d[0] || arrasto.d[1]))
          aoMover(m, [m.centro[0] + arrasto.d[0], m.centro[1] + arrasto.d[1]]);
        setArrasto(null);
      }}
    >
      {/* malha do papel: 10 cm, mais forte a cada 1 m */}
      <rect
        x={x0 - margem * 4}
        y={-y1 - margem * 4}
        width={x1 - x0 + margem * 8}
        height={y1 - y0 + margem * 8}
        fill="url(#malha)"
        pointerEvents="none"
      />
      {/* andar de baixo, de referência */}
      {fundo?.paredes.map((p) => (
        <polygon key={`fundo-${p.id}`} points={pontos(p.corpo)} fill="var(--tinta)" fillOpacity={0.12} pointerEvents="none" />
      ))}
      {/* cômodos */}
      {geometria.comodos.map((c) => {
        const pintado = c.id === comodoSelecionado && cores;
        return (
          c.poligono && (
            <polygon
              key={c.id}
              points={pontos(c.poligono)}
              fill={pintado && cores.piso ? cores.piso : "var(--superficie)"}
              fillOpacity={pintado && cores.piso ? 1 : 0.55}
              stroke={(editor ? ehSel("comodo", c.id) : c.id === comodoSelecionado) ? SEL : "none"}
              strokeWidth={3}
              vectorEffect="non-scaling-stroke"
              className="cursor-pointer"
              onPointerDown={(e) => {
                if (editor?.desenhando) return;
                e.stopPropagation();
                aoSelecionar(null);
                if (editor) editor.aoItem({ tipo: "comodo", id: c.id });
                else aoSelecionarComodo(c.id);
              }}
            />
          )
        );
      })}

      {/* escadas embaixo das paredes (encostam nelas); pilar e viga vão por cima */}
      {(geometria.estrutura ?? []).filter((e) => e.tipo === "escada").map(desenharEstrutura)}

      {/* paredes, com os vãos abertos por cima */}
      {geometria.paredes.map((p) => {
        const marcada = ehSel("parede", p.id) || editor?.destacadas.includes(p.id);
        return (
          <polygon
            key={p.id}
            points={pontos(p.corpo)}
            fill="var(--tinta)"
            fillOpacity={0.85}
            stroke={marcada ? SEL : p.estimada ? "var(--chute)" : HALO[p.id] ?? "none"}
            strokeWidth={marcada ? 3 : p.estimada ? 1.5 : 3}
            strokeDasharray={!marcada && p.estimada ? "6 4" : undefined}
            strokeOpacity={!marcada && !p.estimada && HALO[p.id] ? 0.6 : 1}
            vectorEffect="non-scaling-stroke"
            className={editor && !editor.desenhando ? "cursor-pointer" : undefined}
            onPointerDown={(e) => {
              if (!editor || editor.desenhando) return;
              e.stopPropagation();
              editor.aoItem({ tipo: "parede", id: p.id });
            }}
          >
            {editor && <title>{p.id}</title>}
          </polygon>
        );
      })}
      {geometria.aberturas.map((a) => (
        <g
          key={a.id}
          className={editor && !editor.desenhando ? "cursor-pointer" : undefined}
          onPointerDown={(e) => {
            if (!editor || editor.desenhando) return;
            e.stopPropagation();
            editor.aoItem({ tipo: "abertura", id: a.id });
          }}
        >
          <polygon
            points={pontos(a.vao)}
            fill={a.tipo === "janela" ? "var(--superficie)" : "var(--papel)"}
            stroke={ehSel("abertura", a.id) ? SEL : a.estimada ? "var(--chute)" : HALO[a.id] ?? "var(--tinta-suave)"}
            strokeWidth={ehSel("abertura", a.id) ? 3 : a.tipo === "janela" || a.estimada ? 1 : 0}
            strokeDasharray={!ehSel("abertura", a.id) && a.estimada ? "6 4" : undefined}
            vectorEffect="non-scaling-stroke"
          />
          {a.giro && (
            <polygon
              points={pontos(a.giro)}
              fill="none"
              stroke="var(--tinta-suave)"
              strokeWidth={1}
              strokeDasharray="4 3"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </g>
      ))}

      {/* estrutura: laje (só com a aba aberta), furo da laje com X, viga tracejada (acima do
          corte), pilar preenchido */}
      {(geometria.estrutura ?? []).filter((e) => e.tipo !== "escada").map(desenharEstrutura)}

      {/* cor de cada parede: faixa na face voltada para o cômodo pintado */}
      {cores &&
        geometria.comodos
          .filter((c) => c.id === comodoSelecionado)
          .flatMap((c) => c.faces ?? [])
          .map((f, i) => (
            <line
              key={i}
              x1={f.de[0]}
              y1={-f.de[1]}
              x2={f.ate[0]}
              y2={-f.ate[1]}
              stroke={cores.paredes?.[f.parede] ?? cores.parede ?? PADRAO.parede}
              strokeWidth={70}
              pointerEvents="none"
            />
          ))}

      {/* instalações */}
      {geometria.instalacoes.map(
        (i) =>
          i.posicao && (
            <g
              key={i.id}
              transform={`translate(${xy(i.posicao)})`}
              className={editor && !editor.desenhando ? "cursor-pointer" : undefined}
              onPointerDown={(e) => {
                if (!editor || editor.desenhando) return;
                e.stopPropagation();
                editor.aoItem({ tipo: "instalacao", id: i.id });
              }}
            >
              <circle
                r={85}
                fill="var(--superficie)"
                stroke={ehSel("instalacao", i.id) ? SEL : HALO[i.id] ?? COR_INST[i.tipo] ?? "var(--tinta)"}
                strokeWidth={ehSel("instalacao", i.id) || HALO[i.id] ? 3 : 1.5}
                vectorEffect="non-scaling-stroke"
              />
              <text fontSize={LETRA[i.tipo]?.length === 2 ? 70 : 90} textAnchor="middle" dy={30} fill={COR_INST[i.tipo] ?? "var(--tinta)"} fontWeight={600}>
                {LETRA[i.tipo] ?? "?"}
              </text>
            </g>
          ),
      )}

      {/* móveis */}
      {geometria.moveis.map((m) => {
        const d = arrasto?.id === m.id ? arrasto.d : [0, 0];
        const sel = m.id === selecionado;
        const [cx, cy] = m.centro;
        // seta curta na borda da frente (meio entre os cantos frente-dir. e frente-esq.)
        const borda: Pt = [(m.cantos[2][0] + m.cantos[3][0]) / 2, (m.cantos[2][1] + m.cantos[3][1]) / 2];
        const ini: Pt = [borda[0] - m.frente[0] * 160, borda[1] - m.frente[1] * 160];
        const fim: Pt = [borda[0] - m.frente[0] * 30, borda[1] - m.frente[1] * 30];
        // móvel fino (TV, painel): o nome vai à frente dele, não dentro
        const fino = Math.hypot(borda[0] - cx, borda[1] - cy) < 150;
        const rotulo: Pt = fino ? [borda[0] + m.frente[0] * 220, borda[1] + m.frente[1] * 220] : [cx, cy];
        return (
          <g
            key={m.id}
            transform={`translate(${d[0]},${-d[1]})`}
            className={editor ? undefined : "cursor-move"}
            opacity={editor ? 0.35 : 1}
            pointerEvents={editor ? "none" : undefined}
            onPointerDown={(e) => {
              e.stopPropagation();
              (e.target as Element).setPointerCapture?.(e.pointerId);
              aoSelecionar(m.id);
              setArrasto({ id: m.id, ini: emMm(e), d: [0, 0], tela: [e.clientX, e.clientY], solto: false });
            }}
          >
            {/* halo do problema: 8 px na cor da gravidade, 40 % */}
            {HALO[m.id] && !sel && (
              <polygon
                points={pontos(m.contorno?.length ? m.contorno : m.cantos)}
                fill="none"
                stroke={HALO[m.id]}
                strokeOpacity={0.4}
                strokeWidth={8}
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
              />
            )}
            <polygon
              points={pontos(m.contorno?.length ? m.contorno : m.cantos)}
              fill={
                (m.comodo === comodoSelecionado && (cores?.moveis?.[m.id] ?? cores?.moveis?.[m.tipo])) ||
                "var(--superficie)"
              }
              fillOpacity={m.elevado ? 0.6 : 1}
              stroke={sel ? SEL : "var(--tinta-suave)"}
              strokeWidth={sel ? 3 : 1}
              strokeDasharray={m.elevado ? "6 4" : undefined}
              vectorEffect="non-scaling-stroke"
            />
            {(m.detalhes ?? []).map((d, i) => (
              <polygon
                key={`d${i}`}
                points={pontos(d)}
                fill="none"
                stroke="var(--tinta-suave)"
                strokeWidth={1}
                strokeDasharray="4 3"
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
              />
            ))}
            {!fino && <line
              x1={ini[0]}
              y1={-ini[1]}
              x2={fim[0]}
              y2={-fim[1]}
              stroke="var(--tinta-suave)"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
              markerEnd="url(#seta)"
            />}
            <text x={rotulo[0]} y={-rotulo[1]} fontSize={90} textAnchor="middle" dy={30} fill="var(--tinta)">
              {m.nome ?? m.tipo}
            </text>
          </g>
        );
      })}

      {/* lados do móvel selecionado: puxar a alça muda a largura/profundidade (o lado oposto fica) */}
      {!editor &&
        aoRedimensionar &&
        geometria.moveis
          .filter((m) => m.id === selecionado && !arrasto?.solto)
          .map((m) => {
            const c = m.cantos as Pt[];
            const prev = puxando?.id === m.id ? puxando : null;
            const desloca = prev ? prev.t - prev.t0 : 0;
            const fantasma = c.map((p, i) =>
              prev && LADOS[prev.lado].includes(i) ? ([p[0] + prev.normal[0] * desloca, p[1] + prev.normal[1] * desloca] as Pt) : p,
            );
            return (
              <g key={`alcas-${m.id}`}>
                {prev && <polygon points={pontos(fantasma)} fill="var(--trena)" fillOpacity={0.12} stroke={SEL} strokeWidth={2} strokeDasharray="6 4" vectorEffect="non-scaling-stroke" pointerEvents="none" />}
                {(Object.keys(LADOS) as LadoMovel[]).map((lado) => {
                  const [i, j] = LADOS[lado];
                  const a = prev?.lado === lado ? fantasma : c;
                  const meio: Pt = [(a[i][0] + a[j][0]) / 2, (a[i][1] + a[j][1]) / 2];
                  const nx = meio[0] - m.centro[0] - (prev?.lado === lado ? prev.normal[0] * desloca / 2 : 0);
                  const ny = meio[1] - m.centro[1] - (prev?.lado === lado ? prev.normal[1] * desloca / 2 : 0);
                  const n = Math.hypot(nx, ny) || 1;
                  const normal: Pt = [nx / n, ny / n];
                  // largura = costas-esq. → costas-dir.; profundidade = costas-dir. → frente-dir.
                  const medida = Math.round(
                    lado === "esquerda" || lado === "direita" ? Math.hypot(c[1][0] - c[0][0], c[1][1] - c[0][1]) : Math.hypot(c[2][0] - c[1][0], c[2][1] - c[1][1]),
                  );
                  return (
                    <g key={lado}>
                      <rect
                        x={meio[0] - 45}
                        y={-meio[1] - 45}
                        width={90}
                        height={90}
                        fill="var(--superficie)"
                        stroke={SEL}
                        strokeWidth={2}
                        vectorEffect="non-scaling-stroke"
                        className={Math.abs(normal[0]) > Math.abs(normal[1]) ? "cursor-ew-resize" : "cursor-ns-resize"}
                        onPointerDown={(e) => {
                          e.stopPropagation();
                          (e.target as Element).setPointerCapture?.(e.pointerId);
                          setPuxando({ id: m.id, lado, ini: emMm(e), normal, t0: medida, t: medida });
                        }}
                      >
                        <title>Puxe para mudar a {lado === "esquerda" || lado === "direita" ? "largura" : "profundidade"}</title>
                      </rect>
                      {prev?.lado === lado && (
                        <text className="num" x={meio[0] + normal[0] * 260} y={-(meio[1] + normal[1] * 260)} fontSize={110} textAnchor="middle" dy={35} fill="var(--tinta)" stroke="var(--papel)" strokeWidth={14} paintOrder="stroke">
                          {formatar(prev.t, unidade)}
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}

      {/* rótulos dos cômodos por cima de tudo */}
      {geometria.comodos.map(
        (c) =>
          c.centro && (
            <text
              key={c.id}
              x={c.centro[0]}
              y={-c.centro[1] - 320}
              fontSize={130}
              textAnchor="middle"
              fill="var(--tinta-suave)"
              stroke="var(--papel)"
              strokeWidth={12}
              strokeOpacity={0.85}
              paintOrder="stroke"
              pointerEvents="none"
            >
              {c.nome}
              {c.area_m2 != null && (
                <tspan x={c.centro[0]} dy={150} fontSize={90}>
                  {c.area_m2.toLocaleString("pt-BR")} m²
                </tspan>
              )}
            </text>
          ),
      )}

      {/* problemas com posição */}
      {problemas
        .filter((p) => p.posicao && p.severidade !== "info")
        .map((p, i) => (
          <circle
            key={i}
            cx={p.posicao![0]}
            cy={-p.posicao![1]}
            r={90}
            fill="none"
            stroke={p.severidade === "erro" ? "var(--erro)" : "var(--aviso)"}
            strokeWidth={20}
          >
            <title>{maiuscula(p.mensagem)}</title>
          </circle>
        ))}

      {/* "Ver na planta": a área do problema pisca 2× na cor da gravidade */}
      {destaque && (destaque.p.regiao?.length || destaque.p.posicao) && (
        <g key={destaque.vez} className="piscar" pointerEvents="none">
          {destaque.p.regiao?.length ? (
            <polygon
              points={pontos(destaque.p.regiao as Pt[])}
              fill={COR_GRAV[destaque.p.severidade] ?? "var(--info)"}
              fillOpacity={0.25}
              stroke={COR_GRAV[destaque.p.severidade] ?? "var(--info)"}
              strokeWidth={30}
            />
          ) : (
            <circle
              cx={destaque.p.posicao![0]}
              cy={-destaque.p.posicao![1]}
              r={250}
              fill="none"
              stroke={COR_GRAV[destaque.p.severidade] ?? "var(--info)"}
              strokeWidth={40}
            />
          )}
        </g>
      )}

      {/* editor: alças nos cantos (arrastar move o canto e as paredes que se encontram nele) */}
      {editor &&
        !editor.desenhando &&
        cantos.map((c) => {
          const movendo = canto && canto.de[0] === c[0] && canto.de[1] === c[1];
          const [x, y] = movendo ? canto.para : c;
          return (
            <rect
              key={`${c[0]},${c[1]}`}
              x={x - (movendo ? 80 : 55)}
              y={-y - (movendo ? 80 : 55)}
              width={movendo ? 160 : 110}
              height={movendo ? 160 : 110}
              fill="var(--superficie)"
              stroke={movendo ? SEL : "var(--tinta)"}
              strokeWidth={movendo ? 3 : 1.5}
              vectorEffect="non-scaling-stroke"
              className="cursor-grab"
              onPointerDown={(e) => {
                e.stopPropagation();
                (e.target as Element).setPointerCapture?.(e.pointerId);
                setCanto({ de: c, para: c });
              }}
            >
              <title>
                canto ({formatar(c[0], unidade)}, {formatar(c[1], unidade)}) — arraste para mover
              </title>
            </rect>
          );
        })}
      {canto && (
        <text className="num" x={canto.para[0]} y={-canto.para[1] - 140} fontSize={90} textAnchor="middle" fill="var(--tinta)">
          {formatar(canto.para[0], unidade)}, {formatar(canto.para[1], unidade)}
        </text>
      )}

      {/* editor: desenhando paredes (clique a clique; botão direito termina) */}
      {editor?.desenhando && cursor && (
        <g pointerEvents="none">
          {trilha && (
            <>
              <line x1={trilha[0]} y1={-trilha[1]} x2={cursor[0]} y2={-cursor[1]} stroke={GUIA} strokeWidth={1.5} strokeDasharray="8 5" vectorEffect="non-scaling-stroke" />
              <text x={(trilha[0] + cursor[0]) / 2} y={-(trilha[1] + cursor[1]) / 2 - 80} fontSize={100} textAnchor="middle" fill={GUIA} className="num">
                {formatar(Math.round(Math.hypot(cursor[0] - trilha[0], cursor[1] - trilha[1])), unidade)}
              </text>
            </>
          )}
          <circle cx={cursor[0]} cy={-cursor[1]} r={45} fill={GUIA} />
        </g>
      )}

      {/* escala: 1 m */}
      <g transform={`translate(${x0},${-y0 + margem / 2})`}>
        <line x1={0} y1={0} x2={1000} y2={0} stroke="var(--tinta-suave)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        <text x={500} y={-30} fontSize={80} textAnchor="middle" fill="var(--tinta-suave)" className="num">
          {formatar(1000, unidade)}
        </text>
      </g>

      <defs>
        <marker id="seta" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--tinta-suave)" />
        </marker>
        <pattern id="malha-10" width={100} height={100} patternUnits="userSpaceOnUse">
          <path d="M100,0 L0,0 L0,100" fill="none" stroke="var(--malha)" strokeWidth={6} />
        </pattern>
        <pattern id="malha" width={1000} height={1000} patternUnits="userSpaceOnUse">
          <rect width={1000} height={1000} fill="url(#malha-10)" />
          <path d="M1000,0 L0,0 L0,1000" fill="none" stroke="var(--linha)" strokeWidth={12} />
        </pattern>
      </defs>
    </svg>
  );
}
