import { useEffect, useRef, useState } from "react";
import type { Cores, MovelTela, PavimentoTela, Problema } from "../api/cliente";
import { PADRAO } from "./PainelCores";
import { formatar, type Unidade } from "../unidades";
import { encaixar, vertices, type Pt } from "../editor/geometria";

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

const AZUL = "#0284c7";

/** y do pavimento é para cima; no SVG é para baixo: inverte só aqui. */
const xy = ([x, y]: Pt | readonly number[]) => `${x},${-y}`;
const pontos = (lista: (Pt | readonly number[])[]) => lista.map(xy).join(" ");

const PASSO = 10; // arrastar anda de 1 em 1 cm

const COR_MOVEL: Record<string, string> = {
  cama: "#e7d3b8",
  guarda_roupa: "#c9b08f",
  armario: "#c9b08f",
  sofa: "#b8c7d9",
  tv: "#55606b",
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
  comodoSelecionado,
  aoSelecionarComodo,
  cores,
  editor,
}: {
  editor?: ModoEditor;
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
}) {
  const svg = useRef<SVGSVGElement>(null);
  // ``tela``: onde o clique começou (px); ``solto``: já passou da folga e está arrastando
  const [arrasto, setArrasto] = useState<{ id: string; ini: Pt; d: Pt; tela: Pt; solto: boolean } | null>(null);
  const [canto, setCanto] = useState<{ de: Pt; para: Pt } | null>(null);
  const [trilha, setTrilha] = useState<Pt | null>(null);
  const [cursor, setCursor] = useState<Pt | null>(null);
  const cantos = vertices(geometria.paredes.map((p) => p.eixo));
  const desenhando = editor?.desenhando ?? false;
  useEffect(() => {
    if (!desenhando) setTrilha(null); // parou de desenhar: a próxima sequência começa do zero
  }, [desenhando]);
  const ehSel = (tipo: Item["tipo"], id: string) => editor?.item?.tipo === tipo && editor.item.id === id;

  const lim = geometria.limites ?? [
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

  return (
    <svg
      ref={svg}
      viewBox={viewBox}
      className="h-full w-full touch-none select-none bg-white"
      onPointerDown={(e) => {
        if (editor?.desenhando) {
          if (e.button !== 0) return;
          const p = encaixar(emMm(e), cantos, trilha);
          if (trilha && (p[0] !== trilha[0] || p[1] !== trilha[1])) editor.aoNovaParede(trilha, p);
          setTrilha(p);
          return;
        }
        if (e.target === svg.current) {
          aoSelecionar(null);
          editor?.aoItem(null);
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
          setCursor(encaixar(emMm(e), cantos, trilha));
          return;
        }
        if (canto) {
          setCanto({ ...canto, para: encaixar(emMm(e), cantos, null, canto.de) });
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
        if (!arrasto) return;
        const m = geometria.moveis.find((x) => x.id === arrasto.id);
        if (m && (arrasto.d[0] || arrasto.d[1]))
          aoMover(m, [m.centro[0] + arrasto.d[0], m.centro[1] + arrasto.d[1]]);
        setArrasto(null);
      }}
    >
      {/* cômodos */}
      {geometria.comodos.map((c) => {
        const pintado = c.id === comodoSelecionado && cores;
        return (
          c.poligono && (
            <polygon
              key={c.id}
              points={pontos(c.poligono)}
              fill={pintado && cores.piso ? cores.piso : "#f5f1ea"}
              stroke={(editor ? ehSel("comodo", c.id) : c.id === comodoSelecionado) ? "#0369a1" : "none"}
              strokeWidth={20}
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

      {/* paredes, com os vãos abertos por cima */}
      {geometria.paredes.map((p) => {
        const marcada = ehSel("parede", p.id) || editor?.destacadas.includes(p.id);
        return (
          <polygon
            key={p.id}
            points={pontos(p.corpo)}
            fill={marcada ? AZUL : "#3f3a36"}
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
            fill={a.tipo === "janela" ? "#dbeafe" : "#f5f1ea"}
            stroke={ehSel("abertura", a.id) ? AZUL : "none"}
            strokeWidth={25}
          />
          {a.giro && (
            <polygon
              points={pontos(a.giro)}
              fill="none"
              stroke="#8a817a"
              strokeWidth={12}
              strokeDasharray="40 30"
            />
          )}
        </g>
      ))}

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
              <circle r={85} fill={ehSel("instalacao", i.id) ? "#e0f2fe" : "#fff"} stroke={ehSel("instalacao", i.id) ? AZUL : "#b45309"} strokeWidth={ehSel("instalacao", i.id) ? 24 : 12} />
              <text fontSize={LETRA[i.tipo]?.length === 2 ? 70 : 90} textAnchor="middle" dy={30} fill="#b45309" fontWeight={600}>
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
            <polygon
              points={pontos(m.contorno?.length ? m.contorno : m.cantos)}
              fill={
                (m.comodo === comodoSelecionado && (cores?.moveis?.[m.id] ?? cores?.moveis?.[m.tipo])) ||
                COR_MOVEL[m.tipo] ||
                "#d6d3d1"
              }
              fillOpacity={m.elevado ? 0.5 : 0.9}
              stroke={sel ? "#0369a1" : "#57534e"}
              strokeWidth={sel ? 30 : 12}
              strokeDasharray={m.elevado ? "50 30" : undefined}
            />
            {!fino && <line
              x1={ini[0]}
              y1={-ini[1]}
              x2={fim[0]}
              y2={-fim[1]}
              stroke="#57534e"
              strokeWidth={10}
              markerEnd="url(#seta)"
            />}
            <text x={rotulo[0]} y={-rotulo[1]} fontSize={90} textAnchor="middle" dy={30} fill="#292524">
              {m.nome ?? m.tipo}
            </text>
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
              fill="#57534e"
              stroke="#ffffff"
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
            stroke={p.severidade === "erro" ? "#dc2626" : "#f59e0b"}
            strokeWidth={20}
          >
            <title>{p.mensagem}</title>
          </circle>
        ))}

      {/* editor: alças nos cantos (arrastar move o canto e as paredes que se encontram nele) */}
      {editor &&
        !editor.desenhando &&
        cantos.map((c) => {
          const movendo = canto && canto.de[0] === c[0] && canto.de[1] === c[1];
          const [x, y] = movendo ? canto.para : c;
          return (
            <circle
              key={`${c[0]},${c[1]}`}
              cx={x}
              cy={-y}
              r={movendo ? 90 : 60}
              fill="#fff"
              stroke={AZUL}
              strokeWidth={18}
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
            </circle>
          );
        })}
      {canto && (
        <text x={canto.para[0]} y={-canto.para[1] - 140} fontSize={90} textAnchor="middle" fill={AZUL}>
          {formatar(canto.para[0], unidade)}, {formatar(canto.para[1], unidade)}
        </text>
      )}

      {/* editor: desenhando paredes (clique a clique; botão direito termina) */}
      {editor?.desenhando && cursor && (
        <g pointerEvents="none">
          {trilha && (
            <>
              <line x1={trilha[0]} y1={-trilha[1]} x2={cursor[0]} y2={-cursor[1]} stroke={AZUL} strokeWidth={40} strokeDasharray="80 40" />
              <text x={(trilha[0] + cursor[0]) / 2} y={-(trilha[1] + cursor[1]) / 2 - 80} fontSize={100} textAnchor="middle" fill={AZUL}>
                {formatar(Math.round(Math.hypot(cursor[0] - trilha[0], cursor[1] - trilha[1])), unidade)}
              </text>
            </>
          )}
          <circle cx={cursor[0]} cy={-cursor[1]} r={50} fill={AZUL} />
        </g>
      )}

      {/* escala: 1 m */}
      <g transform={`translate(${x0},${-y0 + margem / 2})`}>
        <line x1={0} y1={0} x2={1000} y2={0} stroke="#57534e" strokeWidth={15} />
        <text x={500} y={-30} fontSize={80} textAnchor="middle" fill="#57534e">
          {formatar(1000, unidade)}
        </text>
      </g>

      <defs>
        <marker id="seta" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="#57534e" />
        </marker>
      </defs>
    </svg>
  );
}
