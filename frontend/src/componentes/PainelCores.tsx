import { useEffect, useState } from "react";
import { api, ou, type Cores, type PavimentoTela } from "../api/cliente";
import { lerCor, rgbTexto } from "../cores";
import { useEditar, useVariacoes } from "../dados";

/** Cores padrão do render (para o seletor mostrar algo quando a variação não define). */
export const PADRAO = { parede: "#eeeae3", piso: "#a67c52", teto: "#f7f5f0", rodape: "#ffffff" };

const vazio = (): Cores => ({ paredes: {}, moveis: {} });

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
      className={`w-28 rounded border px-1 font-mono text-xs ${valido ? "" : "border-red-400 bg-red-50"}`}
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
  aoMudar,
}: {
  rotulo: string;
  valor?: string | null;
  padrao: string;
  formato: Formato;
  aoMudar: (v: string | null) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2 py-0.5 text-sm">
      <span className={valor ? "" : "text-stone-500"}>{rotulo}</span>
      <span className="flex items-center gap-1">
        <CampoCodigo hex={valor ?? padrao} formato={formato} aoMudar={aoMudar} />
        <input
          type="color"
          aria-label={`cor de ${rotulo}`}
          className="h-6 w-8 cursor-pointer rounded border"
          value={valor ?? padrao}
          onChange={(e) => aoMudar(e.target.value)}
        />
        {valor ? (
          <button type="button" className="w-10 text-left text-xs text-stone-500 hover:underline" onClick={() => aoMudar(null)}>
            limpar
          </button>
        ) : (
          <span className="w-10 text-xs text-stone-400">padrão</span>
        )}
      </span>
    </div>
  );
}

/**
 * Cores de um cômodo. "Base" = cores padrão (não editável); as outras são variações
 * guardadas à parte, que nunca mudam o projeto base. Enquanto edita, a planta já mostra
 * o rascunho (``aoRascunho``); "salvar" grava a variação inteira.
 */
export function PainelCores({
  codigo,
  comodo,
  geometria,
  ativa,
  aoAtivar,
  aoRascunho,
}: {
  codigo: string;
  comodo: string;
  geometria: PavimentoTela;
  ativa: string;
  aoAtivar: (nome: string) => void;
  aoRascunho: (cores: Cores | null) => void;
}) {
  const variacoes = useVariacoes(codigo, comodo).data ?? {};
  const editar = useEditar(codigo);
  const [rascunho, setRascunho] = useState<Cores>(vazio);
  const [mudou, setMudou] = useState(false);
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
  const salva = variacoes[ativa];

  useEffect(() => {
    setRascunho(salva ? { ...vazio(), ...salva.cores } : vazio());
    setMudou(false);
  }, [ativa, salva]);
  useEffect(() => aoRascunho(ativa === "base" ? null : rascunho), [ativa, rascunho, aoRascunho]);

  const mudar = (f: (r: Cores) => Cores) => {
    setRascunho((r) => f({ ...r, paredes: { ...r.paredes }, moveis: { ...r.moveis } }));
    setMudou(true);
  };
  const tirarNulos = (o: Record<string, string>, k: string, v: string | null) => {
    if (v === null) delete o[k];
    else o[k] = v;
    return o;
  };

  const gravar = (nome: string, cores: Cores, apelido?: string | null) =>
    editar.mutate(
      (versao) =>
        ou(
          api.PUT("/projetos/{codigo}/comodos/{comodo}/variacoes/{nome}", {
            params: { path: { codigo, comodo, nome }, query: { versao } },
            body: { nome: apelido ?? salva?.nome ?? nome, cores },
          }),
        ),
      { onSuccess: () => aoAtivar(nome) },
    );

  return (
    <section className="border-b border-stone-200 p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
        Cores · {c?.nome ?? comodo}
      </h2>
      <div className="mb-2 flex flex-wrap gap-1">
        {["base", ...Object.keys(variacoes)].map((n) => (
          <button
            key={n}
            onClick={() => aoAtivar(n)}
            className={`rounded px-2 py-0.5 text-sm ${n === ativa ? "bg-stone-800 text-white" : "border border-stone-300"}`}
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
          className="min-w-0 flex-1 rounded border px-1"
          placeholder={ativa === "base" ? "nova variação (ex.: Escura)" : "duplicar como…"}
          value={novoNome}
          onChange={(e) => setNovoNome(e.target.value)}
        />
        <button className="rounded border border-stone-300 px-2" disabled={!novoNome.trim() || editar.isPending}>
          criar
        </button>
      </form>

      {ativa !== "base" && (
        <div className="mb-2 flex items-center gap-2 text-xs text-stone-500">
          código da cor
          {(["rgb", "hex"] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => trocarFormato(f)}
              className={`rounded px-1.5 py-0.5 uppercase ${f === formato ? "bg-stone-800 text-white" : "border border-stone-300"}`}
            >
              {f}
            </button>
          ))}
        </div>
      )}
      {ativa === "base" ? (
        <p className="text-sm text-stone-500">
          "base" são as cores padrão. Crie uma variação para pintar (o projeto base não muda).
        </p>
      ) : (
        <>
          <Cor formato={formato} rotulo="paredes (geral)" valor={rascunho.parede} padrao={PADRAO.parede}
               aoMudar={(v) => mudar((r) => ({ ...r, parede: v }))} />
          <Cor formato={formato} rotulo="piso" valor={rascunho.piso} padrao={PADRAO.piso} aoMudar={(v) => mudar((r) => ({ ...r, piso: v }))} />
          <Cor formato={formato} rotulo="teto" valor={rascunho.teto} padrao={PADRAO.teto} aoMudar={(v) => mudar((r) => ({ ...r, teto: v }))} />
          <Cor formato={formato} rotulo="rodapé" valor={rascunho.rodape} padrao={PADRAO.rodape}
               aoMudar={(v) => mudar((r) => ({ ...r, rodape: v }))} />
          <h3 className="mt-2 text-xs text-stone-500">Cada parede (face deste cômodo)</h3>
          {paredes.map((p) => (
            <Cor formato={formato} key={p} rotulo={p} valor={rascunho.paredes?.[p]} padrao={rascunho.parede ?? PADRAO.parede}
                 aoMudar={(v) => mudar((r) => ({ ...r, paredes: tirarNulos(r.paredes!, p, v) }))} />
          ))}
          {moveis.length > 0 && <h3 className="mt-2 text-xs text-stone-500">Móveis</h3>}
          {moveis.map((m) => (
            <Cor formato={formato} key={m.id} rotulo={m.nome ?? m.id} valor={rascunho.moveis?.[m.id] ?? rascunho.moveis?.[m.tipo]}
                 padrao="#d6d3d1" aoMudar={(v) => mudar((r) => ({ ...r, moveis: tirarNulos(r.moveis!, m.id, v) }))} />
          ))}
          <div className="mt-3 flex gap-2">
            <button
              className="rounded bg-stone-800 px-3 py-1 text-sm text-white disabled:opacity-40"
              disabled={!mudou || editar.isPending}
              onClick={() => gravar(ativa, rascunho)}
            >
              salvar
            </button>
            <button
              className="text-sm text-red-700 hover:underline"
              disabled={editar.isPending}
              onClick={() =>
                editar.mutate(
                  (versao) =>
                    ou(
                      api.DELETE("/projetos/{codigo}/comodos/{comodo}/variacoes/{nome}", {
                        params: { path: { codigo, comodo, nome: ativa }, query: { versao } },
                      }),
                    ),
                  { onSuccess: () => aoAtivar("base") },
                )
              }
            >
              apagar variação
            </button>
          </div>
        </>
      )}
      {editar.error && <p className="mt-1 text-sm text-red-700">{editar.error.message}</p>}
    </section>
  );
}
