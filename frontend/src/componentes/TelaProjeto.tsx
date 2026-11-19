import { useCallback, useState } from "react";
import { api, ou, type Cores, type MovelTela, type Problema } from "../api/cliente";
import { PainelCores } from "./PainelCores";
import { PainelImagens } from "./PainelImagens";
import { useEditar, useGeometria, useProblemas, useProjeto, useUnidade } from "../dados";
import { AdicionarMovel, FaltaMedir, PainelMovel, PainelProblemas } from "./Paineis";
import { Planta } from "./Planta";

export function TelaProjeto({
  codigo,
  comodoInicial,
  variacaoInicial,
  aoVoltar,
}: {
  codigo: string;
  comodoInicial?: string;
  variacaoInicial?: string;
  aoVoltar: () => void;
}) {
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
  const [comodo, setComodo] = useState<string | null>(comodoInicial ?? null);
  const [ativa, setAtiva] = useState<Record<string, string>>(
    comodoInicial && variacaoInicial ? { [comodoInicial]: variacaoInicial } : {},
  );
  const [rascunho, setRascunho] = useState<Cores | null>(null);
  const aoRascunho = useCallback((c: Cores | null) => setRascunho(c), []);

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
              comodoSelecionado={comodo}
              aoSelecionarComodo={setComodo}
              cores={rascunho}
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
          {comodo && geometria.data && (
            <PainelCores
              key={comodo}
              codigo={codigo}
              comodo={comodo}
              geometria={geometria.data}
              ativa={ativa[comodo] ?? "base"}
              aoAtivar={(nome) => setAtiva((a) => ({ ...a, [comodo]: nome }))}
              aoRascunho={aoRascunho}
            />
          )}
          {comodo && (
            <PainelImagens key={`img-${comodo}`} codigo={codigo} comodo={comodo} variacao={ativa[comodo] ?? "base"} />
          )}
          {!comodo && (
            <p className="border-b border-stone-200 p-3 text-sm text-stone-500">
              Clique num cômodo para pintar paredes, piso e móveis.
            </p>
          )}
          {geometria.data && <AdicionarMovel codigo={codigo} geometria={geometria.data} />}
          <PainelProblemas problemas={problemas} novos={novos} />
          <FaltaMedir codigo={codigo} unidade={unidade} />
        </aside>
      </div>
    </div>
  );
}
