import { type ReactNode, useEffect, useRef, useState } from "react";

export const LARGURA_PADRAO = 384;
const MINIMA = 280;
const CHAVE = "coluna-largura";

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

/** Coluna da direita com largura ajustável: arraste a borda esquerda (ou ← → com ela em
 * foco). A largura fica lembrada neste navegador. */
export function ColunaLateral({ children }: { children: ReactNode }) {
  const [largura, setLargura] = useState(() => limitarLargura(lerLargura(), window.innerWidth));
  const coluna = useRef<HTMLElement>(null);

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

  return (
    <>
      <button
        type="button"
        aria-label="Ajustar a largura da coluna (arraste ou use as setas)"
        title="arraste para ajustar a largura"
        className="w-1.5 shrink-0 cursor-col-resize bg-stone-200 hover:bg-stone-300 focus-visible:bg-sky-300 focus-visible:outline-none"
        onPointerDown={arrastar}
        onDoubleClick={() => setLargura(limitarLargura(LARGURA_PADRAO, window.innerWidth))}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") setLargura((l) => limitarLargura(l + 24, window.innerWidth));
          if (e.key === "ArrowRight") setLargura((l) => limitarLargura(l - 24, window.innerWidth));
        }}
      />
      <aside ref={coluna} style={{ width: largura }} className="flex shrink-0 flex-col bg-stone-50">
        {children}
      </aside>
    </>
  );
}

export type Aba<T extends string> = { id: T; titulo: string; marca?: number };

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
    <div role="tablist" aria-label="Painéis" className="flex shrink-0 border-b border-stone-200 bg-white">
      {abas.map((a) => (
        <button
          key={a.id}
          role="tab"
          aria-selected={a.id === ativa}
          className={`flex-1 border-b-2 px-2 py-2 text-sm ${
            a.id === ativa ? "border-stone-800 font-semibold text-stone-900" : "border-transparent text-stone-500 hover:text-stone-800"
          }`}
          onClick={() => aoTrocar(a.id)}
        >
          {a.titulo}
          {a.marca ? (
            <span className="ml-1 rounded-full bg-amber-100 px-1.5 text-xs font-normal text-amber-800">{a.marca}</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
