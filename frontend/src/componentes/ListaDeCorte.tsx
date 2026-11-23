import { useState } from "react";
import { URL_API, type Esquemas } from "../api/cliente";
import { formatar, type Unidade } from "../unidades";

type Vista = Esquemas["PlanejadoTela"];
type Peca = Esquemas["PecaTela"];

/** Endereço do desenho (``pdf``/``dxf``) ou da lista de corte (``xlsx``) do móvel na API. */
export function urlPlanejado(codigo: string, comodo: string, id: string, formato: "pdf" | "dxf" | "xlsx"): string {
  const c = encodeURIComponent;
  return `${URL_API}/projetos/${c(codigo)}/comodos/${c(comodo)}/moveis/${c(id)}/planejado.${formato}`;
}

/** "2C2L" → "2 compridos e 2 curtos"; vazio → "—". */
export function textoFita(fita: string): string {
  if (!fita) return "—";
  const partes: string[] = [];
  for (let i = 0; i + 1 < fita.length; i += 2) {
    const n = Number(fita[i]);
    const lado = fita[i + 1] === "C" ? (n > 1 ? "compridos" : "comprido") : n > 1 ? "curtos" : "curto";
    partes.push(`${n} ${lado}`);
  }
  return partes.join(" e ");
}

/** " (11,5 m de fita)" com vírgula; sem fita, nada. */
export function textoMetrosFita(metros: number): string {
  return metros > 0 ? ` (${metros.toLocaleString("pt-BR")} m de fita)` : "";
}

/** Peças agrupadas por material/espessura (a ordem em que o marceneiro corta). */
export function porMaterial(lista: Peca[]): [string, Peca[]][] {
  const grupos = new Map<string, Peca[]>();
  for (const p of lista) {
    const chave = `${p.material} ${p.espessura} mm`;
    grupos.set(chave, [...(grupos.get(chave) ?? []), p]);
  }
  return [...grupos.entries()];
}

/** Lista de corte na tela (peças, chapas, ferragens) e os arquivos para o marceneiro. */
export function ListaDeCorte({
  codigo,
  comodo,
  id,
  vista,
  unidade,
}: {
  codigo: string;
  comodo: string;
  id: string;
  vista: Vista;
  unidade: Unidade;
}) {
  const [aberta, setAberta] = useState(false);
  const lista = vista.lista ?? [];
  const med = (mm: number) => formatar(Math.round(mm), unidade, false);
  return (
    <div className="mt-2 border-t border-linha pt-2 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-tinta-suave">Para o marceneiro</span>
        <a href={urlPlanejado(codigo, comodo, id, "pdf")} target="_blank" rel="noreferrer" className="link text-xs">
          Ver desenho (PDF)
        </a>
        <a href={urlPlanejado(codigo, comodo, id, "dxf")} className="link text-xs">
          DXF
        </a>
        <a href={urlPlanejado(codigo, comodo, id, "xlsx")} className="link text-xs">
          Lista de corte (.xlsx)
        </a>
      </div>
      <p className="mt-1 text-xs text-tinta-suave">
        {vista.pecas} peças ·{" "}
        {vista.chapas
          .map((ch) => `${ch.chapas} chapa${ch.chapas > 1 ? "s" : ""} de ${ch.material} ${ch.espessura} mm${textoMetrosFita(ch.fita_metros)}`)
          .join(" · ")}
      </p>
      <button type="button" className="mt-1 text-xs link" onClick={() => setAberta(!aberta)}>
        {aberta ? "Esconder a lista de corte" : "Ver a lista de corte"}
      </button>
      {aberta && (
        <div className="mt-1 space-y-2">
          {porMaterial(lista).map(([material, pecas]) => (
            <div key={material}>
              <p className="text-xs font-semibold text-tinta">{material}</p>
              <table className="w-full text-xs">
                <thead className="text-tinta-suave">
                  <tr>
                    <th className="text-left font-normal">Peça</th>
                    <th className="text-right font-normal">Qtd</th>
                    <th className="text-right font-normal">Compr. × larg. ({unidade})</th>
                    <th className="text-right font-normal">Fita</th>
                  </tr>
                </thead>
                <tbody>
                  {pecas.map((p, i) => (
                    <tr key={i} className="border-t border-linha" title={p.obs || undefined}>
                      <td className="py-0.5 pr-1">{p.nome}</td>
                      <td className="text-right tabular-nums">{p.quantidade}</td>
                      <td className="text-right tabular-nums">
                        {med(p.comprimento)} × {med(p.largura)}
                      </td>
                      <td className="pl-1 text-right text-tinta-suave">{textoFita(p.fita ?? "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          {vista.ferragens.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-tinta">Ferragens</p>
              <ul className="text-xs">
                {vista.ferragens.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-tinta-suave">
            Chapas por área com 15 % de perda (sem plano de corte). Passe o mouse numa peça para ver a observação.
          </p>
        </div>
      )}
    </div>
  );
}
