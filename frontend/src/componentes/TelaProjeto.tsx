import { useCallback, useRef, useState } from "react";
import { api, ou, type Cores, type Medida, type MovelTela, type Problema } from "../api/cliente";
import { proximoId, type Pt } from "../editor/geometria";
import { PainelPlanta } from "../editor/PainelPlanta";
import { BotoesDesfazer, PainelHistorico } from "./Desfazer";
import { PainelCores } from "./PainelCores";
import { PainelImagens } from "./PainelImagens";
import { Tela3D } from "./Tela3D";
import { useEditar, useGeometria, useProblemas, useProjeto, useUnidade } from "../dados";
import { AdicionarMovel, FaltaMedir, PainelMovel, PainelProblemas } from "./Paineis";
import { Planta, type Item } from "./Planta";

export function TelaProjeto({
  codigo,
  comodoInicial,
  variacaoInicial,
  modoInicial = "moveis",
  selInicial,
  aoVoltar,
}: {
  modoInicial?: "moveis" | "planta";
  /** ``tipo:id`` (ex.: ``parede:p2``) para abrir com o item selecionado no editor. */
  selInicial?: string;
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
  const [historico, setHistorico] = useState(false);
  const [ver3d, setVer3d] = useState(false);
  const [rascunho, setRascunho] = useState<Cores | null>(null);
  const aoRascunho = useCallback((c: Cores | null) => setRascunho(c), []);

  // editor de planta
  const [modo, setModo] = useState<"moveis" | "planta">(modoInicial);
  const [item, setItem] = useState<Item | null>(() => {
    const [tipo, id] = selInicial?.split(":") ?? [];
    return tipo && id ? ({ tipo, id } as Item) : null;
  });
  const [espessura, setEspessura] = useState<Medida | null>(null);
  const [escolhendo, setEscolhendo] = useState<string[] | null>(null);
  const idsNovos = useRef(new Set<string>()); // ids já pedidos nesta sequência de desenho
  const base = { codigo, pavimento };

  const aoItemEditor = (i: Item | null) => {
    if (escolhendo !== null) {
      if (i?.tipo === "parede")
        setEscolhendo((e) => (e!.includes(i.id) ? e!.filter((x) => x !== i.id) : [...e!, i.id]));
      return;
    }
    setItem(i);
  };
  const moverVertice = (de: Pt, para: Pt) =>
    editar.mutate((versao) =>
      ou(api.POST("/projetos/{codigo}/pavimentos/{pavimento}/vertices/mover", { params: { path: base, query: { versao } }, body: { de, para } })),
    );
  const novaParede = (a: Pt, b: Pt) => {
    if (!espessura || !geometria.data) return;
    const id = proximoId("p", [...geometria.data.paredes.map((p) => p.id), ...idsNovos.current]);
    idsNovos.current.add(id);
    editar.mutate((versao) =>
      ou(
        api.POST("/projetos/{codigo}/pavimentos/{pavimento}/paredes", {
          params: { path: base, query: { versao } },
          body: { id, inicio: a, fim: b, espessura, lado_a: "externo", lado_b: "externo" },
        }),
      ),
    );
  };

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
        <div className="ml-4 flex overflow-hidden rounded border border-stone-300 text-sm">
          {(["moveis", "planta"] as const).map((m) => (
            <button
              key={m}
              className={`px-3 py-0.5 ${modo === m ? "bg-stone-800 text-white" : "hover:bg-stone-100"}`}
              onClick={() => {
                setModo(m);
                setItem(null);
                setEspessura(null);
                setEscolhendo(null);
                setSelecionado(null);
              }}
            >
              {m === "moveis" ? "Móveis e cores" : "Editar planta"}
            </button>
          ))}
        </div>
        <div className="flex overflow-hidden rounded border border-stone-300 text-sm">
          {([false, true] as const).map((v) => (
            <button
              key={String(v)}
              className={`px-3 py-0.5 ${ver3d === v ? "bg-stone-800 text-white" : "hover:bg-stone-100"}`}
              onClick={() => setVer3d(v)}
            >
              {v ? "3D" : "Planta"}
            </button>
          ))}
        </div>
        <BotoesDesfazer codigo={codigo} aoProblemas={setNovos} aoHistorico={() => setHistorico((h) => !h)} />
        {editar.isPending && <span className="text-xs text-stone-500">gravando…</span>}
        {editar.error && <span className="text-sm text-red-700">{editar.error.message}</span>}
      </header>
      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1">
          {ver3d ? (
            <Tela3D
              codigo={codigo}
              comodo={comodo}
              comodos={pavimentos.find((p) => p.id === pavimento)?.comodos ?? []}
              versaoProjeto={projeto.data?.versao}
              aoComodo={setComodo}
            />
          ) : geometria.data ? (
            <Planta
              geometria={geometria.data}
              unidade={unidade}
              problemas={problemas}
              selecionado={selecionado}
              aoSelecionar={setSelecionado}
              aoMover={mover}
              comodoSelecionado={comodo}
              aoSelecionarComodo={setComodo}
              cores={modo === "moveis" ? rascunho : null}
              editor={
                modo === "planta"
                  ? {
                      item,
                      destacadas: escolhendo ?? [],
                      desenhando: espessura !== null,
                      aoItem: aoItemEditor,
                      aoMoverVertice: moverVertice,
                      aoNovaParede: novaParede,
                    }
                  : undefined
              }
            />
          ) : (
            <p className="p-4 text-stone-500">{geometria.error?.message ?? "carregando…"}</p>
          )}
        </main>
        <aside className="w-96 overflow-y-auto border-l border-stone-200 bg-stone-50">
          {historico && <PainelHistorico codigo={codigo} aoFechar={() => setHistorico(false)} />}
          {modo === "planta" && geometria.data && (
            <PainelPlanta
              codigo={codigo}
              pavimento={pavimento}
              geometria={geometria.data}
              unidade={unidade}
              item={item}
              aoItem={setItem}
              desenhando={espessura !== null}
              aoDesenhar={(sim, m) => {
                idsNovos.current.clear();
                setEspessura(sim ? (m ?? null) : null);
              }}
              escolhendo={escolhendo}
              aoEscolher={setEscolhendo}
            />
          )}
          {modo === "moveis" && <>
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
          </>}
          <PainelProblemas problemas={problemas} novos={novos} />
          <FaltaMedir codigo={codigo} unidade={unidade} />
        </aside>
      </div>
    </div>
  );
}
