/** Primeira letra maiúscula (rótulos, botões e mensagens que vêm da API em minúscula). */
export function maiuscula(s: string): string {
  return s ? s[0].toLocaleUpperCase("pt-BR") + s.slice(1) : s;
}
