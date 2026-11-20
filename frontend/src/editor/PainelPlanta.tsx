import { useState } from "react";
import { api, ou, type Medida, type PavimentoTela } from "../api/cliente";
import { CampoMedida } from "../componentes/CampoMedida";
import { useEditar, useProjeto } from "../dados";
import { formatar, ORIGENS, paraMm, type Origem, type Unidade } from "../unidades";
import type { Item } from "../componentes/Planta";
import { paraId, proximoId } from "./geometria";

const botao = "rounded border border-stone-300 px-2 py-0.5 text-sm hover:bg-stone-100 disabled:opacity-40";
const perigo = "rounded border border-red-300 px-2 py-0.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-40";

const TIPOS_COMODO = [
  "quarto", "sala", "cozinha", "banheiro", "lavabo", "area_servico", "escritorio", "corredor",
  "varanda", "garagem", "outro",
] as const; // prettier-ignore
const TIPOS_INSTALACAO = {
  tomada: "Tomada",
  interruptor: "Interruptor",
  ponto_luz: "Ponto de luz",
  agua_fria: "Água fria",
  agua_quente: "Água quente",
  esgoto: "Esgoto",
  ralo: "Ralo",
  gas: "Gás",
} as const;
type TipoInstalacao = keyof typeof TIPOS_INSTALACAO;

function Caixa({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-stone-200 p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">{titulo}</h2>
      {children}
    </section>
  );
}

/** Medida nova (valor + origem obrigatória). Devolve ``null`` enquanto incompleta. */
function NovaMedida({
  rotulo,
  unidade,
  aoMudar,
  inicial = "",
}: {
  rotulo: string;
  unidade: Unidade;
  aoMudar: (m: Medida | null) => void;
  inicial?: string;
}) {
  const [texto, setTexto] = useState(inicial);
  const [origem, setOrigem] = useState<Origem | null>(null);
  const avisar = (t: string, o: Origem | null) => {
    const mm = paraMm(t, unidade);
    aoMudar(mm !== null && o !== null ? { valor: mm, origem: o } : null);
  };
  return (
    <div className="py-1 text-sm">
      <label className="flex items-center gap-2">
        <span className="w-28 text-stone-500">{rotulo}</span>
        <input
          className="w-20 rounded border px-1"
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value);
            avisar(e.target.value, origem);
          }}
        />
        <span className="text-stone-500">{unidade}</span>
      </label>
      <div className="ml-28 flex gap-2 pl-2 text-xs">
        {ORIGENS.map((o) => (
          <label key={o.valor} title={o.dica} className="flex items-center gap-0.5">
            <input
              type="radio"
              checked={origem === o.valor}
              onChange={() => {
                setOrigem(o.valor);
                avisar(texto, o.valor);
              }}
            />
            {o.rotulo}
          </label>
        ))}
      </div>
    </div>
  );
}

type Props = {
  codigo: string;
  pavimento: string;
  geometria: PavimentoTela;
  unidade: Unidade;
  item: Item | null;
  aoItem: (i: Item | null) => void;
  desenhando: boolean;
  aoDesenhar: (sim: boolean, espessura?: Medida) => void;
  escolhendo: string[] | null;
  aoEscolher: (paredes: string[] | null) => void;
};

/** Painel lateral do editor de planta: muda conforme o que está selecionado. */
export function PainelPlanta(props: Props) {
  const { codigo, pavimento, item } = props;
  const projeto = useProjeto(codigo).data;
  const pav = projeto?.projeto.pavimentos.find((p) => p.id === pavimento);
  const editar = useEditar(codigo);
  if (!pav) return null;
  const base = { codigo, pavimento };
  const fazer = (f: (versao: number) => Promise<unknown>, depois?: () => void) =>
    editar.mutate((v) => f(v) as never, { onSuccess: depois });
  const unicoAndar = (projeto?.projeto.pavimentos.length ?? 1) <= 1;
  const ctx = { ...props, pav, base, fazer, ocupado: editar.isPending, unicoAndar };

  return (
    <>
      {editar.error && <p className="border-b border-red-200 bg-red-50 p-2 text-sm text-red-800">{editar.error.message}</p>}
      {!item && <Ferramentas {...ctx} />}
      {item?.tipo === "parede" && <PainelParede key={item.id} {...ctx} id={item.id} />}
      {item?.tipo === "abertura" && <PainelAbertura key={item.id} {...ctx} id={item.id} />}
      {item?.tipo === "instalacao" && <PainelInstalacao key={item.id} {...ctx} id={item.id} />}
      {item?.tipo === "comodo" && <PainelComodo key={item.id} {...ctx} id={item.id} />}
    </>
  );
}

type Pav = NonNullable<ReturnType<typeof useProjeto>["data"]>["projeto"]["pavimentos"][number];
type Ctx = Props & {
  pav: Pav;
  base: { codigo: string; pavimento: string };
  fazer: (f: (versao: number) => Promise<unknown>, depois?: () => void) => void;
  ocupado: boolean;
  /** O projeto só tem este andar (não dá para remover). */
  unicoAndar: boolean;
};

// ------------------------------------------------------------------ sem seleção

function Ferramentas({ pav, unidade, base, fazer, ocupado, desenhando, aoDesenhar, escolhendo, aoEscolher, unicoAndar }: Ctx) {
  const [espessura, setEspessura] = useState<Medida | null>(null);
  const [nome, setNome] = useState("");
  const [tipo, setTipo] = useState<(typeof TIPOS_COMODO)[number]>("quarto");

  return (
    <>
      <Caixa titulo="Desenhar paredes">
        {desenhando ? (
          <>
            <p className="mb-2 text-sm text-stone-600">
              Clique na planta canto a canto. Gruda nos cantos existentes e alinha reto. Botão direito
              termina a sequência.
            </p>
            <button className={botao} onClick={() => aoDesenhar(false)}>
              parar de desenhar
            </button>
          </>
        ) : (
          <>
            <NovaMedida rotulo="espessura" unidade={unidade} inicial={unidade === "cm" ? "15" : ""} aoMudar={setEspessura} />
            <button className={`${botao} mt-1`} disabled={!espessura} onClick={() => aoDesenhar(true, espessura!)}>
              começar a desenhar
            </button>
          </>
        )}
      </Caixa>

      <Caixa titulo="Novo cômodo">
        {escolhendo === null ? (
          <button className={botao} onClick={() => aoEscolher([])}>
            escolher as paredes…
          </button>
        ) : (
          <div className="flex flex-col gap-1 text-sm">
            <p className="text-stone-600">
              Clique nas paredes que fecham o cômodo, em volta dele ({escolhendo.length} escolhidas
              {escolhendo.length ? `: ${escolhendo.join(", ")}` : ""}).
            </p>
            <input className="rounded border px-1" placeholder="nome (ex.: Cozinha)" value={nome} onChange={(e) => setNome(e.target.value)} />
            <select className="rounded border" value={tipo} onChange={(e) => setTipo(e.target.value as typeof tipo)}>
              {TIPOS_COMODO.map((t) => (
                <option key={t} value={t}>
                  {t.replace("_", " ")}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <button
                className={botao}
                disabled={!nome.trim() || escolhendo.length < 3 || ocupado}
                onClick={() =>
                  fazer(
                    (versao) =>
                      ou(
                        api.POST("/projetos/{codigo}/pavimentos/{pavimento}/comodos", {
                          params: { path: base, query: { versao } },
                          body: { comodo: { id: paraId(nome) || proximoId("comodo-", []), nome: nome.trim(), tipo, paredes: escolhendo } },
                        }),
                      ),
                    () => {
                      aoEscolher(null);
                      setNome("");
                    },
                  )
                }
              >
                criar cômodo
              </button>
              <button className={botao} onClick={() => aoEscolher(null)}>
                cancelar
              </button>
            </div>
          </div>
        )}
      </Caixa>

      <Caixa titulo={`Pavimento ${pav.nome ?? pav.id}`}>
        {(["pe_direito", "rodape"] as const).map((campo) => (
          <CampoMedida
            key={campo}
            rotulo={campo === "pe_direito" ? "pé-direito" : "rodapé"}
            medida={pav[campo]}
            unidade={unidade}
            ocupado={ocupado}
            aoSalvar={(m) =>
              fazer((versao) =>
                ou(api.PATCH("/projetos/{codigo}/pavimentos/{pavimento}", { params: { path: base, query: { versao } }, body: { [campo]: m } })),
              )
            }
          />
        ))}
        <p className="mt-2 text-xs text-stone-500">
          Clique numa parede, porta, janela, tomada ou cômodo para editar. Arraste os cantos (círculos azuis)
          para mover paredes.
        </p>
        <RemoverAndar pav={pav} sozinho={unicoAndar} base={base} fazer={fazer} ocupado={ocupado} />
      </Caixa>
    </>
  );
}

/** Remover o andar aberto, com confirmação na tela; com paredes ou cômodos, vai tudo junto
 * (inclusive os móveis). O único andar do projeto não sai. Entra no rascunho: dá para desfazer. */
function RemoverAndar({
  pav,
  sozinho,
  base,
  fazer,
  ocupado,
}: Pick<Ctx, "pav" | "base" | "fazer" | "ocupado"> & { sozinho: boolean }) {
  const [confirmar, setConfirmar] = useState(false);
  if (sozinho) return null;
  const cheio = (pav.paredes?.length ?? 0) + (pav.comodos?.length ?? 0) > 0;
  return confirmar ? (
    <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-900">
      Remover o andar "{pav.nome ?? pav.id}"
      {cheio && `, com ${pav.comodos?.length ?? 0} cômodo(s) e ${pav.paredes?.length ?? 0} parede(s) (e os móveis)`}?
      <div className="mt-1 flex gap-2">
        <button
          className="rounded bg-red-700 px-2 py-0.5 text-white disabled:opacity-40"
          disabled={ocupado}
          onClick={() =>
            fazer((versao) =>
              ou(
                api.DELETE("/projetos/{codigo}/pavimentos/{pavimento}", {
                  params: { path: base, query: { versao, cascata: cheio } },
                }),
              ),
            )
          }
        >
          remover
        </button>
        <button className="rounded border border-red-200 bg-white px-2 py-0.5" onClick={() => setConfirmar(false)}>
          cancelar
        </button>
      </div>
    </div>
  ) : (
    <button className="mt-2 text-xs text-red-700 hover:underline" onClick={() => setConfirmar(true)}>
      remover este andar
    </button>
  );
}

// ------------------------------------------------------------------ parede

function PainelParede({ id, pav, unidade, base, fazer, ocupado, aoItem }: Ctx & { id: string }) {
  const p = pav.paredes?.find((x) => x.id === id);
  const [corte, setCorte] = useState("");
  const [cascata, setCascata] = useState(false);
  const [novo, setNovo] = useState<"porta" | "janela" | "instalacao" | null>(null);
  if (!p) return null;
  const comp = Math.round(Math.hypot(p.fim[0] - p.inicio[0], p.fim[1] - p.inicio[1]));
  const caminho = { ...base, id_: id };
  const aberturas = (pav.aberturas ?? []).filter((a) => a.parede === id);

  return (
    <Caixa titulo={`Parede ${id}`}>
      <p className="mb-1 text-sm text-stone-600">
        comprimento {formatar(comp, unidade)} · lados: {p.lado_a} | {p.lado_b}
      </p>
      <CampoMedida
        rotulo="espessura"
        medida={p.espessura}
        unidade={unidade}
        ocupado={ocupado}
        aoSalvar={(m) =>
          fazer((versao) =>
            ou(api.PATCH("/projetos/{codigo}/pavimentos/{pavimento}/paredes/{id_}", { params: { path: caminho, query: { versao } }, body: { campos: { espessura: m } } })),
          )
        }
      />
      {aberturas.length > 0 && (
        <p className="text-xs text-stone-500">
          nela:{" "}
          {aberturas.map((a) => (
            <button key={a.id} className="mr-1 text-sky-700 hover:underline" onClick={() => aoItem({ tipo: "abertura", id: a.id })}>
              {a.id}
            </button>
          ))}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-1">
        <button className={botao} onClick={() => setNovo("porta")}>+ porta</button>
        <button className={botao} onClick={() => setNovo("janela")}>+ janela</button>
        <button className={botao} onClick={() => setNovo("instalacao")}>+ tomada/ponto</button>
      </div>
      {novo === "instalacao" && <NovaInstalacao {...{ id, pav, unidade, base, fazer, ocupado, aoItem }} aoFim={() => setNovo(null)} />}
      {(novo === "porta" || novo === "janela") && (
        <NovaAbertura tipo={novo} parede={p} {...{ pav, unidade, base, fazer, ocupado, aoItem }} aoFim={() => setNovo(null)} />
      )}
      <form
        className="mt-3 flex items-center gap-1 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          const mm = paraMm(corte, unidade);
          if (mm === null) return;
          fazer((versao) =>
            ou(
              api.POST("/projetos/{codigo}/pavimentos/{pavimento}/paredes/{id_}/dividir", {
                params: { path: caminho, query: { versao } },
                body: { distancia: mm, novo_id: proximoId("p", (pav.paredes ?? []).map((w) => w.id)) },
              }),
            ),
          );
        }}
      >
        <span className="text-stone-500">dividir a</span>
        <input className="w-16 rounded border px-1" value={corte} onChange={(e) => setCorte(e.target.value)} />
        <span className="text-stone-500">{unidade} do início</span>
        <button className={botao} disabled={paraMm(corte, unidade) === null || ocupado}>ok</button>
      </form>
      <div className="mt-3 flex items-center gap-2 text-sm">
        <button
          className={perigo}
          disabled={ocupado}
          onClick={() =>
            fazer(
              (versao) =>
                ou(api.DELETE("/projetos/{codigo}/pavimentos/{pavimento}/paredes/{id_}", { params: { path: caminho, query: { versao, cascata } } })),
              () => aoItem(null),
            )
          }
        >
          remover parede
        </button>
        <label className="flex items-center gap-1 text-xs text-stone-600">
          <input type="checkbox" checked={cascata} onChange={(e) => setCascata(e.target.checked)} />
          levar junto portas/janelas e tirar dos cômodos
        </label>
      </div>
    </Caixa>
  );
}

function NovaAbertura({
  tipo,
  parede,
  pav,
  unidade,
  base,
  fazer,
  ocupado,
  aoItem,
  aoFim,
}: Pick<Ctx, "pav" | "unidade" | "base" | "fazer" | "ocupado" | "aoItem"> & {
  tipo: "porta" | "janela";
  parede: Pav["paredes"] extends (infer P)[] | undefined ? P : never;
  aoFim: () => void;
}) {
  const [m, setM] = useState<Record<string, Medida | null>>({});
  const lados = [parede.lado_a, parede.lado_b];
  const [abrePara, setAbrePara] = useState(lados.find((l) => l !== "externo") ?? lados[0]);
  const campos = tipo === "porta" ? ["distancia_inicio", "largura", "altura"] : ["distancia_inicio", "largura", "altura", "peitoril"];
  const rotulos: Record<string, string> = { distancia_inicio: "do início", largura: "largura", altura: "altura", peitoril: "peitoril" };
  const iniciais: Record<string, Record<Unidade, string>> = {
    largura: { cm: tipo === "porta" ? "80" : "120", m: tipo === "porta" ? "0,8" : "1,2", mm: tipo === "porta" ? "800" : "1200" },
    altura: { cm: tipo === "porta" ? "210" : "100", m: tipo === "porta" ? "2,1" : "1", mm: tipo === "porta" ? "2100" : "1000" },
    peitoril: { cm: "110", m: "1,1", mm: "1100" },
  };
  const pronto = campos.every((c) => m[c]);
  const id = proximoId(`${tipo}-`, (pav.aberturas ?? []).map((a) => a.id));
  return (
    <div className="mt-2 rounded border border-stone-200 bg-white p-2">
      <p className="mb-1 text-sm font-medium">Nova {tipo} ({id})</p>
      {campos.map((c) => (
        <NovaMedida key={c} rotulo={rotulos[c]} unidade={unidade} inicial={iniciais[c]?.[unidade] ?? ""} aoMudar={(v) => setM((x) => ({ ...x, [c]: v }))} />
      ))}
      {tipo === "porta" && (
        <label className="flex items-center gap-2 py-1 text-sm">
          <span className="w-28 text-stone-500">abre para</span>
          <select className="rounded border" value={abrePara} onChange={(e) => setAbrePara(e.target.value)}>
            {lados.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </label>
      )}
      <div className="mt-1 flex gap-2">
        <button
          className={botao}
          disabled={!pronto || ocupado}
          onClick={() => {
            const corpo =
              tipo === "porta"
                ? { id, tipo, parede: parede.id, de: lados[0], para: lados[1], folha: "giro" as const, abre_para: abrePara, dobradica: "inicio" as const,
                    distancia_inicio: m.distancia_inicio!, largura: m.largura!, altura: m.altura! } // prettier-ignore
                : { id, tipo, parede: parede.id, distancia_inicio: m.distancia_inicio!, largura: m.largura!, altura: m.altura!, peitoril: m.peitoril! };
            fazer(
              (versao) => ou(api.POST("/projetos/{codigo}/pavimentos/{pavimento}/aberturas", { params: { path: base, query: { versao } }, body: corpo })),
              () => {
                aoFim();
                aoItem({ tipo: "abertura", id });
              },
            );
          }}
        >
          criar
        </button>
        <button className={botao} onClick={aoFim}>cancelar</button>
      </div>
    </div>
  );
}

function NovaInstalacao({
  id: parede,
  pav,
  unidade,
  base,
  fazer,
  ocupado,
  aoItem,
  aoFim,
}: Pick<Ctx, "pav" | "unidade" | "base" | "fazer" | "ocupado" | "aoItem"> & { id: string; aoFim: () => void }) {
  const [tipo, setTipo] = useState<TipoInstalacao>("tomada");
  const [dist, setDist] = useState<Medida | null>(null);
  const [altura, setAltura] = useState<Medida | null>(null);
  const w = pav.paredes?.find((x) => x.id === parede);
  const lados = w ? [w.lado_a, w.lado_b].filter((l) => l !== "externo") : [];
  const [comodo, setComodo] = useState(lados[0] ?? "");
  const id = proximoId(`${tipo.replace("_", "-")}-`, (pav.instalacoes ?? []).map((i) => i.id));
  return (
    <div className="mt-2 rounded border border-stone-200 bg-white p-2">
      <select className="mb-1 rounded border text-sm" value={tipo} onChange={(e) => setTipo(e.target.value as TipoInstalacao)}>
        {Object.entries(TIPOS_INSTALACAO).map(([k, v]) => (
          <option key={k} value={k}>{v}</option>
        ))}
      </select>
      <NovaMedida rotulo="do início" unidade={unidade} aoMudar={setDist} />
      <NovaMedida rotulo="altura do piso" unidade={unidade} inicial={unidade === "cm" ? (tipo === "interruptor" ? "110" : "30") : ""} aoMudar={setAltura} />
      {lados.length === 2 && (
        <label className="flex items-center gap-2 py-1 text-sm">
          <span className="w-28 text-stone-500">lado (cômodo)</span>
          <select className="rounded border" value={comodo} onChange={(e) => setComodo(e.target.value)}>
            {lados.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </label>
      )}
      <div className="mt-1 flex gap-2">
        <button
          className={botao}
          disabled={!dist || !altura || ocupado}
          onClick={() =>
            fazer(
              (versao) =>
                ou(
                  api.POST("/projetos/{codigo}/pavimentos/{pavimento}/instalacoes", {
                    params: { path: base, query: { versao } },
                    body: {
                      instalacao: { id, forma: "ponto", tipo, parede, altura: altura!, ...(lados.length === 2 ? { comodo } : {}) },
                      distancia: dist!.valor,
                    },
                  }),
                ),
              () => {
                aoFim();
                aoItem({ tipo: "instalacao", id });
              },
            )
          }
        >
          criar
        </button>
        <button className={botao} onClick={aoFim}>cancelar</button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ abertura

function PainelAbertura({ id, pav, unidade, base, fazer, ocupado, aoItem }: Ctx & { id: string }) {
  const a = pav.aberturas?.find((x) => x.id === id);
  if (!a) return null;
  const caminho = { ...base, id_: id };
  const alterar = (campos: Record<string, unknown>) =>
    fazer((versao) =>
      ou(api.PATCH("/projetos/{codigo}/pavimentos/{pavimento}/aberturas/{id_}", { params: { path: caminho, query: { versao } }, body: campos })),
    );
  const medidas = a.tipo === "janela" ? (["distancia_inicio", "largura", "altura", "peitoril"] as const) : (["distancia_inicio", "largura", "altura"] as const);
  const rotulos = { distancia_inicio: "do início", largura: "largura", altura: "altura", peitoril: "peitoril" };
  return (
    <Caixa titulo={`${a.tipo === "porta" ? "Porta" : "Janela"} ${id}`}>
      <p className="mb-1 text-sm text-stone-600">
        na parede{" "}
        <button className="text-sky-700 hover:underline" onClick={() => aoItem({ tipo: "parede", id: a.parede })}>
          {a.parede}
        </button>
      </p>
      {medidas.map((c) => (
        <CampoMedida key={c} rotulo={rotulos[c]} medida={(a as Record<string, unknown>)[c] as Medida} unidade={unidade} ocupado={ocupado} aoSalvar={(m) => alterar({ [c]: m })} />
      ))}
      {a.tipo === "porta" && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-stone-500">abre para</span>
          <select className="rounded border" value={a.abre_para ?? ""} onChange={(e) => alterar({ abre_para: e.target.value })}>
            {[a.de, a.para].map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
          <button className={botao} disabled={ocupado} onClick={() => alterar({ dobradica: a.dobradica === "fim" ? "inicio" : "fim" })}>
            trocar lado da dobradiça
          </button>
        </div>
      )}
      <button
        className={`${perigo} mt-3`}
        disabled={ocupado}
        onClick={() =>
          fazer(
            (versao) => ou(api.DELETE("/projetos/{codigo}/pavimentos/{pavimento}/aberturas/{id_}", { params: { path: caminho, query: { versao } } })),
            () => aoItem(null),
          )
        }
      >
        remover
      </button>
    </Caixa>
  );
}

// ------------------------------------------------------------------ instalação

function PainelInstalacao({ id, pav, unidade, base, fazer, ocupado, aoItem }: Ctx & { id: string }) {
  const i = pav.instalacoes?.find((x) => x.id === id);
  const [dist, setDist] = useState("");
  if (!i) return null;
  const caminho = { ...base, id_: id };
  const alterar = (campos: Record<string, unknown>, distancia?: number) =>
    fazer((versao) =>
      ou(api.PATCH("/projetos/{codigo}/pavimentos/{pavimento}/instalacoes/{id_}", { params: { path: caminho, query: { versao } }, body: { campos, distancia } })),
    );
  const nome = TIPOS_INSTALACAO[i.tipo as TipoInstalacao] ?? i.tipo;
  return (
    <Caixa titulo={`${nome} ${id}`}>
      {"parede" in i && i.parede && <p className="mb-1 text-sm text-stone-600">na parede {i.parede}</p>}
      <CampoMedida rotulo="altura do piso" medida={i.altura} unidade={unidade} ocupado={ocupado} aoSalvar={(m) => alterar({ altura: m })} />
      {"parede" in i && i.parede && (
        <form
          className="mt-2 flex items-center gap-1 text-sm"
          onSubmit={(e) => {
            e.preventDefault();
            const mm = paraMm(dist, unidade);
            if (mm !== null) alterar({}, mm);
          }}
        >
          <span className="text-stone-500">mover para</span>
          <input className="w-16 rounded border px-1" value={dist} onChange={(e) => setDist(e.target.value)} />
          <span className="text-stone-500">{unidade} do início</span>
          <button className={botao} disabled={paraMm(dist, unidade) === null || ocupado}>ok</button>
        </form>
      )}
      <button
        className={`${perigo} mt-3`}
        disabled={ocupado}
        onClick={() =>
          fazer(
            (versao) => ou(api.DELETE("/projetos/{codigo}/pavimentos/{pavimento}/instalacoes/{id_}", { params: { path: caminho, query: { versao } } })),
            () => aoItem(null),
          )
        }
      >
        remover
      </button>
    </Caixa>
  );
}

// ------------------------------------------------------------------ cômodo

function PainelComodo({ id, pav, unidade, base, fazer, ocupado, aoItem }: Ctx & { id: string }) {
  const c = pav.comodos?.find((x) => x.id === id);
  const [nome, setNome] = useState(c?.nome ?? "");
  if (!c) return null;
  const caminho = { ...base, id_: id };
  const alterar = (campos: Record<string, unknown>) =>
    fazer((versao) =>
      ou(api.PATCH("/projetos/{codigo}/pavimentos/{pavimento}/comodos/{id_}", { params: { path: caminho, query: { versao } }, body: { campos } })),
    );
  return (
    <Caixa titulo={`Cômodo ${c.nome}`}>
      <form className="mb-2 flex gap-1 text-sm" onSubmit={(e) => (e.preventDefault(), nome.trim() && alterar({ nome: nome.trim() }))}>
        <input className="min-w-0 flex-1 rounded border px-1" value={nome} onChange={(e) => setNome(e.target.value)} />
        <button className={botao} disabled={nome.trim() === c.nome || ocupado}>renomear</button>
      </form>
      <label className="mb-2 flex items-center gap-2 text-sm">
        <span className="text-stone-500">tipo</span>
        <select className="rounded border" value={c.tipo} onChange={(e) => alterar({ tipo: e.target.value })}>
          {TIPOS_COMODO.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
        </select>
      </label>
      <CampoMedida rotulo="pé-direito" medida={c.pe_direito ?? pav.pe_direito} unidade={unidade} ocupado={ocupado} aoSalvar={(m) => alterar({ pe_direito: m })} />
      <p className="mt-1 text-xs text-stone-500">
        paredes:{" "}
        {c.paredes.map((p) => (
          <button key={p} className="mr-1 text-sky-700 hover:underline" onClick={() => aoItem({ tipo: "parede", id: p })}>
            {p}
          </button>
        ))}
      </p>
      <button
        className={`${perigo} mt-3`}
        disabled={ocupado}
        onClick={() =>
          fazer(
            (versao) => ou(api.DELETE("/projetos/{codigo}/pavimentos/{pavimento}/comodos/{id_}", { params: { path: caminho, query: { versao } } })),
            () => aoItem(null),
          )
        }
      >
        remover cômodo (e os móveis dele)
      </button>
    </Caixa>
  );
}
