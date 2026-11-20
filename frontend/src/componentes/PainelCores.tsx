import { btn, opcao } from "../estilo";
import { useEffect, useRef, useState } from "react";
import { api, ou, type Cores, type PavimentoTela } from "../api/cliente";
import { lerCor, rgbTexto } from "../cores";
import { useEditar, useVariacoes } from "../dados";
import { aplicar, type Chave, valorDe } from "../variacao";
import { SeletorCor } from "./SeletorCor";

/** Cores padrão do render (para o seletor mostrar algo quando a variação não define). */
export const PADRAO = { parede: "#eeeae3", piso: "#a67c52", teto: "#f7f5f0", rodape: "#ffffff" };

const vazio = (): Cores => ({ paredes: {}, moveis: {}, pecas: {} });

/** Detalhes abertos depois de a seleção passar de ``antes`` para ``agora``. */
export function trocarAberto(abertos: Set<string>, antes: string | null, agora: string | null): Set<string> {
  const n = new Set(abertos);
  if (antes) n.delete(antes);
  if (agora) n.add(agora);
  return n;
}

/** ``minhas-cores``, ``minhas-cores-2``, ... o primeiro nome de variação livre. */
export function nomeLivre(existentes: string[]): string {
  let n = 1;
  const nome = () => (n === 1 ? "minhas-cores" : `minhas-cores-${n}`);
  while (existentes.includes(nome())) n++;
  return nome();
}

export type Formato = "rgb" | "hex";

const codigo = (hex: string, formato: Formato) => (formato === "rgb" ? rgbTexto(hex) : hex);

/** Código da cor (RGB ou HEX) digitável; só aplica quando o código é válido. */
function CampoCodigo({
  hex,
  formato,
  aoMudar,
}: {
  hex: string;
  formato: Formato;
  aoMudar: (v: string) => void;
}) {
  const [texto, setTexto] = useState(codigo(hex, formato));
  const [focado, setFocado] = useState(false);
  useEffect(() => {
    if (!focado) setTexto(codigo(hex, formato));
  }, [hex, formato, focado]);
  const valido = lerCor(texto) !== null;
  return (
    <input
      className={`w-28 rounded-md border px-1 font-mono text-xs ${valido ? "" : "border-erro bg-erro-fundo"}`}
      value={texto}
      title={formato === "rgb" ? "R, G, B de 0 a 255 (também aceita #hex)" : "#rrggbb (também aceita R, G, B)"}
      placeholder={formato === "rgb" ? "R, G, B" : "#rrggbb"}
      onFocus={() => setFocado(true)}
      onBlur={() => {
        setFocado(false);
        setTexto(codigo(hex, formato));
      }}
      onChange={(e) => {
        setTexto(e.target.value);
        const lida = lerCor(e.target.value);
        if (lida) aoMudar(lida);
      }}
    />
  );
}

function Cor({
  rotulo,
  valor,
  padrao,
  formato,
  usadas,
  destacar = false,
  marcado,
  aoMarcar,
  aoRotulo,
  aoMudar,
}: {
  rotulo: string;
  valor?: string | null;
  padrao: string;
  formato: Formato;
  usadas: string[];
  destacar?: boolean;
  marcado: boolean;
  aoMarcar: () => void;
  /** Clicar no nome (móvel: seleciona o móvel). */
  aoRotulo?: () => void;
  aoMudar: (v: string | null) => void;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-2 py-0.5 text-sm ${destacar ? "-mx-1 rounded-sm bg-trena/15 px-1 ring-1 ring-trena" : ""}`}
    >
      <label className="flex min-w-0 items-center gap-1.5">
        <input type="checkbox" checked={marcado} onChange={aoMarcar} aria-label={`marcar ${rotulo}`} className="accent-tinta" />
        {aoRotulo ? (
          <button
            type="button"
            className={`truncate text-left hover:underline ${valor ? "" : "text-tinta-suave"}`}
            title="Selecionar este móvel"
            onClick={(e) => {
              e.preventDefault();
              aoRotulo();
            }}
          >
            {rotulo}
          </button>
        ) : (
          <span className={`truncate ${valor ? "" : "text-tinta-suave"}`}>{rotulo}</span>
        )}
        {destacar && <span className="text-xs text-tinta-suave">Selecionado</span>}
      </label>
      <span className="flex shrink-0 items-center gap-1">
        <CampoCodigo hex={valor ?? padrao} formato={formato} aoMudar={aoMudar} />
        <SeletorCor valor={valor ?? padrao} rotulo={rotulo} usadas={usadas} aoMudar={aoMudar} />
        {valor ? (
          <button type="button" className="w-10 text-left text-xs text-tinta-suave hover:underline" onClick={() => aoMudar(null)}>
            Limpar
          </button>
        ) : (
          <span className="w-10 text-xs text-tinta-suave">Padrão</span>
        )}
      </span>
    </div>
  );
}

/** Espera depois da última mudança antes de mandar o passo (arrastar no degradê vira um passo só). */
const ESPERA_MS = 600;

/**
 * Cores de um cômodo. "Base" = cores padrão (não editável); as outras são variações
 * guardadas à parte, que nunca mudam o projeto base. Cada mudança aparece na hora (planta e
 * 3D) e entra no rascunho logo depois (um passo; arrastar o degradê conta como um só): o
 * Desfazer volta passo a passo, e o Salvar do topo grava.
 * Marcando várias linhas, uma cor só pinta todas.
 */
export function PainelCores({
  codigo,
  comodo,
  geometria,
  ativa,
  aoAtivar,
  aoRascunho,
  destaque = null,
  aoSelecionarMovel,
}: {
  codigo: string;
  comodo: string;
  geometria: PavimentoTela;
  ativa: string;
  aoAtivar: (nome: string) => void;
  aoRascunho: (cores: Cores | null) => void;
  /** Móvel selecionado (planta ou 3D): a linha dele fica marcada. */
  destaque?: string | null;
  aoSelecionarMovel?: (id: string) => void;
}) {
  const variacoes = useVariacoes(codigo, comodo).data ?? {};
  const editar = useEditar(codigo);
  const [rascunho, setRascunho] = useState<Cores>(vazio);
  const [estado, setEstado] = useState<"salvo" | "pendente" | "salvando">("salvo");
  const [marcados, setMarcados] = useState<Set<Chave>>(new Set());
  // móveis com as partes abertas ("detalhes")
  const [abertos, setAbertos] = useState<Set<string>>(() => new Set(destaque ? [destaque] : []));
  // seleção manda nos detalhes: o móvel selecionado abre, o que deixou de ser fecha (os que
  // a pessoa abriu na mão continuam abertos)
  const destaqueAnterior = useRef(destaque);
  useEffect(() => {
    const antes = destaqueAnterior.current;
    destaqueAnterior.current = destaque;
    if (antes === destaque) return;
    setAbertos((a) => trocarAberto(a, antes, destaque));
  }, [destaque]);
  const [novoNome, setNovoNome] = useState("");
  const [formato, setFormato] = useState<Formato>(() => {
    try {
      return localStorage.getItem("formato-cor") === "hex" ? "hex" : "rgb";
    } catch {
      return "rgb";
    }
  });
  const trocarFormato = (f: Formato) => {
    setFormato(f);
    try {
      localStorage.setItem("formato-cor", f);
    } catch {
      /* sem armazenamento: vale só nesta aba */
    }
  };
  const c = geometria.comodos.find((x) => x.id === comodo);
  const paredes = [...new Set((c?.faces ?? []).map((f) => f.parede))].sort((a, b) =>
    a.localeCompare(b, undefined, { numeric: true }),
  );
  const moveis = geometria.moveis.filter((m) => m.comodo === comodo);
  const tipos = Object.fromEntries(moveis.map((m) => [m.id, m.tipo]));
  const salva = variacoes[ativa];
  // cores já escolhidas neste cômodo, para repetir com um clique
  const usadas = [
    ...new Set(
      [
        rascunho.parede, rascunho.piso, rascunho.teto, rascunho.rodape,
        ...Object.values(rascunho.paredes ?? {}), ...Object.values(rascunho.moveis ?? {}),
        ...Object.values(rascunho.pecas ?? {}).flatMap((p) => Object.values(p)),
      ]
        .filter((x): x is string => !!x)
        .map((x) => x.toLowerCase()),
    ),
  ];

  // gravação automática: ``ultimo`` = rascunho mais novo; ``geracao`` > 0 = mudança local
  // ainda não confirmada pelo servidor (aí o que vem do servidor não pode apagar o rascunho)
  const ultimo = useRef<Cores>(vazio());
  const geracao = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const gravarAgora = useRef<(() => void) | null>(null);

  const gravar = (nome: string, cores: Cores, apelido?: string | null, depois?: () => void) =>
    editar.mutate(
      (versao) =>
        ou(
          api.PUT("/projetos/{codigo}/comodos/{comodo}/variacoes/{nome}", {
            params: { path: { codigo, comodo, nome }, query: { versao } },
            body: { nome: apelido ?? variacoes[nome]?.nome ?? nome, cores },
          }),
        ),
      { onSuccess: () => aoAtivar(nome), onSettled: depois },
    );

  const ativaAnterior = useRef(ativa);
  useEffect(() => {
    const trocou = ativaAnterior.current !== ativa;
    ativaAnterior.current = ativa;
    if (!trocou && geracao.current > 0) return; // ainda gravando: não volta a cor no meio
    const cores = salva ? { ...vazio(), ...salva.cores } : vazio();
    ultimo.current = cores;
    setRascunho(cores);
    setMarcados(new Set());
  }, [ativa, salva]);
  useEffect(() => aoRascunho(ativa === "base" ? null : rascunho), [ativa, rascunho, aoRascunho]);
  // saiu do painel (outra aba, outro cômodo) com mudança esperando: grava já
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
      gravarAgora.current?.();
    },
    [],
  );

  const mudar = (chaves: Iterable<Chave>, valor: string | null) => {
    const novo = aplicar(ultimo.current, chaves, valor);
    ultimo.current = novo;
    setRascunho(novo);
    const g = ++geracao.current;
    setEstado("pendente");
    if (timer.current) clearTimeout(timer.current);
    const nome = ativa;
    gravarAgora.current = () => {
      gravarAgora.current = null;
      setEstado("salvando");
      gravar(nome, novo, null, () => {
        if (geracao.current === g) {
          geracao.current = 0;
          setEstado("salvo");
        }
      });
    };
    timer.current = setTimeout(() => gravarAgora.current?.(), ESPERA_MS);
  };
  const marcar = (k: Chave) =>
    setMarcados((m) => {
      const n = new Set(m);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });
  // mudar uma linha marcada pinta todas as marcadas
  const mudarLinha = (k: Chave) => (v: string | null) => mudar(marcados.has(k) ? marcados : [k], v);

  const linha = (k: Chave, rotulo: string, padrao: string, extra: Partial<Parameters<typeof Cor>[0]> = {}) => (
    <Cor
      key={k}
      formato={formato}
      usadas={usadas}
      rotulo={rotulo}
      valor={valorDe(rascunho, k, tipos)}
      padrao={padrao}
      marcado={marcados.has(k)}
      aoMarcar={() => marcar(k)}
      aoMudar={mudarLinha(k)}
      {...extra}
    />
  );
  const primeiro = [...marcados][0];

  return (
    <section className="border-b border-linha p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-tinta-suave">
        Cores · {c?.nome ?? comodo}
      </h2>
      <div className="mb-2 flex flex-wrap gap-1">
        {["base", ...Object.keys(variacoes)].map((n) => (
          <button
            key={n}
            onClick={() => aoAtivar(n)}
            className={`rounded-md px-2 py-0.5 text-sm ${opcao(n === ativa)}`}
          >
            {n === "base" ? "base" : (variacoes[n]?.nome ?? n)}
          </button>
        ))}
      </div>
      <form
        className="mb-3 flex gap-1 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          const nome = novoNome.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-");
          if (nome) gravar(nome, ativa === "base" ? vazio() : rascunho, novoNome.trim());
          setNovoNome("");
        }}
      >
        <input
          className="min-w-0 flex-1 rounded-md border px-1"
          placeholder={ativa === "base" ? "nova variação (ex.: Escura)" : "Duplicar como…"}
          value={novoNome}
          onChange={(e) => setNovoNome(e.target.value)}
        />
        <button className="rounded-md border border-linha-forte px-2" disabled={!novoNome.trim() || editar.isPending}>
          Criar
        </button>
      </form>

      {ativa === "base" ? (
        <div className="text-sm text-tinta-suave">
          <button
            className={`mb-1 ${btn("primario", "sm")}`}
            disabled={editar.isPending}
            onClick={() => gravar(nomeLivre(Object.keys(variacoes)), vazio(), "Minhas cores")}
          >
            Pintar este cômodo
          </button>
          <p>
            "base" são as cores padrão. Pintar cria uma variação ("Minhas cores"): o projeto base não muda e
            dá para comparar depois.
          </p>
        </div>
      ) : (
        <>
          <div className="mb-2 flex items-center gap-2 text-xs text-tinta-suave">
            Código da cor
            {(["rgb", "hex"] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => trocarFormato(f)}
                className={`rounded-md px-1.5 py-0.5 uppercase ${opcao(f === formato)}`}
              >
                {f}
              </button>
            ))}
            <span className="ml-auto" aria-live="polite">
              {estado === "salvo" ? "" : "Aplicando…"}
            </span>
          </div>
          {marcados.size > 0 ? (
            <div className="sticky top-0 z-10 -mx-1 mb-2 flex items-center gap-2 rounded-md border border-linha-forte bg-superficie px-2 py-1 text-sm shadow-sm">
              <span className="font-medium">{marcados.size} marcados</span>
              <SeletorCor
                valor={valorDe(rascunho, primeiro, tipos) ?? "#d6d3d1"}
                rotulo={`${marcados.size} marcados`}
                usadas={usadas}
                aoMudar={(v) => mudar(marcados, v)}
              />
              <button type="button" className="text-xs text-tinta-suave hover:underline" onClick={() => mudar(marcados, null)}>
                Padrão
              </button>
              <button type="button" className="ml-auto text-xs text-tinta-suave hover:underline" onClick={() => setMarcados(new Set())}>
                Desmarcar
              </button>
            </div>
          ) : (
            <p className="mb-1 text-xs text-tinta-suave">Marque várias linhas para pintar todas com a mesma cor.</p>
          )}
          {linha("parede", "paredes (geral)", PADRAO.parede)}
          {linha("piso", "piso", PADRAO.piso)}
          {linha("teto", "teto", PADRAO.teto)}
          {linha("rodape", "rodapé", PADRAO.rodape)}
          <h3 className="mt-2 text-xs text-tinta-suave">Cada parede (face deste cômodo)</h3>
          {paredes.map((p) => linha(`p:${p}`, p, rascunho.parede ?? PADRAO.parede))}
          {moveis.length > 0 && <h3 className="mt-2 text-xs text-tinta-suave">Móveis (clique no nome para selecionar)</h3>}
          {moveis.map((m) => {
            const partes = m.partes ?? [];
            const aberto = abertos.has(m.id);
            const corpo = valorDe(rascunho, `m:${m.id}`, tipos) ?? "#d6d3d1";
            const comCor = partes.filter((pt) => valorDe(rascunho, `q:${m.id}:${pt.id}`, tipos)).length;
            return (
              <div key={m.id}>
                {linha(`m:${m.id}`, m.nome ?? m.id, "#d6d3d1", {
                  destacar: m.id === destaque,
                  aoRotulo: aoSelecionarMovel ? () => aoSelecionarMovel(m.id) : undefined,
                })}
                {partes.length > 0 && (
                  <button
                    type="button"
                    aria-expanded={aberto}
                    className="ml-6 text-xs text-tinta-suave hover:underline"
                    onClick={() =>
                      setAbertos((a) => {
                        const n = new Set(a);
                        if (n.has(m.id)) n.delete(m.id);
                        else n.add(m.id);
                        return n;
                      })
                    }
                  >
                    {aberto ? "▾" : "▸"} detalhes ({partes.map((pt) => pt.nome.toLowerCase()).join(", ")})
                    {comCor > 0 && ` · ${comCor} com cor própria`}
                  </button>
                )}
                {aberto && (
                  <div className="ml-6 border-l border-linha pl-2">
                    {partes.map((pt) => linha(`q:${m.id}:${pt.id}`, pt.nome, corpo))}
                  </div>
                )}
              </div>
            );
          })}
          <div className="mt-3">
            <button
              className="text-sm text-erro hover:underline"
              disabled={editar.isPending}
              onClick={() => {
                if (timer.current) clearTimeout(timer.current);
                gravarAgora.current = null;
                geracao.current = 0;
                editar.mutate(
                  (versao) =>
                    ou(
                      api.DELETE("/projetos/{codigo}/comodos/{comodo}/variacoes/{nome}", {
                        params: { path: { codigo, comodo, nome: ativa }, query: { versao } },
                      }),
                    ),
                  { onSuccess: () => aoAtivar("base") },
                );
              }}
            >
              Apagar variação
            </button>
          </div>
        </>
      )}
      {editar.error && <p className="mt-1 text-sm text-erro">{editar.error.message}</p>}
    </section>
  );
}
