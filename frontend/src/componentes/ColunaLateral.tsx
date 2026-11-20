import { type ReactNode, useEffect, useRef, useState } from "react";

export const LARGURA_PADRAO = 384;
const MINIMA = 280;
const CHAVE = "coluna-largura";
const CHAVE_FECHADA = "coluna-fechada";

function lerFechada(): boolean {
  try {
    return localStorage.getItem(CHAVE_FECHADA) === "1";
  } catch {
    return false;
  }
}

/** Ícone ☰ (três traços). */
function Hamburguer() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M3 5h14M3 10h14M3 15h14" />
    </svg>
  );
}

/** Largura da coluna dentro dos limites: nunca menor que 280 px nem tirando mais que
 * metade da janela da planta. */
export function limitarLargura(largura: number, janela: number): number {
  const maxima = Math.max(MINIMA, Math.round(janela / 2));
  return Math.min(maxima, Math.max(MINIMA, Math.round(largura)));
}

function lerLargura(): number {
  try {
    const v = Number(localStorage.getItem(CHAVE));
    return v > 0 ? v : LARGURA_PADRAO;
  } catch {
    return LARGURA_PADRAO; // sem armazenamento: vale só nesta aba
  }
}

/** Coluna da direita com título e botão ☰ para fechar/abrir, e largura ajustável: arraste a
 * borda esquerda (ou ← → com ela em foco). Largura e aberta/fechada ficam lembradas neste
 * navegador. */
export function ColunaLateral({ titulo, children }: { titulo: string; children: ReactNode }) {
  const [largura, setLargura] = useState(() => limitarLargura(lerLargura(), window.innerWidth));
  const [fechada, setFechada] = useState(lerFechada);
  const coluna = useRef<HTMLElement>(null);

  const alternar = () =>
    setFechada((f) => {
      try {
        localStorage.setItem(CHAVE_FECHADA, f ? "0" : "1");
      } catch {
        /* sem armazenamento */
      }
      return !f;
    });
  const botaoMenu = (
    <button
      type="button"
      onClick={alternar}
      aria-expanded={!fechada}
      aria-controls="coluna-lateral"
      aria-label={fechada ? `Abrir ${titulo.toLowerCase()}` : `Fechar ${titulo.toLowerCase()}`}
      title={fechada ? "Abrir o painel" : "Fechar o painel"}
      className="rounded-md p-1 text-tinta-suave hover:bg-superficie-2 hover:text-tinta focus-visible:outline-2 focus-visible:outline-foco"
    >
      <Hamburguer />
    </button>
  );

  useEffect(() => {
    try {
      localStorage.setItem(CHAVE, String(largura));
    } catch {
      /* sem armazenamento */
    }
  }, [largura]);
  useEffect(() => {
    const ajustar = () => setLargura((l) => limitarLargura(l, window.innerWidth));
    window.addEventListener("resize", ajustar);
    return () => window.removeEventListener("resize", ajustar);
  }, []);

  const arrastar = (e: React.PointerEvent<HTMLButtonElement>) => {
    const alca = e.currentTarget;
    alca.setPointerCapture(e.pointerId);
    const direita = coluna.current?.getBoundingClientRect().right ?? window.innerWidth;
    const mover = (ev: PointerEvent) => setLargura(limitarLargura(direita - ev.clientX, window.innerWidth));
    alca.addEventListener("pointermove", mover);
    alca.addEventListener("pointerup", () => alca.removeEventListener("pointermove", mover), { once: true });
  };

  if (fechada) {
    return (
      <aside className="flex shrink-0 flex-col items-center border-l border-linha bg-papel py-1.5">
        {botaoMenu}
      </aside>
    );
  }

  return (
    <>
      <button
        type="button"
        aria-label="Ajustar a largura da coluna (arraste ou use as setas)"
        title="Arraste para ajustar a largura"
        className="w-1.5 shrink-0 cursor-col-resize bg-superficie-2 hover:bg-superficie-2 focus-visible:bg-foco focus-visible:outline-none"
        onPointerDown={arrastar}
        onDoubleClick={() => setLargura(limitarLargura(LARGURA_PADRAO, window.innerWidth))}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") setLargura((l) => limitarLargura(l + 24, window.innerWidth));
          if (e.key === "ArrowRight") setLargura((l) => limitarLargura(l - 24, window.innerWidth));
        }}
      />
      <aside id="coluna-lateral" ref={coluna} style={{ width: largura }} className="flex shrink-0 flex-col bg-papel">
        <div className="flex shrink-0 items-center gap-2 border-b border-linha bg-superficie px-2 py-1.5">
          {botaoMenu}
          <h2 className="text-sm font-semibold text-tinta">{titulo}</h2>
        </div>
        {children}
      </aside>
    </>
  );
}

/** ``marca``: contador depois do rótulo; ``tom``: cor dele (a pior gravidade presente). */
export type Aba<T extends string> = { id: T; titulo: string; marca?: number; tom?: "erro" | "aviso" | "info" | null };

const TOM = {
  erro: "bg-erro text-erro-sobre",
  aviso: "bg-aviso-fundo text-aviso",
  info: "bg-superficie-2 text-tinta-suave",
} as const;

/** Abas da coluna: uma coisa por vez, a barra fica fixa no topo enquanto o conteúdo rola. */
export function Abas<T extends string>({
  abas,
  ativa,
  aoTrocar,
}: {
  abas: Aba<T>[];
  ativa: T;
  aoTrocar: (id: T) => void;
}) {
  return (
    <div role="tablist" aria-label="Painéis" className="flex shrink-0 border-b border-linha bg-superficie">
      {abas.map((a) => (
        <button
          key={a.id}
          role="tab"
          aria-selected={a.id === ativa}
          className={`flex-1 border-b-2 px-2 py-2 text-sm ${
            a.id === ativa ? "border-tinta font-medium text-tinta" : "border-transparent font-medium text-tinta-suave hover:text-tinta"
          }`}
          onClick={() => aoTrocar(a.id)}
        >
          {a.titulo}
          {a.marca ? (
            <span className={`ml-1 rounded-full px-1.5 text-xs font-semibold ${TOM[a.tom ?? "info"]}`}>{a.marca}</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
