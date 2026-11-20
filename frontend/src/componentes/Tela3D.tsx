import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { type Cores, type InfoRender, type PavimentoTela, URL_API } from "../api/cliente";
import { usePedirRenderPavimento, useRenders, useRendersPavimento } from "../dados";
import type { Pintura } from "../visor/Visor3D";

// three.js é pesado: só baixa quando a pessoa abre o 3D
const Visor3D = lazy(() => import("../visor/Visor3D"));

const INTEIRO = "__pavimento__";
const ATIVOS = new Set(["na_fila", "rodando"]);

/** Área principal no modo 3D: o modelo do render pronto mais recente do cômodo, ou o do
 * pavimento inteiro (a casa com o teto cortado), pintado ao vivo com as cores do painel. */
export function Tela3D({
  codigo,
  pavimento,
  comodo,
  comodos,
  versaoProjeto,
  aoComodo,
  variacao,
  cores,
  geometria,
  selecionado,
  aoSelecionarMovel,
}: {
  codigo: string;
  pavimento: string;
  comodo: string | null;
  comodos: { id: string; nome?: string | null }[];
  versaoProjeto: number | undefined;
  aoComodo: (id: string) => void;
  /** Variação ativa do cômodo no painel de cores (o modelo dela é o preferido). */
  variacao: string;
  /** Rascunho das cores do painel (``null`` na base). */
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
  const doComodo = useRenders(codigo, atual ?? "").data ?? [];
  const doPavimento = useRendersPavimento(codigo, pavimento, inteiro).data ?? [];
  const pedir = usePedirRenderPavimento(codigo, pavimento);
  const lista = inteiro ? doPavimento : atual ? doComodo : [];
  // o modelo da variação ativa vem com as cores dela; sem ele, o mais recente
  const r = lista.find((x) => x.modelo_url && (inteiro || x.variacao === variacao)) ?? lista.find((x) => x.modelo_url);
  const pintura = useMemo<Pintura | null>(() => {
    if (!atual || !geometria) return null;
    const aberturas = Object.fromEntries(geometria.aberturas.map((a) => [a.id, a.parede]));
    const moveis = Object.fromEntries(geometria.moveis.filter((m) => m.comodo === atual).map((m) => [m.id, m.tipo]));
    return { cores, ctx: { comodo: atual, pavimento: inteiro, aberturas, moveis } };
  }, [atual, geometria, cores, inteiro]);
  const rodando = inteiro ? doPavimento.find((x) => ATIVOS.has(x.status)) : undefined;
  const falhou = inteiro && doPavimento[0]?.status === "erro" ? doPavimento[0] : undefined;
  const desatualizado = r && versaoProjeto !== undefined && r.versao_projeto !== versaoProjeto;

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-stone-200 bg-white px-3 py-1.5 text-sm">
        <select
          className="rounded border"
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
        {inteiro && (
          <button
            className="rounded border border-stone-300 bg-white px-2 py-0.5 hover:bg-stone-100 disabled:opacity-50"
            disabled={!!rodando || pedir.isPending}
            onClick={() => pedir.mutate({ qualidade: "rascunho" })}
          >
            {r ? "atualizar modelo da casa" : "gerar modelo da casa"}
          </button>
        )}
        {rodando && <Andamento r={rodando} />}
        {pedir.error && <span className="text-xs text-red-700">{pedir.error.message}</span>}
        {cores && r && (
          <span className="text-xs text-stone-500">
            cores do painel aplicadas ao vivo{inteiro && " (no pavimento: piso, teto, rodapé e móveis)"}
          </span>
        )}
        {r && (
          <span className="text-xs text-stone-500">
            modelo do render de {new Date(r.criado_em).toLocaleString("pt-BR")} · versão {r.versao_projeto}
          </span>
        )}
        {desatualizado && (
          <span className="text-xs text-amber-700">
            {inteiro
              ? "o projeto mudou depois deste modelo: clique em atualizar"
              : 'o projeto mudou depois deste render: as cores aparecem ao vivo; medidas e móveis novos só com um rascunho em "Imagens 3D"'}
          </span>
        )}
      </div>
      {falhou && !rodando && (
        <p className="border-b border-red-200 bg-red-50 px-3 py-1 text-xs text-red-800">
          o último modelo da casa falhou: {falhou.erro?.split("\n")[0]}
        </p>
      )}
      <div className="min-h-0 flex-1">
        {r?.modelo_url ? (
          <Suspense fallback={<p className="p-4 text-stone-500">carregando o visor…</p>}>
            <Visor3D
              key={r.modelo_url}
              url={URL_API + r.modelo_url}
              pintura={pintura}
              selecionado={selecionado}
              aoMovel={aoSelecionarMovel}
              moveis={geometria?.moveis.map((m) => m.id) ?? []}
            />
          </Suspense>
        ) : (
          <p className="p-4 text-stone-500">
            {inteiro
              ? rodando
                ? "gerando o modelo da casa…"
                : 'Ainda não há modelo da casa: clique em "gerar modelo da casa" (segundos).'
              : atual
                ? 'Ainda não há modelo 3D deste cômodo: peça um rascunho no painel "Imagens 3D" (segundos).'
                : "Nenhum cômodo no projeto."}
          </p>
        )}
      </div>
    </div>
  );
}

function Andamento({ r }: { r: InfoRender }) {
  return (
    <span className="text-xs text-stone-600">
      {r.status === "na_fila" ? "na fila" : `gerando ${Math.round(r.progresso * 100)}%`}
      {r.restante_s != null && ` · ~${Math.ceil(r.restante_s)} s`}
    </span>
  );
}
