import { useState } from "react";
import { api, ou, type MovelTela, type Problema } from "../api/cliente";
import { useEditar, useGeometria, useProblemas, useProjeto, useUnidade } from "../dados";
import { AdicionarMovel, FaltaMedir, PainelMovel, PainelProblemas } from "./Paineis";
import { Planta } from "./Planta";

export function TelaProjeto({ codigo, aoVoltar }: { codigo: string; aoVoltar: () => void }) {
  const projeto = useProjeto(codigo);
  const pavimentos = projeto.data?.projeto.pavimentos ?? [];
  const [pav, setPav] = useState<string | null>(null);
  const pavimento = pav ?? pavimentos[0]?.id ?? "terreo";
  const geometria = useGeometria(codigo, pavimento);
  const problemas = useProblemas(codigo).data ?? [];
  const unidade = useUnidade();
  const editar = useEditar(codigo);
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [novos, setNovos] = useState<Problema[]>([]);

  const mover = (m: MovelTela, centro: [number, number]) =>
    editar.mutate(
      (versao) =>
        ou(
          api.POST("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/mover", {
            params: { path: { codigo, comodo: m.comodo, id_: m.id }, query: { versao } },
            body: { centro },
          }),
        ),
      { onSuccess: (r) => setNovos(r.novos) },
    );

  const sel = geometria.data?.moveis.find((m) => m.id === selecionado);

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-4 border-b border-stone-200 bg-white px-4 py-2">
        <button className="text-sm text-sky-700 hover:underline" onClick={aoVoltar}>
          ← projetos
        </button>
        <h1 className="font-semibold">{codigo}</h1>
        {projeto.data && <span className="text-xs text-stone-500">versão {projeto.data.versao}</span>}
        {pavimentos.length > 1 && (
          <select className="rounded border text-sm" value={pavimento} onChange={(e) => setPav(e.target.value)}>
            {pavimentos.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nome ?? p.id}
              </option>
            ))}
          </select>
        )}
        {editar.isPending && <span className="text-xs text-stone-500">gravando…</span>}
        {editar.error && <span className="text-sm text-red-700">{editar.error.message}</span>}
      </header>
      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1">
          {geometria.data ? (
            <Planta
              geometria={geometria.data}
              unidade={unidade}
              problemas={problemas}
              selecionado={selecionado}
              aoSelecionar={setSelecionado}
              aoMover={mover}
            />
          ) : (
            <p className="p-4 text-stone-500">{geometria.error?.message ?? "carregando…"}</p>
          )}
        </main>
        <aside className="w-96 overflow-y-auto border-l border-stone-200 bg-stone-50">
          {sel && geometria.data && (
            <PainelMovel
              key={sel.id}
              codigo={codigo}
              comodo={sel.comodo}
              id={sel.id}
              geometria={geometria.data}
              unidade={unidade}
              aoRemovido={() => setSelecionado(null)}
            />
          )}
          {geometria.data && <AdicionarMovel codigo={codigo} geometria={geometria.data} />}
          <PainelProblemas problemas={problemas} novos={novos} />
          <FaltaMedir codigo={codigo} unidade={unidade} />
        </aside>
      </div>
    </div>
  );
}
