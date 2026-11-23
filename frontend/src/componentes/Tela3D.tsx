import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { Cores, PavimentoTela } from "../api/cliente";
import { useCena } from "../dados";
import type { Pintura } from "../visor/Visor3D";

// three.js é pesado: só baixa quando a pessoa abre o 3D
const Visor3D = lazy(() => import("../visor/Visor3D"));

const INTEIRO = "__pavimento__";

/** Área principal no modo 3D, **ao vivo**: o 3D é montado da cena que o core calcula a cada
 * versão do projeto (rascunho incluído), então muda junto com a planta, sem render. O cômodo
 * da lista, ou o pavimento inteiro (a casa com o teto cortado), pintado com as cores do painel.
 * As fotos realistas (Blender) ficam em "Imagens". */
export function Tela3D({
  codigo,
  pavimento,
  comodo,
  comodos,
  aoComodo,
  cores,
  geometria,
  selecionado,
  aoSelecionarMovel,
  aoMoverMovel,
  aoGirarMovel,
}: {
  /** Arrastar o móvel no 3D: deslocamento em mm na planta. */
  aoMoverMovel?: (id: string, d: [number, number]) => void;
  aoGirarMovel?: (id: string) => void;
  codigo: string;
  pavimento: string;
  comodo: string | null;
  comodos: { id: string; nome?: string | null }[];
  aoComodo: (id: string) => void;
  /** Cores para pintar por cima (rascunho do painel ou a variação salva; ``null`` na base). */
  cores: Cores | null;
  geometria: PavimentoTela | undefined;
  selecionado: string | null;
  aoSelecionarMovel: (id: string) => void;
}) {
  const [inteiro, setInteiro] = useState(false);
  const atual = comodo ?? comodos[0]?.id ?? null;
  // no 3D não dá para clicar no cômodo: o da lista fica selecionado (abre o painel de cores)
  useEffect(() => {
    if (!comodo && comodos[0]) aoComodo(comodos[0].id);
  }, [comodo, comodos, aoComodo]);
  const cena = useCena(codigo, inteiro ? { pavimento } : { comodo: atual ?? "" }, inteiro || !!atual);
  const pintura = useMemo<Pintura | null>(() => {
    if (!atual || !geometria) return null;
    const aberturas = Object.fromEntries(geometria.aberturas.map((a) => [a.id, a.parede]));
    const moveis = Object.fromEntries(geometria.moveis.filter((m) => m.comodo === atual).map((m) => [m.id, m.tipo]));
    return { cores, ctx: { comodo: atual, pavimento: inteiro, aberturas, moveis } };
  }, [atual, geometria, cores, inteiro]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-linha bg-superficie px-3 py-1.5 text-sm">
        <select
          className="rounded-md border"
          value={inteiro ? INTEIRO : (atual ?? "")}
          onChange={(e) => {
            const v = e.target.value;
            setInteiro(v === INTEIRO);
            if (v !== INTEIRO) aoComodo(v);
          }}
        >
          <option value={INTEIRO}>Pavimento inteiro</option>
          {comodos.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome ?? c.id}
            </option>
          ))}
        </select>
        <span className="text-xs text-tinta-suave">
          Ao vivo · versão {cena.data?.versao ?? "…"}
          {cena.isFetching && " · atualizando…"}
          {inteiro && " · no pavimento pintam piso, teto, rodapé e móveis"}
        </span>
        <span className="text-xs text-tinta-suave">Fotos realistas: aba "Imagens"</span>
      </div>
      {cena.error && <p className="border-b border-erro bg-erro-fundo px-3 py-1 text-xs text-erro">{cena.error.message}</p>}
      <div className="min-h-0 flex-1">
        {cena.data ? (
          <Suspense fallback={<p className="p-4 text-tinta-suave">Carregando o visor…</p>}>
            <Visor3D
              cena={cena.data}
              chave={inteiro ? `pavimento:${pavimento}` : `comodo:${atual}`}
              pintura={pintura}
              selecionado={selecionado}
              aoMovel={aoSelecionarMovel}
              aoArrastar={aoMoverMovel}
              aoGirar={aoGirarMovel}
              moveis={geometria?.moveis.map((m) => m.id) ?? []}
            />
          </Suspense>
        ) : (
          <p className="p-4 text-tinta-suave">{atual || inteiro ? "montando o 3D…" : "Nenhum cômodo no projeto."}</p>
        )}
      </div>
    </div>
  );
}
