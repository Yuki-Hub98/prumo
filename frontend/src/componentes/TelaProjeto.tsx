import { BotaoTema } from "./BotaoTema";
import { Box, PencilRuler } from "lucide-react";
import { Marca } from "./Logo";
import { alternar } from "../estilo";
import { useCallback, useRef, useState } from "react";
import { api, ou, type Cores, type Medida, type MovelTela, type Problema } from "../api/cliente";
import { proximoId, type Pt } from "../editor/geometria";
import { PainelPlanta } from "../editor/PainelPlanta";
import { BarraRascunho, BotoesDesfazer, PainelHistorico, useRascunho } from "./Desfazer";
import { PainelCores } from "./PainelCores";
import { PainelEstruturas } from "./PainelEstruturas";
import { PainelImagens } from "./PainelImagens";
import { NovoAndar } from "./NovoAndar";
import { PainelTinta } from "./PainelTinta";
import { Tela3D } from "./Tela3D";
import { Abas, ColunaLateral } from "./ColunaLateral";
import { useEditar, useGeometria, useProblemas, useProjeto, useUnidade, useVariacoes } from "../dados";
import { AdicionarMovel, FaixaPreliminar, FaltaMedir, PainelMovel, PainelProblemas, piorGravidade } from "./Paineis";
import { Planta, type Item, type LadoMovel } from "./Planta";

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
  // o andar escolhido pode deixar de existir (removido, desfeito): volta para o primeiro
  const pavimento = (pav && pavimentos.some((p) => p.id === pav) ? pav : pavimentos[0]?.id) ?? "terreo";
  const geometria = useGeometria(codigo, pavimento);
  // andar de baixo mais próximo que tenha paredes, de referência ao desenhar o de cima
  const abaixo =
    pavimentos
      .slice(0, Math.max(0, pavimentos.findIndex((p) => p.id === pavimento)))
      .reverse()
      .find((p) => (p.paredes?.length ?? 0) > 0)?.id ?? null;
  const fundo = useGeometria(codigo, abaixo ?? "", !!abaixo).data;
  const problemas = useProblemas(codigo).data ?? [];
  const unidade = useUnidade();
  const editar = useEditar(codigo);
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [aba, setAba] = useState<"movel" | "cores" | "imagens" | "problemas" | "estruturas">("cores");
  const [estruturaSel, setEstruturaSel] = useState<string | null>(null);
  // clicar num móvel abre a aba Móvel e seleciona o cômodo dele (a aba Cores já pinta o móvel)
  const selecionar = (id: string | null) => {
    setSelecionado(id);
    if (!id) return;
    if (aba !== "cores" && aba !== "estruturas") setAba("movel"); // pintando: fica em Cores, com a linha do móvel marcada
    const m = geometria.data?.moveis.find((x) => x.id === id);
    if (m) setComodo(m.comodo);
  };
  const [novos, setNovos] = useState<Problema[]>([]);
  const acoes = useRascunho(codigo, setNovos);
  // "Ver na planta" de um problema (pisca na planta) e "Ver o que falta medir" da faixa
  const [destaque, setDestaque] = useState<{ p: Problema; vez: number } | null>(null);
  const [pedidoFalta, setPedidoFalta] = useState(0);
  const [comodo, setComodo] = useState<string | null>(comodoInicial ?? null);
  const [ativa, setAtiva] = useState<Record<string, string>>(
    comodoInicial && variacaoInicial ? { [comodoInicial]: variacaoInicial } : {},
  );
  const [historico, setHistorico] = useState(false);
  const [ver3d, setVer3d] = useState(false);
  const [rascunho, setRascunho] = useState<Cores | null>(null);
  const aoRascunho = useCallback((c: Cores | null) => setRascunho(c), []);
  const variacoesComodo = useVariacoes(codigo, comodo).data;

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

  const girar = (m: MovelTela) =>
    editar.mutate(
      (versao) =>
        ou(
          api.POST("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/mover", {
            params: { path: { codigo, comodo: m.comodo, id_: m.id }, query: { versao } },
            body: { rotacao: (((m.rotacao ?? 0) + 90) % 360) as 0 | 90 | 180 | 270 },
          }),
        ),
      { onSuccess: (r) => setNovos(r.novos) },
    );

  const redimensionar = (m: MovelTela, lado: LadoMovel, tamanho: number) =>
    editar.mutate(
      (versao) =>
        ou(
          api.POST("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/redimensionar", {
            params: { path: { codigo, comodo: m.comodo, id_: m.id }, query: { versao } },
            body: { lado, tamanho },
          }),
        ),
      { onSuccess: (r) => setNovos(r.novos) },
    );

  const sel = geometria.data?.moveis.find((m) => m.id === selecionado);
  // com o painel Cores aberto, o rascunho (ao vivo); fechado, as cores salvas da variação ativa
  const variacaoAtiva = comodo ? (ativa[comodo] ?? "base") : "base";
  const coresVistas =
    modo !== "moveis" || variacaoAtiva === "base"
      ? null
      : aba === "cores"
        ? rascunho
        : (variacoesComodo?.[variacaoAtiva]?.cores ?? null);

  function verNaPlanta(p: Problema) {
    if (p.pavimento && p.pavimento !== pavimento) setPav(p.pavimento);
    setVer3d(false);
    setDestaque((d) => ({ p, vez: (d?.vez ?? 0) + 1 }));
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-4 border-b border-linha bg-superficie px-4 py-2">
        <button
          className="flex items-center gap-1.5 rounded-md px-1 text-sm text-tinta-suave hover:text-tinta"
          onClick={aoVoltar}
          title="Voltar para a lista de projetos"
        >
          <Marca altura={22} />
          ← Projetos
        </button>
        <h1 className="font-cond text-lg font-semibold">{codigo}</h1>
        {projeto.data && <span className="text-xs text-tinta-suave">Versão {projeto.data.versao}</span>}
        <div className="flex items-center gap-1">
          <select
            className="rounded-md border text-sm"
            value={pavimento}
            onChange={(e) => {
              setPav(e.target.value);
              setComodo(null);
              setSelecionado(null);
            }}
            aria-label="andar"
          >
            {pavimentos.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nome ?? p.id}
              </option>
            ))}
          </select>
          <NovoAndar
            codigo={codigo}
            pavimentos={pavimentos}
            atual={pavimento}
            unidade={unidade}
            aoCriado={(id) => {
              setPav(id);
              setComodo(null);
              setSelecionado(null);
              setVer3d(false);
              setModo("planta");
            }}
          />
        </div>
        <div className="ml-4 flex overflow-hidden rounded-md border border-linha-forte text-sm">
          {(["moveis", "planta"] as const).map((m) => (
            <button
              key={m}
              className={`px-3 py-0.5 ${alternar(modo === m)}`}
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
        <div className="flex overflow-hidden rounded-md border border-linha-forte text-sm">
          {([false, true] as const).map((v) => (
            <button
              key={String(v)}
              className={`px-3 py-0.5 ${alternar(ver3d === v)}`}
              onClick={() => setVer3d(v)}
            >
              <span className="inline-flex items-center gap-1">
                {v ? <Box size={14} /> : <PencilRuler size={14} />}
                {v ? "3D" : "Planta"}
              </span>
            </button>
          ))}
        </div>
        <BotoesDesfazer acoes={acoes} aoHistorico={() => setHistorico((h) => !h)} />
        {editar.isPending && <span className="text-xs text-tinta-suave">Gravando…</span>}
        {editar.error && <span className="text-sm text-erro">{editar.error.message}</span>}
        <span className="ml-auto">
          <BotaoTema />
        </span>
      </header>
      <FaixaPreliminar
        codigo={codigo}
        aoVer={() => {
          if (modo === "moveis") setAba("problemas");
          setPedidoFalta((n) => n + 1);
        }}
      />
      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1">
          {ver3d ? (
            <Tela3D
              codigo={codigo}
              pavimento={pavimento}
              comodo={comodo}
              comodos={pavimentos.find((p) => p.id === pavimento)?.comodos ?? []}
              aoComodo={setComodo}
              cores={coresVistas}
              geometria={geometria.data}
              selecionado={selecionado}
              aoSelecionarMovel={selecionar}
              aoMoverMovel={(id, [dx, dy]) => {
                const m = geometria.data?.moveis.find((x) => x.id === id);
                if (m) mover(m, [m.centro[0] + dx, m.centro[1] + dy]);
              }}
              aoGirarMovel={(id) => {
                const m = geometria.data?.moveis.find((x) => x.id === id);
                if (m) girar(m);
              }}
            />
          ) : geometria.data ? (
            <Planta
              geometria={geometria.data}
              unidade={unidade}
              problemas={problemas}
              selecionado={selecionado}
              aoSelecionar={selecionar}
              aoMover={mover}
              aoRedimensionar={redimensionar}
              comodoSelecionado={comodo}
              aoSelecionarComodo={setComodo}
              cores={coresVistas}
              fundo={abaixo ? (fundo ?? null) : null}
              destaque={destaque}
              estrutura={
                modo === "moveis" && aba === "estruturas"
                  ? {
                      sel: estruturaSel,
                      aoSelecionar: setEstruturaSel,
                      aoMover: (id, campo, ponto) =>
                        editar.mutate((versao) =>
                          ou(
                            api.PATCH("/projetos/{codigo}/pavimentos/{pavimento}/estrutura/{id_}", {
                              params: { path: { ...base, id_: id }, query: { versao } },
                              body: { [campo]: ponto },
                            }),
                          ),
                        ),
                    }
                  : undefined
              }
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
            <p className="p-4 text-tinta-suave">{geometria.error?.message ?? "Carregando…"}</p>
          )}
        </main>
        <ColunaLateral titulo={modo === "planta" ? "Editar planta" : "Painel de edição"}>
          {historico && (
            <div className="max-h-[50%] shrink-0 overflow-y-auto border-b border-linha">
              <PainelHistorico codigo={codigo} aoFechar={() => setHistorico(false)} />
            </div>
          )}
          {modo === "planta" ? (
            <div className="min-h-0 flex-1 overflow-y-auto">
              {geometria.data && (
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
              <PainelProblemas problemas={problemas} novos={novos} aoVer={verNaPlanta} />
              <FaltaMedir codigo={codigo} unidade={unidade} pedido={pedidoFalta} />
            </div>
          ) : (
            <>
              <Abas
                abas={[
                  { id: "movel", titulo: "Móvel" },
                  { id: "cores", titulo: "Cores" },
                  { id: "imagens", titulo: "Imagens" },
                  { id: "estruturas", titulo: "Estruturas" },
                  { id: "problemas", titulo: "Problemas", marca: problemas.length, tom: piorGravidade(problemas) },
                ]}
                ativa={aba}
                aoTrocar={setAba}
              />
              <div className="min-h-0 flex-1 overflow-y-auto" role="tabpanel">
                {aba === "movel" && (
                  <>
                    {sel && geometria.data ? (
                      <PainelMovel
                        key={sel.id}
                        codigo={codigo}
                        comodo={sel.comodo}
                        id={sel.id}
                        geometria={geometria.data}
                        unidade={unidade}
                        aoRemovido={() => setSelecionado(null)}
                      />
                    ) : (
                      <p className="border-b border-linha p-3 text-sm text-tinta-suave">
                        Clique num móvel na planta para editar medidas, girar ou encostar na parede.
                      </p>
                    )}
                    {geometria.data && (
                      <AdicionarMovel codigo={codigo} geometria={geometria.data} unidade={unidade} aoCriado={selecionar} />
                    )}
                  </>
                )}
                {aba === "cores" &&
                  (comodo && geometria.data ? (
                    <PainelCores
                      key={comodo}
                      codigo={codigo}
                      comodo={comodo}
                      geometria={geometria.data}
                      ativa={ativa[comodo] ?? "base"}
                      aoAtivar={(nome) => setAtiva((a) => ({ ...a, [comodo]: nome }))}
                      aoRascunho={aoRascunho}
                      destaque={sel?.comodo === comodo ? sel.id : null}
                      aoSelecionarMovel={selecionar}
                    />
                  ) : (
                    <p className="p-3 text-sm text-tinta-suave">Clique num cômodo para pintar paredes, piso e móveis.</p>
                  ))}
                {aba === "cores" && (
                  <PainelTinta
                    codigo={codigo}
                    pavimento={pavimento}
                    escolhas={Object.fromEntries(
                      (pavimentos.find((p) => p.id === pavimento)?.comodos ?? []).map((c) => [c.id, ativa[c.id] ?? "base"]),
                    )}
                  />
                )}
                {aba === "imagens" &&
                  (comodo ? (
                    <PainelImagens key={`img-${comodo}`} codigo={codigo} comodo={comodo} variacao={ativa[comodo] ?? "base"} />
                  ) : (
                    <p className="p-3 text-sm text-tinta-suave">Clique num cômodo para pedir as imagens 3D dele.</p>
                  ))}
                {aba === "estruturas" && geometria.data && (
                  <PainelEstruturas
                    codigo={codigo}
                    pavimento={pavimento}
                    geometria={geometria.data}
                    comodo={comodo}
                    unidade={unidade}
                    sel={estruturaSel}
                    aoSelecionar={setEstruturaSel}
                  />
                )}
                {aba === "problemas" && (
                  <>
                    <PainelProblemas problemas={problemas} novos={novos} aoVer={verNaPlanta} />
                    <FaltaMedir codigo={codigo} unidade={unidade} pedido={pedidoFalta} />
                  </>
                )}
              </div>
            </>
          )}
        </ColunaLateral>
      </div>
      <BarraRascunho acoes={acoes} />
    </div>
  );
}
