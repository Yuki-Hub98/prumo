import { lazy, Suspense, useState } from "react";
import { type InfoRender, URL_API } from "../api/cliente";
import { usePedirRenderPavimento, useRenders, useRendersPavimento } from "../dados";

// three.js é pesado: só baixa quando a pessoa abre o 3D
const Visor3D = lazy(() => import("../visor/Visor3D"));

const INTEIRO = "__pavimento__";
const ATIVOS = new Set(["na_fila", "rodando"]);

/** Área principal no modo 3D: o modelo do render pronto mais recente do cômodo, ou o do
 * pavimento inteiro (a casa com o teto cortado). */
export function Tela3D({
  codigo,
  pavimento,
  comodo,
  comodos,
  versaoProjeto,
  aoComodo,
}: {
  codigo: string;
  pavimento: string;
  comodo: string | null;
  comodos: { id: string; nome?: string | null }[];
  versaoProjeto: number | undefined;
  aoComodo: (id: string) => void;
}) {
  const [inteiro, setInteiro] = useState(false);
  const atual = comodo ?? comodos[0]?.id ?? null;
  const doComodo = useRenders(codigo, atual ?? "").data ?? [];
  const doPavimento = useRendersPavimento(codigo, pavimento, inteiro).data ?? [];
  const pedir = usePedirRenderPavimento(codigo, pavimento);
  const lista = inteiro ? doPavimento : atual ? doComodo : [];
  const r = lista.find((x) => x.modelo_url);
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
        {r && (
          <span className="text-xs text-stone-500">
            modelo do render de {new Date(r.criado_em).toLocaleString("pt-BR")} · versão {r.versao_projeto}
          </span>
        )}
        {desatualizado && (
          <span className="text-xs text-amber-700">
            {inteiro
              ? "o projeto mudou depois deste modelo: clique em atualizar"
              : 'o projeto mudou depois deste render: peça um rascunho em "Imagens 3D" para atualizar'}
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
            <Visor3D key={r.modelo_url} url={URL_API + r.modelo_url} />
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
