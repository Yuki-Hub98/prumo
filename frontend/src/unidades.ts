/**
 * Conversão entre a unidade que a pessoa escolheu e os milímetros da API.
 * A API e o banco são sempre mm inteiros; a tela só converte na entrada e na saída.
 */
export type Unidade = "mm" | "cm" | "m";

const FATOR: Record<Unidade, number> = { mm: 1, cm: 10, m: 1000 };
const CASAS: Record<Unidade, number> = { mm: 0, cm: 1, m: 3 };

/** mm → texto na unidade escolhida (vírgula decimal, sem zeros sobrando). */
export function formatar(mm: number, unidade: Unidade, comSufixo = true): string {
  const valor = mm / FATOR[unidade];
  const texto = String(Number(valor.toFixed(CASAS[unidade]))).replace(".", ",");
  return comSufixo ? `${texto} ${unidade}` : texto;
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
  { valor: "trena", rotulo: "Medi", dica: "medido com trena no local" },
  { valor: "projeto", rotulo: "Quero assim", dica: "valor decidido no projeto" },
  { valor: "estimada", rotulo: "Chute", dica: "estimado; o desenho sai PRELIMINAR" },
];
