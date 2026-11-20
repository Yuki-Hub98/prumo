import { History, Redo2, Undo2 } from "lucide-react";
import { btn } from "../estilo";
import { useEffect, useState } from "react";
import { api, ou, type Problema } from "../api/cliente";
import { useEditar, useVersoes } from "../dados";
import { nomeOperacao, resumoCaminho } from "../historico";

const botao = btn("fantasma", "sm");

function digitando(alvo: EventTarget | null): boolean {
  const el = alvo as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

/** Ações do rascunho (desfazer, refazer, salvar, descartar) com os atalhos Ctrl+Z,
 * Ctrl+Shift+Z (ou Ctrl+Y) e Ctrl+S. Usado uma vez na tela; os botões do topo e a barra
 * do rodapé recebem o mesmo objeto.
 *
 * Toda edição da tela entra num **rascunho**: dá para testar à vontade e desfazer passo a
 * passo; **Salvar versão** grava cada mudança como versão e atualiza ``projetos/``;
 * **Descartar** volta para o que estava salvo. */
export function useRascunho(codigo: string, aoProblemas: (novos: Problema[]) => void) {
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
  const rascunho = versoes?.rascunho ?? null;
  const passos = rascunho?.passos ?? 0;
  const [confirmar, setConfirmar] = useState(false);
  const fechar = (como: "salvar" | "descartar") => {
    setConfirmar(false);
    editar.mutate((versao) =>
      ou(
        como === "salvar"
          ? api.POST("/projetos/{codigo}/rascunho/salvar", { params: { path: { codigo }, query: { versao } } })
          : api.POST("/projetos/{codigo}/rascunho/descartar", { params: { path: { codigo }, query: { versao } } }),
      ),
    );
  };

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || digitando(e.target)) return;
      const k = e.key.toLowerCase();
      if (k === "z" && !e.shiftKey && podeDesfazer) voltar("desfazer");
      else if (((k === "z" && e.shiftKey) || k === "y") && podeRefazer) voltar("refazer");
      else if (k === "s" && passos > 0 && !editar.isPending) fechar("salvar");
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  });

  return { editar, voltar, podeDesfazer, podeRefazer, passos, confirmar, setConfirmar, fechar };
}

export type AcoesRascunho = ReturnType<typeof useRascunho>;

/** Desfazer / refazer / histórico no topo da tela (sempre visíveis). */
export function BotoesDesfazer({ acoes, aoHistorico }: { acoes: AcoesRascunho; aoHistorico: () => void }) {
  const { voltar, podeDesfazer, podeRefazer, editar } = acoes;
  return (
    <div className="flex items-center gap-1">
      <button className={botao} disabled={!podeDesfazer} onClick={() => voltar("desfazer")} title="Desfazer (Ctrl+Z)">
        <Undo2 size={16} /> Desfazer
      </button>
      <button className={botao} disabled={!podeRefazer} onClick={() => voltar("refazer")} title="Refazer (Ctrl+Shift+Z)">
        <Redo2 size={16} /> Refazer
      </button>
      <button className={botao} onClick={aoHistorico} title="Ver e voltar para uma versão">
        <History size={16} /> Histórico
      </button>
      {editar.error && <span className="text-sm text-erro">{editar.error.message}</span>}
    </div>
  );
}

/** Barra do rodapé, só quando há edição não salva:
 * ● Rascunho · N alterações · [Desfazer] [Refazer] ····· [Descartar] [Salvar versão]. */
export function BarraRascunho({ acoes }: { acoes: AcoesRascunho }) {
  const { voltar, podeDesfazer, podeRefazer, passos, confirmar, setConfirmar, fechar, editar } = acoes;
  if (passos <= 0) return null;
  return (
    <div
      role="region"
      aria-label="Rascunho"
      className="flex shrink-0 items-center gap-2 border-t border-linha bg-superficie px-4 py-2 text-sm shadow-flutuante"
    >
      <span className="size-2 rounded-full bg-trena" aria-hidden="true" />
      <span>
        <b className="font-semibold">Rascunho</b>
        <span className="text-tinta-suave"> · {passos === 1 ? "1 alteração" : `${passos} alterações`}</span>
      </span>
      <button className={btn("fantasma", "sm")} disabled={!podeDesfazer} onClick={() => voltar("desfazer")} title="Desfazer (Ctrl+Z)">
        <Undo2 size={16} /> Desfazer
      </button>
      <button className={btn("fantasma", "sm")} disabled={!podeRefazer} onClick={() => voltar("refazer")} title="Refazer (Ctrl+Shift+Z)">
        <Redo2 size={16} /> Refazer
      </button>
      <span className="ml-auto flex items-center gap-2">
        {confirmar ? (
          <>
            <span>Descartar tudo o que não foi salvo?</span>
            <button className={btn("secundario", "sm")} onClick={() => setConfirmar(false)}>
              Não
            </button>
            <button className={btn("perigo", "sm")} onClick={() => fechar("descartar")}>
              Sim, descartar
            </button>
          </>
        ) : (
          <>
            <button
              className={btn("secundario", "sm")}
              disabled={editar.isPending}
              onClick={() => setConfirmar(true)}
              title="Voltar para o que estava salvo"
            >
              Descartar
            </button>
            <button
              className={btn("primario", "sm")}
              disabled={editar.isPending}
              onClick={() => fechar("salvar")}
              title="Salvar (Ctrl+S): cada mudança vira uma versão"
            >
              Salvar versão
            </button>
          </>
        )}
      </span>
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
    <section className="border-b border-linha p-3">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-tinta-suave">Histórico</h2>
        <button className="text-sm link" onClick={aoFechar}>
          Fechar
        </button>
      </div>
      <p className="mb-2 text-xs text-tinta-suave">
        {versoes?.rascunho
          ? "Há mudanças não salvas: salve ou descarte para voltar a uma versão antiga. Enquanto isso, Desfazer volta um passo de cada vez."
          : "Voltar para uma versão grava o conteúdo dela como versão nova: nada é apagado e dá para desfazer."}
      </p>
      {editar.error && <p className="mb-2 text-sm text-erro">{editar.error.message}</p>}
      <ol className="space-y-1 text-sm">
        {versoes?.versoes.map((v) => {
          const atual = v.versao === versoes.atual;
          return (
            <li key={v.versao} className={`rounded-md px-2 py-1 ${atual ? "bg-superficie-2" : "hover:bg-superficie-2"}`}>
              <div className="flex items-baseline gap-2">
                <span className="w-8 shrink-0 text-xs text-tinta-suave">v{v.versao}</span>
                <span className="flex-1">
                  {nomeOperacao(v.operacao)}
                  {versoes.rascunho && v.versao > versoes.rascunho.desde && (
                    <span className="ml-1 rounded-md bg-aviso-fundo px-1 text-xs text-aviso">Não salva</span>
                  )}
                </span>
                <span className="text-xs text-tinta-suave">{quando(v.quando)}</span>
              </div>
              {v.caminhos.length > 0 && (
                <div className="ml-10 truncate text-xs text-tinta-suave" title={v.caminhos.join("\n")}>
                  {v.caminhos.map(resumoCaminho).join(", ")}
                  {v.alteracoes > v.caminhos.length && ` e mais ${v.alteracoes - v.caminhos.length}`}
                </div>
              )}
              <div className="ml-10 mt-0.5">
                {atual ? (
                  <span className="text-xs font-medium text-tinta-suave">Atual</span>
                ) : confirmar === v.versao ? (
                  <span className="text-xs">
                    Voltar para a v{v.versao}?{" "}
                    <button className="link" disabled={editar.isPending} onClick={() => restaurar(v.versao)}>
                      Sim
                    </button>{" "}
                    ·{" "}
                    <button className="text-tinta-suave hover:underline" onClick={() => setConfirmar(null)}>
                      Não
                    </button>
                  </span>
                ) : versoes.rascunho ? null : (
                  <button className="text-xs link" onClick={() => setConfirmar(v.versao)}>
                    Voltar para esta
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
