import { maiuscula } from "../texto";
import { useEffect, useState } from "react";
import { URL_API, type InfoRender } from "../api/cliente";
import { ultimasImagens } from "../comparar";
import { useEstimativas, usePedirRender, useRenders, useVariacoes, useVistas } from "../dados";
import { Comparador } from "./Comparador";
import { formatarTempo } from "../tempo";
import { alternar, guardar, lembrar, vistaDaImagem, vistasValidas } from "../vistas";

const ROTULO: Record<string, string> = {
  na_fila: "Na fila",
  rodando: "Renderizando",
  pronto: "Pronto",
  erro: "Erro",
};

function Item({ r, titulos }: { r: InfoRender; titulos: Record<string, string> }) {
  const pct = Math.round(r.progresso * 100);
  return (
    <li className="rounded border border-stone-200 bg-white p-2 text-sm">
      <div className="flex justify-between">
        <span>
          <b>{maiuscula(r.variacao)}</b> · {r.qualidade} · {r.vistas.length} {r.vistas.length === 1 ? "vista" : "vistas"}
        </span>
        <span className={r.status === "erro" ? "text-red-700" : "text-stone-500"}>{ROTULO[r.status]}</span>
      </div>
      {r.status === "na_fila" && (
        <p className="text-xs text-stone-500">Estimativa: ~{formatarTempo(r.estimativa_s)}</p>
      )}
      {r.status === "rodando" && (
        <>
          <div className="mt-1 h-2 overflow-hidden rounded bg-stone-200">
            <div className="h-full bg-sky-600 transition-all" style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-0.5 text-xs text-stone-500">
            Imagem {r.imagem_atual ?? 1} de {r.imagens} · {pct}% · faltam ~{formatarTempo(r.restante_s)}
          </p>
        </>
      )}
      {r.status === "pronto" && (
        <>
          <div className="mt-1 grid grid-cols-2 gap-1">
            {r.imagens_url.map((u) => {
              const v = vistaDaImagem(u);
              return (
                <a key={u} href={URL_API + u} target="_blank" rel="noreferrer" className="block">
                  <img src={URL_API + u} alt={titulos[v] ?? v} className="rounded border" />
                  <span className="block truncate text-xs text-stone-500">{titulos[v] ?? v}</span>
                </a>
              );
            })}
          </div>
          <p className="mt-0.5 text-xs text-stone-500">
            {r.em_cache ? "Já estava pronto (nada mudou)" : `Levou ${formatarTempo(r.duracao_s)}`} · versão{" "}
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
  const disponiveis = useVistas(codigo, comodo).data ?? [];
  const nomes = disponiveis.map((v) => v.nome);
  const titulos = Object.fromEntries(disponiveis.map((v) => [v.nome, v.titulo]));
  const [escolha, setEscolha] = useState<string[] | null>(() => lembrar(codigo, comodo));
  const vistas = vistasValidas(escolha, nomes);
  useEffect(() => {
    if (escolha !== null) guardar(codigo, comodo, escolha);
  }, [codigo, comodo, escolha]);
  const est = useEstimativas(Math.max(vistas.length, 1)).data;
  const pedir = usePedirRender(codigo, comodo);
  const semVista = vistas.length === 0;
  const variacoes = useVariacoes(codigo, comodo).data ?? {};
  const nomesVariacoes = Object.fromEntries([
    ["base", "Base (cores padrão)"],
    ...Object.entries(variacoes).map(([k, v]) => [k, v.nome ?? k]),
  ]);
  const comImagem = Object.keys(ultimasImagens(lista)).length;
  const [comparando, setComparando] = useState(false);
  const botao = "flex-1 rounded border border-stone-300 px-2 py-1 text-sm hover:bg-stone-100 disabled:opacity-40";
  return (
    <section className="border-b border-stone-200 p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
        Imagens 3D · variação {variacao}
      </h2>
      <p className="mb-1 text-xs text-stone-500">Vistas (cada uma é uma imagem):</p>
      <div className="mb-2 flex flex-wrap gap-1">
        {disponiveis.map((v) => {
          const ligada = vistas.includes(v.nome);
          return (
            <button
              key={v.nome}
              aria-pressed={ligada}
              className={`rounded-full border px-2 py-0.5 text-xs ${
                ligada ? "border-stone-800 bg-stone-800 text-white" : "border-stone-300 bg-white hover:bg-stone-100"
              }`}
              onClick={() => setEscolha(alternar(vistas, v.nome, nomes))}
            >
              {v.titulo}
            </button>
          );
        })}
        {disponiveis.length === 0 && <span className="text-xs text-stone-400">Carregando vistas…</span>}
      </div>
      <div className="mb-2 flex gap-2">
        <button className={botao} disabled={pedir.isPending || semVista} onClick={() => pedir.mutate({ variacao, qualidade: "rascunho", vistas })}>
          Rascunho
          <span className="block text-xs text-stone-500">~{formatarTempo(est?.rascunho)}</span>
        </button>
        <button className={botao} disabled={pedir.isPending || semVista} onClick={() => pedir.mutate({ variacao, qualidade: "final", vistas })}>
          Final
          <span className="block text-xs text-stone-500">~{formatarTempo(est?.final)}</span>
        </button>
      </div>
      {pedir.error && <p className="mb-2 text-sm text-red-700">{pedir.error.message}</p>}
      <button
        className="mb-2 w-full rounded border border-stone-300 px-2 py-1 text-sm hover:bg-stone-100 disabled:opacity-40"
        disabled={comImagem < 2}
        title={comImagem < 2 ? "Precisa de imagens prontas de pelo menos duas variações" : undefined}
        onClick={() => setComparando(true)}
      >
        Comparar variações lado a lado
        {comImagem < 2 && <span className="block text-xs text-stone-500">Peça imagens de duas variações ou mais</span>}
      </button>
      {comparando && (
        <Comparador renders={lista} nomes={nomesVariacoes} titulos={titulos} aoFechar={() => setComparando(false)} />
      )}
      <ul className="space-y-2">
        {lista.slice(0, 6).map((r) => (
          <Item key={r.id} r={r} titulos={titulos} />
        ))}
      </ul>
      {lista.length === 0 && <p className="text-sm text-stone-500">Nenhuma imagem ainda.</p>}
    </section>
  );
}
