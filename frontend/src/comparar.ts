/** Comparador de variações: a imagem pronta mais recente de cada variação, por vista. */

import type { InfoRender } from "./api/cliente";
import { vistaDaImagem } from "./vistas";

export type Quadro = { url: string; qualidade: string; versao: number; criadoEm: string };

/** variação → vista → imagem mais recente pronta (a lista da API vem da mais nova). */
export function ultimasImagens(renders: InfoRender[]): Record<string, Record<string, Quadro>> {
  const saida: Record<string, Record<string, Quadro>> = {};
  for (const r of renders) {
    if (r.status !== "pronto") continue;
    const porVista = (saida[r.variacao] ??= {});
    for (const url of r.imagens_url) {
      const vista = vistaDaImagem(url);
      porVista[vista] ??= { url, qualidade: r.qualidade, versao: r.versao_projeto, criadoEm: r.criado_em };
    }
  }
  return saida;
}

/** Vistas que pelo menos duas das variações escolhidas têm (dá para comparar). */
export function vistasEmComum(imagens: Record<string, Record<string, Quadro>>, variacoes: string[]): string[] {
  const conta = new Map<string, number>();
  for (const v of variacoes) for (const vista of Object.keys(imagens[v] ?? {})) conta.set(vista, (conta.get(vista) ?? 0) + 1);
  return [...conta].filter(([, n]) => n >= 2).map(([vista]) => vista);
}
