import { useEffect, useMemo, useState } from "react";
import { URL_API, type InfoRender } from "../api/cliente";
import { ultimasImagens, vistasEmComum } from "../comparar";

/** Variações lado a lado, em tela cheia: a imagem pronta mais recente de cada uma na vista
 * escolhida. Esc ou "fechar" volta. */
export function Comparador({
  renders,
  nomes,
  titulos,
  aoFechar,
}: {
  renders: InfoRender[];
  /** variação → nome para mostrar */
  nomes: Record<string, string>;
  /** vista → título (Perspectiva, De cima...) */
  titulos: Record<string, string>;
  aoFechar: () => void;
}) {
  const imagens = useMemo(() => ultimasImagens(renders), [renders]);
  const todas = Object.keys(imagens).sort((a, b) => (a === "base" ? -1 : b === "base" ? 1 : a.localeCompare(b)));
  const [escolhidas, setEscolhidas] = useState<string[]>(todas.slice(0, 4));
  const comuns = vistasEmComum(imagens, escolhidas);
  const [vista, setVista] = useState(comuns.includes("perspectiva") ? "perspectiva" : (comuns[0] ?? "perspectiva"));
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [aoFechar]);
  const colunas = escolhidas.length <= 1 ? 1 : escolhidas.length <= 4 ? 2 : 3;

  return (
    <div role="dialog" aria-label="Comparar variações" className="fixed inset-0 z-50 flex flex-col bg-superficie-2">
      <div className="flex flex-wrap items-center gap-2 border-b border-linha bg-superficie px-4 py-2 text-sm">
        <h2 className="font-semibold">Comparar variações</h2>
        {todas.map((v) => (
          <label key={v} className="flex items-center gap-1 rounded-md border border-linha-forte px-2 py-0.5">
            <input
              type="checkbox"
              checked={escolhidas.includes(v)}
              onChange={() => setEscolhidas((e) => (e.includes(v) ? e.filter((x) => x !== v) : [...e, v]))}
            />
            {nomes[v] ?? v}
          </label>
        ))}
        <select className="rounded-md border" value={vista} onChange={(e) => setVista(e.target.value)} aria-label="vista">
          {(comuns.length ? comuns : [vista]).map((v) => (
            <option key={v} value={v}>
              {titulos[v] ?? v}
            </option>
          ))}
        </select>
        <button className="ml-auto rounded-md border border-linha-forte px-3 py-0.5 hover:bg-superficie-2" onClick={aoFechar}>
          fechar (Esc)
        </button>
      </div>
      <div className="grid min-h-0 flex-1 gap-3 overflow-auto p-4" style={{ gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))` }}>
        {escolhidas.map((v) => {
          const q = imagens[v]?.[vista];
          return (
            <figure key={v} className="min-w-0">
              <figcaption className="mb-1 flex justify-between text-sm">
                <b>{nomes[v] ?? v}</b>
                {q && (
                  <span className="text-xs text-tinta-suave">
                    {q.qualidade} · versão {q.versao}
                  </span>
                )}
              </figcaption>
              {q ? (
                <img src={URL_API + q.url} alt={`${nomes[v] ?? v}: ${titulos[vista] ?? vista}`} className="w-full rounded-md border bg-superficie" />
              ) : (
                <p className="rounded-md border border-dashed border-linha-forte p-6 text-center text-sm text-tinta-suave">
                  Sem imagem "{titulos[vista] ?? vista}" desta variação: peça um render dela
                </p>
              )}
            </figure>
          );
        })}
      </div>
    </div>
  );
}
