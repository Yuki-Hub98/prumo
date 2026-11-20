/**
 * Conversão entre a unidade que a pessoa escolheu e os milímetros da API.
 * A API e o banco são sempre mm inteiros; a tela só converte na entrada e na saída.
 */
export type Unidade = "mm" | "cm" | "m";

const FATOR: Record<Unidade, number> = { mm: 1, cm: 10, m: 1000 };
const CASAS: Record<Unidade, number> = { mm: 0, cm: 1, m: 3 };

/** Espaço fino entre milhares (identidade visual: "2 450 mm"). */
const MILHAR = "\u202f";

/** mm → número na unidade escolhida, vírgula decimal, sem zeros sobrando e sem milhar. */
function numero(mm: number, unidade: Unidade): string {
  return String(Number((mm / FATOR[unidade]).toFixed(CASAS[unidade]))).replace(".", ",");
}

/** mm → texto na unidade escolhida: "2 450 mm", "245 cm", "2,45 m".
 * Sem sufixo (para preencher um campo), sai sem o espaço de milhar: "2450". */
export function formatar(mm: number, unidade: Unidade, comSufixo = true): string {
  if (!comSufixo) return numero(mm, unidade);
  const [num, unid] = partes(mm, unidade);
  return `${num} ${unid}`;
}

/** Número (com espaço fino de milhar) e unidade separados, para estilos diferentes. */
export function partes(mm: number, unidade: Unidade): [string, Unidade] {
  const [int, dec] = numero(mm, unidade).split(",");
  const agrupado = int.replace(/\B(?=(\d{3})+(?!\d))/g, MILHAR);
  return [dec === undefined ? agrupado : `${agrupado},${dec}`, unidade];
}

/**
 * Texto digitado → mm inteiros. Aceita vírgula ou ponto. Devolve `null` se não for
 * um número ≥ 0. Arredonda ao mm (a unidade interna não tem decimais).
 */
export function paraMm(texto: string, unidade: Unidade): number | null {
  const limpo = texto.trim().replace(/\s/g, "").replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(limpo)) return null;
  return Math.round(Number(limpo) * FATOR[unidade]);
}

export type Origem = "trena" | "projeto" | "estimada";

/** Como a tela pergunta a origem (decisão do usuário: sempre perguntar). */
export const ORIGENS: { valor: Origem; rotulo: string; dica: string }[] = [
  { valor: "trena", rotulo: "Medi", dica: "Medido com trena no local" },
  { valor: "projeto", rotulo: "Quero assim", dica: "Valor decidido no projeto" },
  { valor: "estimada", rotulo: "Chute", dica: "Estimado; o desenho sai PRELIMINAR" },
];
