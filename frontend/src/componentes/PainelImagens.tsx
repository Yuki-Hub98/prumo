import { URL_API, type InfoRender } from "../api/cliente";
import { useEstimativas, usePedirRender, useRenders } from "../dados";
import { formatarTempo } from "../tempo";

const ROTULO: Record<string, string> = {
  na_fila: "na fila",
  rodando: "renderizando",
  pronto: "pronto",
  erro: "erro",
};

function Item({ r }: { r: InfoRender }) {
  const pct = Math.round(r.progresso * 100);
  return (
    <li className="rounded border border-stone-200 bg-white p-2 text-sm">
      <div className="flex justify-between">
        <span>
          <b>{r.variacao}</b> · {r.qualidade}
        </span>
        <span className={r.status === "erro" ? "text-red-700" : "text-stone-500"}>{ROTULO[r.status]}</span>
      </div>
      {r.status === "na_fila" && (
        <p className="text-xs text-stone-500">estimativa: ~{formatarTempo(r.estimativa_s)}</p>
      )}
      {r.status === "rodando" && (
        <>
          <div className="mt-1 h-2 overflow-hidden rounded bg-stone-200">
            <div className="h-full bg-sky-600 transition-all" style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-0.5 text-xs text-stone-500">
            imagem {r.imagem_atual ?? 1} de {r.imagens} · {pct}% · faltam ~{formatarTempo(r.restante_s)}
          </p>
        </>
      )}
      {r.status === "pronto" && (
        <>
          <div className="mt-1 grid grid-cols-2 gap-1">
            {r.imagens_url.map((u) => (
              <a key={u} href={URL_API + u} target="_blank" rel="noreferrer">
                <img src={URL_API + u} alt={u.split("/").pop()} className="rounded border" />
              </a>
            ))}
          </div>
          <p className="mt-0.5 text-xs text-stone-500">
            {r.em_cache ? "já estava pronto (nada mudou)" : `levou ${formatarTempo(r.duracao_s)}`} · versão{" "}
            {r.versao_projeto}
          </p>
        </>
      )}
      {r.status === "erro" && <p className="text-xs text-red-700">{r.erro?.split("\n")[0]}</p>}
    </li>
  );
}

/** Pedir imagens do cômodo (na variação de cor ativa) e acompanhar a fila. */
export function PainelImagens({ codigo, comodo, variacao }: { codigo: string; comodo: string; variacao: string }) {
  const lista = useRenders(codigo, comodo).data ?? [];
  const est = useEstimativas().data;
  const pedir = usePedirRender(codigo, comodo);
  const botao = "flex-1 rounded border border-stone-300 px-2 py-1 text-sm hover:bg-stone-100 disabled:opacity-40";
  return (
    <section className="border-b border-stone-200 p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
        Imagens 3D · variação {variacao}
      </h2>
      <div className="mb-2 flex gap-2">
        <button className={botao} disabled={pedir.isPending} onClick={() => pedir.mutate({ variacao, qualidade: "rascunho" })}>
          rascunho
          <span className="block text-xs text-stone-500">~{formatarTempo(est?.rascunho)}</span>
        </button>
        <button className={botao} disabled={pedir.isPending} onClick={() => pedir.mutate({ variacao, qualidade: "final" })}>
          final
          <span className="block text-xs text-stone-500">~{formatarTempo(est?.final)}</span>
        </button>
      </div>
      {pedir.error && <p className="mb-2 text-sm text-red-700">{pedir.error.message}</p>}
      <ul className="space-y-2">
        {lista.slice(0, 6).map((r) => (
          <Item key={r.id} r={r} />
        ))}
      </ul>
      {lista.length === 0 && <p className="text-sm text-stone-500">Nenhuma imagem ainda.</p>}
    </section>
  );
}
