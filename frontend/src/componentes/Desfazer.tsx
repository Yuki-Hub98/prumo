import { useEffect, useState } from "react";
import { api, ou, type Problema } from "../api/cliente";
import { useEditar, useVersoes } from "../dados";
import { nomeOperacao, resumoCaminho } from "../historico";

const botao =
  "rounded border border-stone-300 px-2 py-0.5 text-sm hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-40";

function digitando(alvo: EventTarget | null): boolean {
  const el = alvo as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

/** Desfazer / refazer no topo da tela, com Ctrl+Z e Ctrl+Shift+Z (ou Ctrl+Y). */
export function BotoesDesfazer({
  codigo,
  aoProblemas,
  aoHistorico,
}: {
  codigo: string;
  aoProblemas: (novos: Problema[]) => void;
  aoHistorico: () => void;
}) {
  const versoes = useVersoes(codigo).data;
  const editar = useEditar(codigo);
  const voltar = (tipo: "desfazer" | "refazer") =>
    editar.mutate(
      (versao) =>
        ou(
          tipo === "desfazer"
            ? api.POST("/projetos/{codigo}/desfazer", { params: { path: { codigo }, query: { versao } } })
            : api.POST("/projetos/{codigo}/refazer", { params: { path: { codigo }, query: { versao } } }),
        ),
      { onSuccess: (r) => aoProblemas(r.novos) },
    );
  const podeDesfazer = versoes?.desfazer != null && !editar.isPending;
  const podeRefazer = versoes?.refazer != null && !editar.isPending;

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || digitando(e.target)) return;
      const k = e.key.toLowerCase();
      if (k === "z" && !e.shiftKey && podeDesfazer) voltar("desfazer");
      else if (((k === "z" && e.shiftKey) || k === "y") && podeRefazer) voltar("refazer");
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  });

  return (
    <div className="flex items-center gap-1">
      <button className={botao} disabled={!podeDesfazer} onClick={() => voltar("desfazer")} title="Desfazer (Ctrl+Z)">
        ↶ Desfazer
      </button>
      <button className={botao} disabled={!podeRefazer} onClick={() => voltar("refazer")} title="Refazer (Ctrl+Shift+Z)">
        ↷ Refazer
      </button>
      <button className={botao} onClick={aoHistorico} title="Ver e voltar para uma versão">
        Histórico
      </button>
      {editar.error && <span className="text-sm text-red-700">{editar.error.message}</span>}
    </div>
  );
}

function quando(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/** Lista de versões, da mais nova; cada uma pode virar a atual (gravada como versão nova). */
export function PainelHistorico({ codigo, aoFechar }: { codigo: string; aoFechar: () => void }) {
  const versoes = useVersoes(codigo).data;
  const editar = useEditar(codigo);
  const [confirmar, setConfirmar] = useState<number | null>(null);
  const restaurar = (para: number) =>
    editar.mutate(
      (versao) =>
        ou(
          api.POST("/projetos/{codigo}/versoes/{para}/restaurar", {
            params: { path: { codigo, para }, query: { versao } },
          }),
        ),
      { onSuccess: () => setConfirmar(null) },
    );
  return (
    <section className="border-b border-stone-200 p-3">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-stone-500">Histórico</h2>
        <button className="text-sm text-sky-700 hover:underline" onClick={aoFechar}>
          fechar
        </button>
      </div>
      <p className="mb-2 text-xs text-stone-500">
        Voltar para uma versão grava o conteúdo dela como versão nova: nada é apagado e dá para desfazer.
      </p>
      {editar.error && <p className="mb-2 text-sm text-red-700">{editar.error.message}</p>}
      <ol className="space-y-1 text-sm">
        {versoes?.versoes.map((v) => {
          const atual = v.versao === versoes.atual;
          return (
            <li key={v.versao} className={`rounded px-2 py-1 ${atual ? "bg-stone-200" : "hover:bg-stone-100"}`}>
              <div className="flex items-baseline gap-2">
                <span className="w-8 shrink-0 text-xs text-stone-400">v{v.versao}</span>
                <span className="flex-1">{nomeOperacao(v.operacao)}</span>
                <span className="text-xs text-stone-400">{quando(v.quando)}</span>
              </div>
              {v.caminhos.length > 0 && (
                <div className="ml-10 truncate text-xs text-stone-500" title={v.caminhos.join("\n")}>
                  {v.caminhos.map(resumoCaminho).join(", ")}
                  {v.alteracoes > v.caminhos.length && ` e mais ${v.alteracoes - v.caminhos.length}`}
                </div>
              )}
              <div className="ml-10 mt-0.5">
                {atual ? (
                  <span className="text-xs font-medium text-stone-600">atual</span>
                ) : confirmar === v.versao ? (
                  <span className="text-xs">
                    Voltar para a v{v.versao}?{" "}
                    <button className="text-sky-700 hover:underline" disabled={editar.isPending} onClick={() => restaurar(v.versao)}>
                      sim
                    </button>{" "}
                    ·{" "}
                    <button className="text-stone-500 hover:underline" onClick={() => setConfirmar(null)}>
                      não
                    </button>
                  </span>
                ) : (
                  <button className="text-xs text-sky-700 hover:underline" onClick={() => setConfirmar(v.versao)}>
                    voltar para esta
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
