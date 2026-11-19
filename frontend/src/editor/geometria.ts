/** Ajudas de desenho do editor (só tela: a regra de verdade fica no core). */
export type Pt = [number, number];

export const GRADE = 10; // mm
export const IMA = 150; // mm: distância para "grudar" num canto existente

/** Cantos (pontas de parede) únicos do pavimento. */
export function vertices(eixos: (readonly (readonly number[])[])[]): Pt[] {
  const vistos = new Map<string, Pt>();
  for (const eixo of eixos)
    for (const p of eixo) {
      const v: Pt = [p[0], p[1]];
      vistos.set(`${v[0]},${v[1]}`, v);
    }
  return [...vistos.values()];
}

/**
 * Ponto "encaixado": gruda num canto a menos de ``IMA``; senão arredonda na grade e,
 * se houver ponto de partida, alinha na horizontal/vertical quando está quase reto.
 */
export function encaixar(p: Pt, cantos: Pt[], partida?: Pt | null, ignorar?: Pt | null): Pt {
  let melhor: Pt | null = null;
  let dist = IMA;
  for (const c of cantos) {
    if (ignorar && c[0] === ignorar[0] && c[1] === ignorar[1]) continue;
    const d = Math.hypot(c[0] - p[0], c[1] - p[1]);
    if (d < dist) [melhor, dist] = [c, d];
  }
  if (melhor) return [melhor[0], melhor[1]];
  let [x, y] = [Math.round(p[0] / GRADE) * GRADE, Math.round(p[1] / GRADE) * GRADE];
  if (partida) {
    const [dx, dy] = [x - partida[0], y - partida[1]];
    if (Math.abs(dy) < Math.abs(dx) * 0.08) y = partida[1];
    else if (Math.abs(dx) < Math.abs(dy) * 0.08) x = partida[0];
  }
  return [x, y];
}

/** Primeiro ``<prefixo><n>`` livre (p1, p2...; porta-1...). */
export function proximoId(prefixo: string, usados: Iterable<string>): string {
  const s = new Set(usados);
  let n = 1;
  while (s.has(`${prefixo}${n}`)) n++;
  return `${prefixo}${n}`;
}

/** Texto → id válido (minúsculas, números, - e _). */
export function paraId(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
