/** Escolha das vistas do render: padrão, memória por cômodo e nome de cada imagem. */

export const VISTAS_PADRAO = ["perspectiva", "superior"];

/** Mantém só as vistas que ainda existem no cômodo, na ordem em que a API as oferece;
 * se nada sobrar, volta ao padrão (ou à primeira disponível). */
export function vistasValidas(escolhidas: string[] | null, disponiveis: string[]): string[] {
  const ok = disponiveis.filter((v) => (escolhidas ?? VISTAS_PADRAO).includes(v));
  if (ok.length) return ok;
  const padrao = disponiveis.filter((v) => VISTAS_PADRAO.includes(v));
  return padrao.length ? padrao : disponiveis.slice(0, 1);
}

/** Liga/desliga uma vista, sem deixar a escolha vazia. */
export function alternar(escolhidas: string[], vista: string, disponiveis: string[]): string[] {
  const nova = escolhidas.includes(vista) ? escolhidas.filter((v) => v !== vista) : [...escolhidas, vista];
  return nova.length ? disponiveis.filter((v) => nova.includes(v)) : escolhidas;
}

/** ``/renders/7/imagens/render-cama.png`` → ``cama``. */
export function vistaDaImagem(url: string): string {
  const nome = url.split("/").pop() ?? "";
  return nome.replace(/^render-/, "").replace(/\.png$/, "");
}

const CHAVE = (codigo: string, comodo: string) => `vistas:${codigo}:${comodo}`;

export function lembrar(codigo: string, comodo: string): string[] | null {
  try {
    const v = JSON.parse(localStorage.getItem(CHAVE(codigo, comodo)) ?? "null");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : null;
  } catch {
    return null;
  }
}

export function guardar(codigo: string, comodo: string, vistas: string[]): void {
  try {
    localStorage.setItem(CHAVE(codigo, comodo), JSON.stringify(vistas));
  } catch {
    /* sem armazenamento: só não lembra */
  }
}
