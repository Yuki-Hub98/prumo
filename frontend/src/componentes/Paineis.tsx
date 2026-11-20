import { EscolhaOrigem } from "./Origem";
import { btn, opcao } from "../estilo";
import { maiuscula } from "../texto";
import { Crosshair, Info, OctagonAlert, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ou, type Medida, type PavimentoTela, type Problema } from "../api/cliente";
import { useCatalogo, useEditar, useEstimadas, useProjeto } from "../dados";
import { formatar, type Origem, paraMm, type Unidade } from "../unidades";
import { CampoMedida } from "./CampoMedida";
import { EditorPlanejado } from "./EditorPlanejado";

type ItemCatalogo = {
  tipo: string;
  nome: string;
  categoria: string;
  modelos: { id: string; nome: string; largura: number; profundidade: number; altura: number }[];
  modelo_padrao: string;
};

function Caixa({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-linha p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-tinta-suave">{titulo}</h2>
      {children}
    </section>
  );
}

const botao = btn("secundario", "xs");

// ------------------------------------------------------------------ móvel selecionado

export function PainelMovel({
  codigo,
  comodo,
  id,
  geometria,
  unidade,
  aoRemovido,
}: {
  codigo: string;
  comodo: string;
  id: string;
  geometria: PavimentoTela;
  unidade: Unidade;
  aoRemovido: () => void;
}) {
  const projeto = useProjeto(codigo).data;
  const editar = useEditar(codigo);
  const [parede, setParede] = useState("");
  const [distancia, setDistancia] = useState("0");
  const movel = projeto?.comodos[comodo]?.moveis?.find((m) => m.id === id);
  if (!movel) return null;
  const caminho = { codigo, comodo, id_: id };
  const paredesDoComodo = geometria.paredes.filter((p) => p.lado_a === comodo || p.lado_b === comodo);

  const mover = (corpo: { rotacao?: 0 | 90 | 180 | 270; parede?: string; distancia?: number }) =>
    editar.mutate((versao) =>
      ou(
        api.POST("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/mover", {
          params: { path: caminho, query: { versao } },
          body: corpo,
        }),
      ),
    );
  const alterar = (campo: string, m: Medida) =>
    editar.mutate((versao) =>
      ou(
        api.PATCH("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}", {
          params: { path: caminho, query: { versao } },
          body: { [campo]: m },
        }),
      ),
    );

  return (
    <Caixa titulo={`Móvel: ${movel.nome ?? movel.tipo}`}>
      <p className="mb-2 text-xs text-tinta-suave">
        {movel.tipo}
        {movel.modelo ? ` · ${movel.modelo}` : ""} · arraste na planta para mover
      </p>
      <div className="mb-2 flex flex-wrap gap-2">
        <button
          className={botao}
          disabled={editar.isPending}
          onClick={() => mover({ rotacao: (((movel.rotacao ?? 0) + 90) % 360) as 0 | 90 | 180 | 270 })}
        >
          Girar 90°
        </button>
        <button
          className={`${botao} text-erro`}
          disabled={editar.isPending}
          onClick={() =>
            editar.mutate(
              (versao) =>
                ou(
                  api.DELETE("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}", {
                    params: { path: caminho, query: { versao } },
                  }),
                ),
              { onSuccess: aoRemovido },
            )
          }
        >
          Remover
        </button>
      </div>
      <form
        className="mb-2 flex flex-wrap items-center gap-1 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          const mm = paraMm(distancia, unidade);
          if (parede && mm !== null) mover({ parede, distancia: mm });
        }}
      >
        <span className="text-tinta-suave">Encostar na</span>
        <select className="rounded-md border" value={parede} onChange={(e) => setParede(e.target.value)}>
          <option value="">parede…</option>
          {paredesDoComodo.map((p) => (
            <option key={p.id} value={p.id}>
              {p.id}
            </option>
          ))}
        </select>
        <span className="text-tinta-suave">a</span>
        <input className="w-16 rounded-md border px-1" value={distancia} onChange={(e) => setDistancia(e.target.value)} />
        <span className="text-tinta-suave">{unidade} do início</span>
        <button className={botao} disabled={!parede || editar.isPending}>
          Ok
        </button>
      </form>
      {(["largura", "profundidade", "altura", "elevacao"] as const).map((campo) => (
        <CampoMedida
          key={campo}
          rotulo={campo}
          medida={movel[campo]}
          unidade={unidade}
          ocupado={editar.isPending}
          aoSalvar={(m) => alterar(campo, m)}
        />
      ))}
      {(geometria.moveis.find((m) => m.id === id)?.formas?.length ?? 0) > 1 && (
        <Forma
          forma={movel.forma ?? null}
          raio={movel.raio}
          braco={movel.braco}
          lado={movel.lado_l ?? "esquerda"}
          unidade={unidade}
          ocupado={editar.isPending}
          aoMudar={(campos) =>
            editar.mutate((versao) =>
              ou(
                api.PATCH("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}", {
                  params: { path: caminho, query: { versao } },
                  body: campos,
                }),
              ),
            )
          }
        />
      )}
      {editar.error && <p className="mt-1 text-sm text-erro">{editar.error.message}</p>}
      {geometria.moveis.find((m) => m.id === id)?.planejavel && (
        <div className="-mx-3 mt-2 border-t border-linha">
          <EditorPlanejado
            codigo={codigo}
            comodo={comodo}
            id={id}
            construcao={movel.construcao}
            portas={movel.portas}
            unidade={unidade}
          />
        </div>
      )}
    </Caixa>
  );
}

const FORMAS: { id: "arredondado" | "redondo" | "L" | null; nome: string }[] = [
  { id: null, nome: "Retangular" },
  { id: "arredondado", nome: "Cantos arredondados" },
  { id: "redondo", nome: "Redondo / oval" },
  { id: "L", nome: "Em L" },
];

/** Forma vista de cima: retangular, cantos arredondados (raio), redondo/oval ou em L. */
function Forma({
  forma,
  raio,
  braco,
  lado,
  unidade,
  ocupado,
  aoMudar,
}: {
  forma: "arredondado" | "redondo" | "L" | null;
  raio?: Medida | null;
  braco?: Medida | null;
  lado: "esquerda" | "direita";
  unidade: Unidade;
  ocupado: boolean;
  aoMudar: (campos: Record<string, unknown>) => void;
}) {
  return (
    <div className="mt-2 border-t border-linha pt-2 text-sm">
      <span className="text-tinta-suave">Forma</span>
      <div className="mt-1 flex flex-wrap gap-1">
        {FORMAS.map((f) => (
          <button
            key={f.nome}
            type="button"
            disabled={ocupado || forma === f.id}
            onClick={() => aoMudar({ forma: f.id })}
            className={`rounded-md px-2 py-0.5 text-xs ${opcao(forma === f.id)}`}
          >
            {f.nome}
          </button>
        ))}
      </div>
      {forma === "arredondado" && (
        <CampoMedida rotulo="Raio dos cantos" medida={raio} unidade={unidade} ocupado={ocupado} aoSalvar={(m) => aoMudar({ raio: m })} />
      )}
      {forma === "arredondado" && !raio && <p className="text-xs text-tinta-suave">Sem raio: 10 cm</p>}
      {forma === "L" && (
        <>
          <CampoMedida rotulo="Largura do braço" medida={braco} unidade={unidade} ocupado={ocupado} aoSalvar={(m) => aoMudar({ braco: m })} />
          {!braco && <p className="text-xs text-tinta-suave">Sem medida: 40 % do lado menor</p>}
          <div className="mt-1 flex items-center gap-1 text-xs">
            <span className="text-tinta-suave">Braço para a frente do lado</span>
            {(["esquerda", "direita"] as const).map((l) => (
              <button
                key={l}
                type="button"
                disabled={ocupado || lado === l}
                onClick={() => aoMudar({ lado_l: l })}
                className={`rounded-md px-1.5 py-0.5 ${opcao(lado === l)}`}
              >
                {l}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ adicionar móvel

/** ``comodos.quarto.moveis[sob-medida-2]`` → ``sob-medida-2`` (o id que o servidor deu). */
export function idCriado(caminhos: string[]): string | null {
  for (const c of caminhos) {
    const m = /\.moveis\[([^\]]+)\]$/.exec(c);
    if (m) return m[1];
  }
  return null;
}

/** Móvel do zero: nome e medidas livres (caixa); depois dá para montar por dentro. */
function CriarDoZero({
  codigo,
  comodo,
  centro,
  unidade,
  aoCriado,
}: {
  codigo: string;
  comodo: string;
  centro: [number, number] | undefined;
  unidade: Unidade;
  aoCriado?: (id: string) => void;
}) {
  const editar = useEditar(codigo);
  const [nome, setNome] = useState("");
  const [medidas, setMedidas] = useState({ largura: "", profundidade: "", altura: "" });
  const [origem, setOrigem] = useState<Origem | null>(null);
  const mm = Object.fromEntries(Object.entries(medidas).map(([k, v]) => [k, paraMm(v, unidade)])) as Record<
    keyof typeof medidas,
    number | null
  >;
  const pronto = !!centro && !!origem && Object.values(mm).every((v) => v !== null && v > 0);
  return (
    <form
      className="mt-3 flex flex-col gap-1 border-t border-linha pt-2 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        if (!pronto) return;
        editar.mutate(
          (versao) =>
            ou(
              api.POST("/projetos/{codigo}/comodos/{comodo}/moveis", {
                params: { path: { codigo, comodo }, query: { versao } },
                body: {
                  tipo: "sob_medida",
                  nome: nome.trim() || null,
                  centro: [Math.round(centro![0]), Math.round(centro![1])],
                  medidas: Object.fromEntries(
                    Object.entries(mm).map(([k, v]) => [k, { valor: v!, origem: origem! }]),
                  ),
                },
              }),
            ),
          {
            onSuccess: (r) => {
              const novo = idCriado(r.alteracoes.map((a) => a.caminho));
              if (novo) aoCriado?.(novo);
              setNome("");
              setMedidas({ largura: "", profundidade: "", altura: "" });
              setOrigem(null);
            },
          },
        );
      }}
    >
      <h3 className="text-xs font-semibold text-tinta-suave">Criar do zero</h3>
      <input
        className="rounded-md border px-1"
        placeholder="Nome (ex.: gabinete, nicho, bancada)"
        value={nome}
        onChange={(e) => setNome(e.target.value)}
      />
      <div className="grid grid-cols-3 gap-1">
        {(["largura", "profundidade", "altura"] as const).map((k) => (
          // min-w-0 + w-full: o campo cabe no terço da grade (sem isso o input do navegador
          // tem largura mínima própria, os três se sobrepõem e vazam do painel)
          <label key={k} className="grid min-w-0 text-xs text-tinta-suave">
            <span className="truncate" title={`${maiuscula(k)} (${unidade})`}>
              {maiuscula(k)} ({unidade})
            </span>
            <input
              className={`w-full min-w-0 rounded-md border px-1 text-sm ${medidas[k] && mm[k] === null ? "border-erro" : ""}`}
              inputMode="decimal"
              value={medidas[k]}
              onChange={(e) => setMedidas((m) => ({ ...m, [k]: e.target.value }))}
            />
          </label>
        ))}
      </div>
      <EscolhaOrigem rotulo="As medidas são:" valor={origem} aoEscolher={setOrigem} />
      <button className={botao} disabled={!pronto || editar.isPending}>
        Criar no centro do cômodo
      </button>
      {editar.error && <p className="text-erro">{editar.error.message}</p>}
    </form>
  );
}

export function AdicionarMovel({
  codigo,
  geometria,
  unidade,
  aoCriado,
}: {
  codigo: string;
  geometria: PavimentoTela;
  unidade: Unidade;
  aoCriado?: (id: string) => void;
}) {
  const catalogo = useCatalogo().data as { itens: ItemCatalogo[] } | undefined;
  const editar = useEditar(codigo);
  const comodos = geometria.comodos.filter((c) => c.centro);
  const [comodo, setComodo] = useState("");
  const [tipo, setTipo] = useState("");
  const [modelo, setModelo] = useState("");
  const item = catalogo?.itens.find((i) => i.tipo === tipo);
  const alvo = comodo || comodos[0]?.id || "";
  const centro = comodos.find((c) => c.id === alvo)?.centro;

  return (
    <Caixa titulo="Adicionar móvel">
      <div className="flex flex-col gap-1 text-sm">
        <select className="rounded-md border" value={alvo} onChange={(e) => setComodo(e.target.value)}>
          {comodos.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </select>
        <select
          className="rounded-md border"
          value={tipo}
          onChange={(e) => {
            setTipo(e.target.value);
            setModelo("");
          }}
        >
          <option value="">Tipo…</option>
          {catalogo?.itens.map((i) => (
            <option key={i.tipo} value={i.tipo}>
              {i.nome}
            </option>
          ))}
        </select>
        {item && (
          <select className="rounded-md border" value={modelo || item.modelo_padrao} onChange={(e) => setModelo(e.target.value)}>
            {item.modelos.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nome} ({m.largura} × {m.profundidade} mm)
              </option>
            ))}
          </select>
        )}
        <button
          className={botao}
          disabled={!item || !centro || editar.isPending}
          onClick={() =>
            editar.mutate((versao) =>
              ou(
                api.POST("/projetos/{codigo}/comodos/{comodo}/moveis", {
                  params: { path: { codigo, comodo: alvo }, query: { versao } },
                  body: {
                    tipo,
                    modelo: modelo || null,
                    centro: [Math.round(centro![0]), Math.round(centro![1])],
                  },
                }),
              ),
            )
          }
        >
          Pôr no centro do cômodo
        </button>
        <p className="text-xs text-tinta-suave">As medidas do catálogo entram como chute; ajuste depois.</p>
        {editar.error && <p className="text-erro">{editar.error.message}</p>}
      </div>
      <CriarDoZero
        codigo={codigo}
        comodo={alvo}
        centro={centro ? [centro[0], centro[1]] : undefined}
        unidade={unidade}
        aoCriado={aoCriado}
      />
    </Caixa>
  );
}

// ------------------------------------------------------------------ problemas e falta medir

type Gravidade = "erro" | "aviso" | "info";

const SEV: Record<Gravidade, { Icone: typeof Info; cls: string; nome: string }> = {
  erro: { Icone: OctagonAlert, cls: "bg-erro-fundo text-erro", nome: "Erro" },
  aviso: { Icone: TriangleAlert, cls: "bg-aviso-fundo text-aviso", nome: "Aviso" },
  info: { Icone: Info, cls: "bg-info-fundo text-info", nome: "Info" },
};

/** A pior gravidade presente (para a cor do contador da aba). */
export function piorGravidade(problemas: Problema[]): Gravidade | null {
  for (const g of ["erro", "aviso", "info"] as const) if (problemas.some((p) => p.severidade === g)) return g;
  return null;
}

/** Lista de problemas: ícone e cor da gravidade, mensagem, cômodo e "Ver na planta". */
export function PainelProblemas({
  problemas,
  novos,
  aoVer,
}: {
  problemas: Problema[];
  novos: Problema[];
  aoVer?: (p: Problema) => void;
}) {
  const chave = (p: Problema) => `${p.codigo}|${p.comodo}|${p.elemento}`;
  const recentes = new Set(novos.map(chave));
  return (
    <Caixa titulo={`Problemas (${problemas.length})`}>
      {problemas.length === 0 && <p className="text-sm text-tinta-suave">Nenhum</p>}
      <ul className="space-y-1.5 text-sm">
        {problemas.map((p, i) => {
          const g = SEV[(p.severidade as Gravidade) in SEV ? (p.severidade as Gravidade) : "info"];
          const naPlanta = !!(p.posicao || p.regiao?.length);
          return (
            <li key={i} className={`flex gap-2 rounded-md px-2 py-1.5 ${g.cls}`}>
              <g.Icone size={16} className="mt-0.5 shrink-0" aria-label={g.nome} />
              <div className="min-w-0 flex-1">
                <p>
                  {recentes.has(chave(p)) && (
                    <span className="mr-1 rounded-sm bg-superficie px-1 text-xs font-semibold text-tinta">Novo</span>
                  )}
                  {maiuscula(p.mensagem)}
                </p>
                {(p.comodo || (naPlanta && aoVer)) && (
                  <p className="mt-0.5 flex items-center justify-between gap-2 text-xs">
                    <span className="text-tinta-suave">{p.comodo ?? ""}</span>
                    {naPlanta && aoVer && (
                      <button className={btn("fantasma", "xs")} onClick={() => aoVer(p)}>
                        <Crosshair size={12} /> Ver na planta
                      </button>
                    )}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Caixa>
  );
}

/** Faixa fixa embaixo da barra do topo enquanto houver medida "Chute". */
export function FaixaPreliminar({ codigo, aoVer }: { codigo: string; aoVer: () => void }) {
  const n = useEstimadas(codigo).data?.length ?? 0;
  if (!n) return null;
  return (
    <div className="flex shrink-0 items-center gap-3 border-b border-linha bg-superficie px-4 py-1.5">
      <span className="border-[3px] border-double border-erro px-2 py-0.5 font-cond text-xs font-semibold uppercase tracking-[0.08em] text-erro">
        Preliminar — não usar para obra
      </span>
      <button className="link text-sm" onClick={aoVer}>
        Ver o que falta medir ({n})
      </button>
    </div>
  );
}

export function FaltaMedir({ codigo, unidade, pedido = 0 }: { codigo: string; unidade: Unidade; pedido?: number }) {
  const estimadas = useEstimadas(codigo).data ?? [];
  const [aberto, setAberto] = useState(false);
  const caixa = useRef<HTMLDivElement>(null);
  // "Ver o que falta medir" na faixa PRELIMINAR: abre a lista e rola até ela
  useEffect(() => {
    if (!pedido) return;
    setAberto(true);
    caixa.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [pedido]);
  return (
    <div ref={caixa}>
    <Caixa titulo={`Falta medir (${estimadas.length})`}>
      {estimadas.length === 0 ? (
        <p className="text-sm text-medido">Tudo medido: os desenhos saem sem PRELIMINAR</p>
      ) : (
        <>
          <p className="text-sm text-aviso">
            Enquanto houver chute, os desenhos saem PRELIMINAR — NÃO USAR PARA OBRA.
          </p>
          <button className="text-xs link" onClick={() => setAberto(!aberto)}>
            {aberto ? "Esconder" : "Ver lista"}
          </button>
          {aberto && (
            <ul className="mt-1 max-h-64 space-y-0.5 overflow-auto text-xs">
              {estimadas.map((e) => (
                <li key={e.caminho}>
                  {e.entidade_codigo ?? e.entidade} · {e.campo}: {formatar(e.valor, unidade)}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Caixa>
    </div>
  );
}
