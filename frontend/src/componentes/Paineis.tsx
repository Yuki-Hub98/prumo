import { EscolhaOrigem } from "./Origem";
import { btn, opcao } from "../estilo";
import { maiuscula } from "../texto";
import { BookmarkPlus, Crosshair, Info, OctagonAlert, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, ou, type Medida, type PavimentoTela, type Problema } from "../api/cliente";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCatalogo, useEditar, useEstimadas, useModelosProprios, useProjeto } from "../dados";
import { formatar, type Origem, paraMm, type Unidade } from "../unidades";
import { CampoMedida } from "./CampoMedida";
import { EditorBancada } from "./EditorBancada";
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
  const catalogo = useCatalogo().data as { itens: ItemCatalogo[] } | undefined;
  const editar = useEditar(codigo);
  const [parede, setParede] = useState("");
  const [distancia, setDistancia] = useState("0");
  const movel = projeto?.comodos[comodo]?.moveis?.find((m) => m.id === id);
  if (!movel) return null;
  const caminho = { codigo, comodo, id_: id };
  const formas = geometria.moveis.find((m) => m.id === id)?.formas;
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
        {catalogo?.itens.find((i) => i.tipo === movel.tipo)?.nome ?? movel.tipo}
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
      <SalvarComoModelo codigo={codigo} comodo={comodo} movel={id} nomeAtual={movel.nome ?? ""} />
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
          rotulo={ROTULO_MEDIDA[campo] ?? maiuscula(campo)}
          medida={movel[campo]}
          unidade={unidade}
          ocupado={editar.isPending}
          aoSalvar={(m) => alterar(campo, m)}
        />
      ))}
      {(formas?.length ?? 0) > 1 && (
        <Forma
          formas={formas ?? []}
          sofa={movel.tipo === "sofa"}
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
      <Aparencia
        movel={movel}
        partes={(geometria.moveis.find((m) => m.id === id)?.partes ?? []).map((p) => p.id)}
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
      {editar.error && <p className="mt-1 text-sm text-erro">{editar.error.message}</p>}
      {movel.bancada && (
        <div className="-mx-3 mt-2 border-t border-linha">
          <EditorBancada
            codigo={codigo}
            comodo={comodo}
            id={id}
            bancada={movel.bancada}
            emL={movel.forma === "L"}
            ladoL={movel.lado_l ?? "esquerda"}
            comprimentos={comprimentosBancada(movel)}
            unidade={unidade}
          />
        </div>
      )}
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

/** Comprimento dos trechos da bancada (mm): costas = largura; braço do L = profundidade menos
 * a faixa das costas (sem medida, 60 cm, até 60 % do lado menor — como no core). */
export function comprimentosBancada(m: {
  largura: Medida;
  profundidade: Medida;
  braco?: Medida | null;
}): { costas: number; braco: number; faixa: number } {
  const menor = Math.min(m.largura.valor, m.profundidade.valor);
  const faixa = m.braco?.valor ?? Math.min(600, Math.round(menor * 0.6));
  return { costas: m.largura.valor, braco: m.profundidade.valor - faixa, faixa };
}

const FORMAS: { id: "arredondado" | "redondo" | "L" | null; nome: string }[] = [
  { id: null, nome: "Retangular" },
  { id: "arredondado", nome: "Cantos arredondados" },
  { id: "redondo", nome: "Redondo / oval" },
  { id: "L", nome: "Em L" },
];

/** Forma vista de cima: retangular, cantos arredondados (raio), redondo/oval ou em L. */
function Forma({
  formas,
  sofa,
  forma,
  raio,
  braco,
  lado,
  unidade,
  ocupado,
  aoMudar,
}: {
  /** As que o móvel aceita ("retangular", "arredondado", "redondo", "L"). */
  formas: string[];
  sofa: boolean;
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
        {FORMAS.filter((f) => formas.includes(f.id ?? "retangular")).map((f) => (
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
          {!braco && (
            <p className="text-xs text-tinta-suave">
              {sofa ? "Sem medida: fundo de um assento (90 cm)" : "Sem medida: 40 % do lado menor"}
            </p>
          )}
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

const ROTULO_MEDIDA: Record<string, string> = {
  largura: "Largura",
  profundidade: "Profundidade",
  altura: "Altura",
  elevacao: "Elevação",
  largura_porta: "Largura da porta",
};

/** Acabamento, puxador e pés (só visual; aparecem os que o tipo tem). A cor da variação
 * continua valendo por cima do acabamento. */
function Aparencia({
  movel,
  partes,
  ocupado,
  aoMudar,
}: {
  movel: { acabamento?: string | null; puxador?: string | null; pes?: string | null };
  partes: string[];
  ocupado: boolean;
  aoMudar: (campos: Record<string, string | null>) => void;
}) {
  const cat = useCatalogo().data as { acabamentos?: Record<string, string>; puxadores?: Record<string, string>; pes?: Record<string, string> } | undefined;
  const linhas: [string, string, Record<string, string> | undefined, string][] = [
    ["acabamento", "Acabamento", cat?.acabamentos, "Padrão do tipo"],
    ...(partes.includes("puxadores") ? ([["puxador", "Puxador", cat?.puxadores, "Barra (padrão)"]] as const) : []),
    ...(partes.includes("pes") || movel.pes === "rodape" ? ([["pes", "Pés", cat?.pes, "Padrão do tipo"]] as const) : []),
  ] as [string, string, Record<string, string> | undefined, string][];
  return (
    <div className="mt-2 space-y-1 text-sm">
      {linhas.map(([campo, rotulo, opcoes, padrao]) => (
        <label key={campo} className="flex items-center justify-between gap-2">
          <span className="text-tinta-suave">{rotulo}</span>
          <select
            className="rounded-md border"
            disabled={ocupado}
            value={(movel as Record<string, string | null | undefined>)[campo] ?? ""}
            onChange={(e) => aoMudar({ [campo]: e.target.value || null })}
          >
            <option value="">{padrao}</option>
            {Object.entries(opcoes ?? {}).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}

/** "Salvar como modelo": guarda o móvel (como está agora) em Meus modelos. */
function SalvarComoModelo({ codigo, comodo, movel, nomeAtual }: { codigo: string; comodo: string; movel: string; nomeAtual: string }) {
  const cliente = useQueryClient();
  const [nome, setNome] = useState<string | null>(null);
  const [salvo, setSalvo] = useState<string | null>(null);
  const salvar = useMutation({
    mutationFn: (n: string) => ou(api.POST("/modelos-proprios", { body: { projeto: codigo, comodo, movel, nome: n } })),
    onSuccess: (m) => {
      setSalvo(m.nome);
      setNome(null);
      cliente.invalidateQueries({ queryKey: ["modelos-proprios"] });
    },
  });
  if (nome === null)
    return (
      <p className="mb-2 flex items-center gap-2 text-xs">
        <button className={btn("fantasma", "xs")} onClick={() => (setNome(nomeAtual), setSalvo(null))}>
          <BookmarkPlus size={14} /> Salvar como modelo
        </button>
        {salvo && <span className="text-medido">“{salvo}” está em Meus modelos (Adicionar móvel).</span>}
      </p>
    );
  return (
    <form
      className="mb-2 flex flex-wrap items-center gap-1 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        if (nome.trim()) salvar.mutate(nome.trim());
      }}
    >
      <input autoFocus className="min-w-0 flex-1 rounded-md border px-1" value={nome} placeholder="Nome do modelo" onChange={(e) => setNome(e.target.value)} />
      <button className={btn("primario", "xs")} disabled={!nome.trim() || salvar.isPending}>Salvar</button>
      <button type="button" className={btn("fantasma", "xs")} onClick={() => setNome(null)}>Cancelar</button>
      {salvar.error && <p className="w-full text-xs text-erro">{salvar.error.message}</p>}
      <p className="w-full text-xs text-tinta-suave">Guarda medidas, forma e montagem por dentro, com a origem de cada medida; vale para todos os projetos.</p>
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
  const proprios = useModelosProprios().data ?? [];
  const cliente = useQueryClient();
  const proprio = tipo.startsWith("proprio:") ? proprios.find((m) => `proprio:${m.codigo}` === tipo) : undefined;
  const apagar = useMutation({
    mutationFn: (c: string) => ou(api.DELETE("/modelos-proprios/{codigo_modelo}", { params: { path: { codigo_modelo: c } } })),
    onSuccess: () => {
      setTipo("");
      cliente.invalidateQueries({ queryKey: ["modelos-proprios"] });
    },
  });
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
          {proprios.length > 0 && (
            <optgroup label="Meus modelos">
              {proprios.map((m) => (
                <option key={m.codigo} value={`proprio:${m.codigo}`}>
                  {m.nome}
                </option>
              ))}
            </optgroup>
          )}
          <optgroup label="Catálogo">
            {catalogo?.itens.map((i) => (
              <option key={i.tipo} value={i.tipo}>
                {i.nome}
              </option>
            ))}
          </optgroup>
        </select>
        {proprio && (
          <p className="flex items-center justify-between gap-2 text-xs text-tinta-suave">
            <span>
              <span className="num">
                {formatar(proprio.largura, unidade)} × {formatar(proprio.profundidade, unidade)} × {formatar(proprio.altura, unidade)}
              </span>
              {proprio.planejado && " · planejado"}
              {proprio.estimadas > 0 && <span className="text-chute"> · {proprio.estimadas} medida(s) chute</span>}
            </span>
            <button className="link text-erro" disabled={apagar.isPending} onClick={() => apagar.mutate(proprio.codigo)}>
              Apagar modelo
            </button>
          </p>
        )}
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
          disabled={!(item || proprio) || !centro || editar.isPending}
          onClick={() =>
            editar.mutate((versao) =>
              ou(
                api.POST("/projetos/{codigo}/comodos/{comodo}/moveis", {
                  params: { path: { codigo, comodo: alvo }, query: { versao } },
                  body: proprio
                    ? { tipo: proprio.tipo, modelo_proprio: proprio.codigo, centro: [Math.round(centro![0]), Math.round(centro![1])] }
                    : {
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
        <p className="text-xs text-tinta-suave">
          {proprio
            ? "O móvel sai igual ao modelo, com a origem que cada medida tinha."
            : "As medidas do catálogo entram como chute; ajuste depois."}
        </p>
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
