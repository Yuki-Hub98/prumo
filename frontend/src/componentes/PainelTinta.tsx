import { URL_API } from "../api/cliente";
import { useTinta } from "../dados";

const NOME = { latex: "Látex", esmalte: "Esmalte" } as const;
const ONDE = { latex: "paredes e teto", esmalte: "portas e rodapé" } as const;

const litros = (l: number, casas = 1) => `${l.toLocaleString("pt-BR", { maximumFractionDigits: casas })} L`;

/** O que comprar de tinta no pavimento, com a variação escolhida em cada cômodo. */
export function PainelTinta({
  codigo,
  pavimento,
  escolhas,
}: {
  codigo: string;
  pavimento: string;
  /** cômodo → variação ativa (base = cor padrão) */
  escolhas: Record<string, string>;
}) {
  const tinta = useTinta(codigo, pavimento, escolhas);
  const query = Object.entries(escolhas)
    .filter(([, v]) => v !== "base")
    .map(([c, v]) => `variacao=${encodeURIComponent(`${c}:${v}`)}`)
    .join("&");
  const planilha = `${URL_API}/projetos/${encodeURIComponent(codigo)}/pavimentos/${encodeURIComponent(pavimento)}/tinta.xlsx${query ? `?${query}` : ""}`;
  const t = tinta.data;
  // parâmetros usados no cálculo (padrões ou os do regras.toml)
  const par = (t?.parametros ?? {}) as {
    demaos_latex: number;
    rendimento_latex: number;
    demaos_esmalte: number;
    rendimento_esmalte: number;
    perda: number;
  };
  return (
    <section className="border-b border-linha p-3">
      <h2 className="mb-1 text-xs font-semibold uppercase tracking-wide text-tinta-suave">Tinta do pavimento</h2>
      <p className="mb-2 text-xs text-tinta-suave">Com a variação escolhida em cada cômodo; paredes de destaque contam à parte.</p>
      {tinta.error && <p className="text-sm text-erro">{tinta.error.message}</p>}
      {t && (
        <>
          {t.preliminar && (
            <p className="mb-2 rounded-md bg-aviso-fundo px-2 py-1 text-xs text-aviso">
              Há medidas "chute": confira antes de comprar.
            </p>
          )}
          <table className="w-full text-sm">
            <tbody>
              {t.grupos.map((g) => (
                <tr key={`${g.tinta}-${g.cor}`} className="border-t border-linha align-top">
                  <td className="py-1 pr-2">
                    <span
                      className="inline-block h-4 w-6 rounded-md border border-linha-forte align-middle"
                      style={{ background: g.cor ?? "repeating-linear-gradient(45deg,var(--superficie-2),var(--superficie-2) 3px,var(--linha) 3px,var(--linha) 6px)" }}
                      title={g.cor ?? "Cor padrão"}
                    />
                  </td>
                  <td className="py-1">
                    <b>{NOME[g.tinta]}</b> <span className="text-xs text-tinta-suave">{ONDE[g.tinta]}</span>
                    <div className="text-xs text-tinta-suave">
                      {g.cor?.toUpperCase() ?? "Cor padrão"} · {g.area_m2.toLocaleString("pt-BR")} m² · {litros(g.litros)}
                    </div>
                  </td>
                  <td className="py-1 text-right text-xs">
                    {g.latas.map((l) => (
                      <div key={l.litros} className="whitespace-nowrap">
                        {l.quantidade} × {litros(l.litros, 3)}
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-tinta-suave">
            {par.demaos_latex} demãos de látex a {par.rendimento_latex} m²/L, {par.demaos_esmalte} de esmalte a{" "}
            {par.rendimento_esmalte} m²/L, {Math.round(par.perda * 100)}% de perda (ajustável em [tinta] do regras.toml).
          </p>
          <a href={planilha} className="mt-1 inline-block text-sm link">
            Baixar planilha (.xlsx)
          </a>
        </>
      )}
    </section>
  );
}
