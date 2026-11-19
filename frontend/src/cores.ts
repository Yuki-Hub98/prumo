/**
 * Cores: a API guarda ``#rrggbb``; a tela também mostra e aceita RGB (0–255).
 */
export type Rgb = [number, number, number];

export function hexParaRgb(hex: string): Rgb {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as Rgb;
}

export function rgbParaHex([r, g, b]: Rgb): string {
  return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
}

export function rgbTexto(hex: string): string {
  return hexParaRgb(hex).join(", ");
}

/**
 * Lê o que a pessoa digitou ou colou: ``255, 120, 80`` · ``255 120 80`` ·
 * ``rgb(255, 120, 80)`` · ``#ff7850`` · ``#f75``. Devolve ``#rrggbb`` ou ``null``.
 */
export function lerCor(texto: string): string | null {
  const t = texto.trim().toLowerCase();
  const hex = t.match(/^#?([0-9a-f]{3}|[0-9a-f]{6})$/);
  if (hex && (t.startsWith("#") || /[a-f]/.test(hex[1]) || hex[1].length === 6)) {
    const h = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join("") : hex[1];
    return `#${h}`;
  }
  const nums = t.replace(/^rgb\s*\(|\)$/g, "").split(/[\s,;]+/).filter(Boolean);
  if (nums.length !== 3 || !nums.every((n) => /^\d{1,3}$/.test(n))) return null;
  const rgb = nums.map(Number);
  if (rgb.some((v) => v > 255)) return null;
  return rgbParaHex(rgb as Rgb);
}
