import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { Cores, PavimentoTela } from "../api/cliente";
import { useCena } from "../dados";
import type { Pintura } from "../visor/Visor3D";

// three.js é pesado: só baixa quando a pessoa abre o 3D
const Visor3D = lazy(() => import("../visor/Visor3D"));

const INTEIRO = "__pavimento__";
const CASA = "__casa__";

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
  andares = [],
}: {
  /** Andares do projeto (nome para o "Mostrar até" da casa toda). */
  andares?: { id: string; nome?: string | null }[];
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
  const [modo, setModo] = useState<"comodo" | "pavimento" | "casa">("comodo");
  const inteiro = modo === "pavimento";
  const casa = modo === "casa";
  const [ate, setAte] = useState<string | null>(null);
  const atual = comodo ?? comodos[0]?.id ?? null;
  // no 3D não dá para clicar no cômodo: o da lista fica selecionado (abre o painel de cores)
  useEffect(() => {
    if (!comodo && comodos[0]) aoComodo(comodos[0].id);
  }, [comodo, comodos, aoComodo]);
  const cena = useCena(
    codigo,
    casa ? { casa: true } : inteiro ? { pavimento } : { comodo: atual ?? "" },
    casa || inteiro || !!atual,
  );
  const ordem = casa ? (cena.data?.andares ?? []) : [];
  // "Mostrar até": o andar escolhido na tela, se ele estiver na casa; senão o de cima de todos
  const ateEfetivo = casa ? (ate && ordem.includes(ate) ? ate : (ordem.includes(pavimento) ? pavimento : ordem[ordem.length - 1] ?? null)) : null;
  const pintura = useMemo<Pintura | null>(() => {
    if (!atual || !geometria || casa) return null; // casa toda: cores padrão
    const aberturas = Object.fromEntries(geometria.aberturas.map((a) => [a.id, a.parede]));
    const moveis = Object.fromEntries(geometria.moveis.filter((m) => m.comodo === atual).map((m) => [m.id, m.tipo]));
    return { cores, ctx: { comodo: atual, pavimento: inteiro, aberturas, moveis } };
  }, [atual, geometria, cores, inteiro, casa]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-linha bg-superficie px-3 py-1.5 text-sm">
        <select
          className="rounded-md border"
          value={casa ? CASA : inteiro ? INTEIRO : (atual ?? "")}
          onChange={(e) => {
            const v = e.target.value;
            setModo(v === CASA ? "casa" : v === INTEIRO ? "pavimento" : "comodo");
            if (v !== INTEIRO && v !== CASA) aoComodo(v);
          }}
        >
          <option value={CASA}>Casa toda (andares)</option>
          <option value={INTEIRO}>Pavimento inteiro</option>
          {comodos.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome ?? c.id}
            </option>
          ))}
        </select>
        {casa && ordem.length > 1 && (
          <label className="flex items-center gap-1 text-xs text-tinta-suave">
            Mostrar até
            <select className="rounded-md border text-sm text-tinta" value={ateEfetivo ?? ""} onChange={(e) => setAte(e.target.value)}>
              {[...ordem].reverse().map((id) => (
                <option key={id} value={id}>
                  {andares.find((a) => a.id === id)?.nome ?? id}
                </option>
              ))}
            </select>
          </label>
        )}
        <span className="text-xs text-tinta-suave">
          Ao vivo · versão {cena.data?.versao ?? "…"}
          {cena.isFetching && " · atualizando…"}
          {inteiro && " · no pavimento pintam piso, teto, rodapé e móveis"}
          {casa && " · cores padrão; o teto do último andar mostrado segue o botão Teto"}
        </span>
        <span className="text-xs text-tinta-suave">Fotos realistas: aba "Imagens"</span>
      </div>
      {cena.error && <p className="border-b border-erro bg-erro-fundo px-3 py-1 text-xs text-erro">{cena.error.message}</p>}
      <div className="min-h-0 flex-1">
        {cena.data ? (
          <Suspense fallback={<p className="p-4 text-tinta-suave">Carregando o visor…</p>}>
            <Visor3D
              cena={cena.data}
              chave={casa ? "casa" : inteiro ? `pavimento:${pavimento}` : `comodo:${atual}`}
              andares={ordem}
              ate={ateEfetivo}
              pintura={pintura}
              selecionado={selecionado}
              aoMovel={aoSelecionarMovel}
              aoArrastar={casa ? undefined : aoMoverMovel}
              aoGirar={aoGirarMovel}
              moveis={geometria?.moveis.map((m) => m.id) ?? []}
            />
          </Suspense>
        ) : (
          <p className="p-4 text-tinta-suave">{atual || inteiro || casa ? "montando o 3D…" : "Nenhum cômodo no projeto."}</p>
        )}
      </div>
    </div>
  );
}
