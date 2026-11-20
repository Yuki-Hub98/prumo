import { useState } from "react";
import { api, ou, type Esquemas } from "../api/cliente";
import { useEditar, usePlanejado } from "../dados";
import {
  adicionarEspaco,
  adicionarVao,
  alternarPorta,
  alturaEspaco,
  type Construcao,
  larguraVao,
  moverEspaco,
  removerEspaco,
  removerVao,
  TIPOS_ESPACO,
  tipoEspaco,
  type TipoEspaco,
} from "../planejado";
import { formatar, paraMm, type Unidade } from "../unidades";

type Vista = Esquemas["PlanejadoTela"];

const botao = "rounded border border-stone-300 px-2 py-0.5 text-sm hover:bg-stone-100 disabled:opacity-40";
const mini = "rounded px-1 text-xs text-stone-500 hover:bg-stone-200 disabled:opacity-30";

/** Cor de cada elemento na vista de frente. */
const PINTURA: Record<string, { fill: string; stroke: string }> = {
  lateral: { fill: "#d6d3d1", stroke: "#78716c" },
  base: { fill: "#d6d3d1", stroke: "#78716c" },
  tampo: { fill: "#d6d3d1", stroke: "#78716c" },
  divisoria: { fill: "#d6d3d1", stroke: "#78716c" },
  prateleira: { fill: "#d6d3d1", stroke: "#78716c" },
  rodape: { fill: "#a8a29e", stroke: "#57534e" },
  gaveta: { fill: "#fde68a", stroke: "#b45309" },
  nicho: { fill: "#fafaf9", stroke: "#e7e5e4" },
  cabideiro: { fill: "#fafaf9", stroke: "#e7e5e4" },
};

/** Desenho da frente, em escala: estrutura, gavetas, nichos, cabideiros e (opcional) portas. */
function Frente({ vista, portas }: { vista: Vista; portas: boolean }) {
  const { largura: L, altura: A } = vista;
  const y = (r: { y: number; altura: number }) => A - r.y - r.altura; // SVG: y para baixo
  return (
    <svg viewBox={`-20 -20 ${L + 40} ${A + 40}`} className="max-h-72 w-full rounded border border-stone-200 bg-white">
      {vista.retangulos
        .filter((r) => r.tipo !== "porta")
        .map((r, i) => {
          const p = PINTURA[r.tipo] ?? { fill: "#e7e5e4", stroke: "#78716c" };
          return (
            <g key={i}>
              <rect x={r.x} y={y(r)} width={r.largura} height={r.altura} fill={p.fill} stroke={p.stroke} strokeWidth={3} />
              {r.tipo === "cabideiro" && (
                <line x1={r.x + 30} x2={r.x + r.largura - 30} y1={y(r) + 60} y2={y(r) + 60} stroke="#57534e" strokeWidth={14} />
              )}
              {r.tipo === "gaveta" && (
                <line
                  x1={r.x + r.largura / 2 - Math.min(80, r.largura / 5)}
                  x2={r.x + r.largura / 2 + Math.min(80, r.largura / 5)}
                  y1={y(r) + Math.min(50, r.altura / 3)}
                  y2={y(r) + Math.min(50, r.altura / 3)}
                  stroke="#57534e"
                  strokeWidth={12}
                  strokeLinecap="round"
                />
              )}
              {r.rotulo && r.altura > 90 && r.tipo !== "gaveta" && (
                <text x={r.x + r.largura / 2} y={y(r) + r.altura / 2} textAnchor="middle" dominantBaseline="middle" fontSize={Math.min(70, r.largura / 6)} fill="#78716c">
                  {r.rotulo}
                </text>
              )}
            </g>
          );
        })}
      {portas &&
        vista.retangulos
          .filter((r) => r.tipo === "porta")
          .map((r, i) => (
            <rect key={`p${i}`} x={r.x + 4} y={y(r) + 4} width={r.largura - 8} height={r.altura - 8} fill="#bae6fd" fillOpacity={0.45} stroke="#0369a1" strokeWidth={4} strokeDasharray="30 18" />
          ))}
    </svg>
  );
}

/** Campo de medida curto: vazio = "auto" (divide o que sobra); Enter ou sair do campo aplica. */
function CampoAuto({
  mm,
  unidade,
  rotulo,
  aoMudar,
}: {
  mm: number | null | undefined;
  unidade: Unidade;
  rotulo: string;
  aoMudar: (mm: number | null) => void;
}) {
  const atual = mm != null ? formatar(mm, unidade, false) : "";
  const [texto, setTexto] = useState(atual);
  const [focado, setFocado] = useState(false);
  const mostrado = focado ? texto : atual;
  const aplicar = () => {
    const t = texto.trim();
    const novo = t === "" ? null : paraMm(t, unidade);
    if (t !== "" && novo === null) return setTexto(atual);
    if (novo !== (mm ?? null)) aoMudar(novo);
  };
  return (
    <input
      aria-label={rotulo}
      title={`${rotulo} em ${unidade} (vazio = automático)`}
      placeholder="auto"
      className="w-14 rounded border px-1 text-right text-xs"
      value={mostrado}
      onFocus={() => {
        setTexto(atual);
        setFocado(true);
      }}
      onChange={(e) => setTexto(e.target.value)}
      onBlur={() => {
        setFocado(false);
        aplicar();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
      }}
    />
  );
}

/**
 * Montar o móvel por dentro: vista de frente em escala e, embaixo, cada vão da esquerda para
 * a direita com os espaços de baixo para cima (gaveta, nicho, cabideiro), com ou sem porta.
 * Cada mudança vai para o rascunho (Desfazer volta) e o core confere se cabe.
 */
export function EditorPlanejado({
  codigo,
  comodo,
  id,
  construcao,
  portas,
  unidade,
}: {
  codigo: string;
  comodo: string;
  id: string;
  construcao: Construcao | null | undefined;
  portas: "abrir" | "correr" | null | undefined;
  unidade: Unidade;
}) {
  const editar = useEditar(codigo);
  const vista = usePlanejado(codigo, comodo, id, !!construcao);
  const [verPortas, setVerPortas] = useState(false);
  const caminho = { codigo, comodo, id_: id };

  const gravar = (nova: Construcao | null) =>
    editar.mutate((versao) =>
      ou(
        api.PUT("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/construcao", {
          params: { path: caminho, query: { versao } },
          body: { construcao: nova },
        }),
      ),
    );

  if (!construcao)
    return (
      <section className="border-b border-stone-200 p-3">
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-500">Montar por dentro</h3>
        <p className="mb-2 text-sm text-stone-500">
          Divida em vãos e empilhe gavetas, nichos e cabideiros, com ou sem porta. Começa com uma sugestão para o tipo
          do móvel.
        </p>
        <button
          className={botao}
          disabled={editar.isPending}
          onClick={() =>
            editar.mutate((versao) =>
              ou(
                api.POST("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/construcao/sugerir", {
                  params: { path: caminho, query: { versao } },
                }),
              ),
            )
          }
        >
          montar por dentro
        </button>
        {editar.error && <p className="mt-1 text-sm text-red-700">{editar.error.message}</p>}
      </section>
    );

  const c = construcao;
  const v = vista.data;
  const comPorta = (i: number) => c.vaos[i].porta !== false;
  return (
    <section className="border-b border-stone-200 p-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-stone-500">Montar por dentro</h3>
        <label className="flex items-center gap-1 text-xs text-stone-500">
          <input type="checkbox" checked={verPortas} onChange={(e) => setVerPortas(e.target.checked)} />
          ver portas
        </label>
      </div>
      {v ? <Frente vista={v} portas={verPortas} /> : <p className="text-sm text-stone-500">calculando…</p>}
      {vista.error && <p className="mt-1 text-sm text-red-700">{vista.error.message}</p>}

      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-stone-500">portas</span>
        {([null, "abrir", "correr"] as const).map((t) => (
          <button
            key={t ?? "sem"}
            className={`rounded px-2 py-0.5 text-xs ${(portas ?? null) === t ? "bg-stone-800 text-white" : "border border-stone-300"}`}
            disabled={editar.isPending || (portas ?? null) === t}
            onClick={() =>
              editar.mutate((versao) =>
                ou(
                  api.PATCH("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}", {
                    params: { path: caminho, query: { versao } },
                    body: { portas: t },
                  }),
                ),
              )
            }
          >
            {t === null ? "sem portas" : `de ${t}`}
          </button>
        ))}
      </div>

      <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
        {c.vaos.map((vao, i) => (
          <div key={i} className="min-w-[9.5rem] shrink-0 rounded border border-stone-300 bg-white p-1.5">
            <div className="mb-1 flex items-center justify-between gap-1">
              <span className="text-xs font-medium">Vão {i + 1}</span>
              <button className={mini} title="tirar este vão" disabled={c.vaos.length <= 1 || editar.isPending} onClick={() => gravar(removerVao(c, i))}>
                ✕
              </button>
            </div>
            <div className="mb-1 flex items-center justify-between gap-1 text-xs text-stone-500">
              largura
              <CampoAuto mm={vao.largura?.valor} unidade={unidade} rotulo={`largura do vão ${i + 1}`} aoMudar={(mm) => gravar(larguraVao(c, i, mm))} />
            </div>
            {v?.larguras_vaos[i] !== undefined && !vao.largura && (
              <p className="-mt-1 mb-1 text-right text-[10px] text-stone-400">= {formatar(v.larguras_vaos[i], unidade)}</p>
            )}
            {portas === "abrir" && (
              <label className="mb-1 flex items-center gap-1 text-xs">
                <input type="checkbox" checked={comPorta(i)} disabled={editar.isPending} onChange={() => gravar(alternarPorta(c, i))} />
                com porta
              </label>
            )}
            {/* de cima para baixo na tela, como no móvel */}
            <ol className="flex flex-col-reverse gap-1">
              {vao.espacos.map((esp, j) => (
                <li key={j} className="rounded bg-stone-50 p-1">
                  <div className="flex items-center gap-1">
                    <select
                      aria-label={`espaço ${j + 1} do vão ${i + 1}`}
                      className="min-w-0 flex-1 rounded border text-xs"
                      value={esp.tipo}
                      disabled={editar.isPending}
                      onChange={(e) => gravar(tipoEspaco(c, i, j, e.target.value as TipoEspaco))}
                    >
                      {TIPOS_ESPACO.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.nome}
                        </option>
                      ))}
                    </select>
                    <button className={mini} title="tirar" disabled={vao.espacos.length <= 1 || editar.isPending} onClick={() => gravar(removerEspaco(c, i, j))}>
                      ✕
                    </button>
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-1 text-[11px] text-stone-500">
                    <span className="flex">
                      <button className={mini} title="subir" disabled={j === vao.espacos.length - 1 || editar.isPending} onClick={() => gravar(moverEspaco(c, i, j, 1))}>
                        ↑
                      </button>
                      <button className={mini} title="descer" disabled={j === 0 || editar.isPending} onClick={() => gravar(moverEspaco(c, i, j, -1))}>
                        ↓
                      </button>
                    </span>
                    <span className="flex items-center gap-1">
                      altura
                      <CampoAuto mm={esp.altura?.valor} unidade={unidade} rotulo={`altura do espaço ${j + 1} do vão ${i + 1}`} aoMudar={(mm) => gravar(alturaEspaco(c, i, j, mm))} />
                    </span>
                  </div>
                  {!esp.altura && v?.alturas[i]?.[j] !== undefined && (
                    <p className="text-right text-[10px] text-stone-400">= {formatar(v.alturas[i][j], unidade)}</p>
                  )}
                </li>
              ))}
            </ol>
            <div className="mt-1 flex flex-wrap gap-1">
              {TIPOS_ESPACO.map((t) => (
                <button key={t.id} className={mini} disabled={editar.isPending} onClick={() => gravar(adicionarEspaco(c, i, t.id))} title={`pôr ${t.nome.toLowerCase()} em cima`}>
                  + {t.id}
                </button>
              ))}
            </div>
          </div>
        ))}
        <button className={`${botao} shrink-0 self-start`} disabled={editar.isPending} onClick={() => gravar(adicionarVao(c))}>
          + vão
        </button>
      </div>

      {v && (
        <div className="mt-2 text-xs text-stone-500">
          <p>
            {v.pecas} peças de chapa ·{" "}
            {v.chapas.map((ch) => `${ch.chapas} chapa${ch.chapas > 1 ? "s" : ""} de ${ch.material} ${ch.espessura} mm`).join(" · ")}
          </p>
          {v.ferragens.length > 0 && <p>Ferragens: {v.ferragens.join(", ")}</p>}
        </div>
      )}
      <div className="mt-2 flex items-center justify-between">
        <p className="text-xs text-stone-400">
          Medidas vazias dividem o que sobra. Porta de abrir é por vão (cobre gavetas e nichos dele); de correr cobre
          o móvel todo. Desfazer volta cada passo.
        </p>
        <button className="text-xs text-red-700 hover:underline" disabled={editar.isPending} onClick={() => gravar(null)}>
          desmontar
        </button>
      </div>
      {editar.error && <p className="mt-1 text-sm text-red-700">{editar.error.message}</p>}
    </section>
  );
}
