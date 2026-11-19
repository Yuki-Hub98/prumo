import { lazy, Suspense } from "react";
import { URL_API } from "../api/cliente";
import { useRenders } from "../dados";

// three.js é pesado: só baixa quando a pessoa abre o 3D
const Visor3D = lazy(() => import("../visor/Visor3D"));

/** Área principal no modo 3D: o modelo do render pronto mais recente do cômodo. */
export function Tela3D({
  codigo,
  comodo,
  comodos,
  versaoProjeto,
  aoComodo,
}: {
  codigo: string;
  comodo: string | null;
  comodos: { id: string; nome?: string | null }[];
  versaoProjeto: number | undefined;
  aoComodo: (id: string) => void;
}) {
  const atual = comodo ?? comodos[0]?.id ?? null;
  const renders = useRenders(codigo, atual ?? "").data ?? [];
  const r = atual ? renders.find((x) => x.modelo_url) : undefined;
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-stone-200 bg-white px-3 py-1.5 text-sm">
        <select className="rounded border" value={atual ?? ""} onChange={(e) => aoComodo(e.target.value)}>
          {comodos.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome ?? c.id}
            </option>
          ))}
        </select>
        {r && (
          <span className="text-xs text-stone-500">
            modelo do render de {new Date(r.criado_em).toLocaleString("pt-BR")} · versão {r.versao_projeto}
          </span>
        )}
        {r && versaoProjeto !== undefined && r.versao_projeto !== versaoProjeto && (
          <span className="text-xs text-amber-700">
            o projeto mudou depois deste render: peça um rascunho em "Imagens 3D" para atualizar
          </span>
        )}
      </div>
      <div className="min-h-0 flex-1">
        {r?.modelo_url ? (
          <Suspense fallback={<p className="p-4 text-stone-500">carregando o visor…</p>}>
            <Visor3D key={r.modelo_url} url={URL_API + r.modelo_url} />
          </Suspense>
        ) : (
          <p className="p-4 text-stone-500">
            {atual
              ? 'Ainda não há modelo 3D deste cômodo: peça um rascunho no painel "Imagens 3D" (segundos).'
              : "Nenhum cômodo no projeto."}
          </p>
        )}
      </div>
    </div>
  );
}
