/** Tema claro/escuro da tela. A escolha fica neste navegador (``localStorage``); sem
 * escolha, segue o sistema. Os tokens de cor estão em ``index.css`` (``[data-tema]``). */

export type Tema = "claro" | "escuro";

const CHAVE = "prumo-tema";

export function temaSalvo(): Tema | null {
  try {
    const t = localStorage.getItem(CHAVE);
    return t === "claro" || t === "escuro" ? t : null;
  } catch {
    return null;
  }
}

export function temaDoSistema(): Tema {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
}

export function temaAtual(): Tema {
  return temaSalvo() ?? temaDoSistema();
}

/** Aplica no ``<html>`` e (se pedido) guarda a escolha. */
export function aplicarTema(tema: Tema, guardar = false): void {
  document.documentElement.dataset.tema = tema;
  document.documentElement.style.colorScheme = tema === "escuro" ? "dark" : "light";
  if (guardar) {
    try {
      localStorage.setItem(CHAVE, tema);
    } catch {
      /* navegador sem localStorage: vale só nesta aba */
    }
  }
}
