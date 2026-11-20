/** Mudar as cores de uma variação: uma coisa (piso, uma parede, um móvel) ou várias de uma vez. */

import type { Cores } from "./api/cliente";

/** O que se pinta: ``parede`` (geral), ``piso``, ``teto``, ``rodape``, ``p:<parede>``,
 * ``m:<móvel>`` (o corpo) ou ``q:<móvel>:<parte>`` (portas, gavetas, travesseiros...). */
export type Chave = "parede" | "piso" | "teto" | "rodape" | `p:${string}` | `m:${string}` | `q:${string}:${string}`;

/** ``q:gr-1:portas`` → ``["gr-1", "portas"]`` (ids não têm ``:``). */
const daParte = (chave: string): [string, string] => {
  const [, movel, parte] = chave.split(":");
  return [movel, parte];
};

/** Cópia das cores com ``valor`` em cada chave (``null`` volta ao padrão). Não muda ``cores``. */
export function aplicar(cores: Cores, chaves: Iterable<Chave>, valor: string | null): Cores {
  const novo: Cores = {
    ...cores,
    paredes: { ...cores.paredes },
    moveis: { ...cores.moveis },
    pecas: Object.fromEntries(Object.entries(cores.pecas ?? {}).map(([k, v]) => [k, { ...v }])),
  };
  const por = (o: Record<string, string>, k: string) => {
    if (valor === null) delete o[k];
    else o[k] = valor;
  };
  for (const chave of chaves) {
    if (chave.startsWith("p:")) por(novo.paredes!, chave.slice(2));
    else if (chave.startsWith("m:")) por(novo.moveis!, chave.slice(2));
    else if (chave.startsWith("q:")) {
      const [movel, parte] = daParte(chave);
      const pecas = novo.pecas!;
      pecas[movel] = { ...pecas[movel] };
      por(pecas[movel], parte);
      if (Object.keys(pecas[movel]).length === 0) delete pecas[movel];
    }
    else novo[chave as "parede" | "piso" | "teto" | "rodape"] = valor;
  }
  return novo;
}

/** Cor definida para a chave (``undefined`` = padrão). Móvel também pela cor do tipo. */
export function valorDe(cores: Cores, chave: Chave, tipos: Record<string, string> = {}): string | undefined {
  if (chave.startsWith("p:")) return cores.paredes?.[chave.slice(2)] ?? undefined;
  if (chave.startsWith("q:")) {
    const [movel, parte] = daParte(chave);
    return cores.pecas?.[movel]?.[parte] ?? cores.pecas?.[tipos[movel]]?.[parte] ?? undefined;
  }
  if (chave.startsWith("m:")) {
    const id = chave.slice(2);
    return cores.moveis?.[id] ?? cores.moveis?.[tipos[id]] ?? undefined;
  }
  return cores[chave as "parede" | "piso" | "teto" | "rodape"] ?? undefined;
}
