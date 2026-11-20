/** Andar novo: id a partir do nome e a cota do piso sugerida. */

type Pav = { id: string; cota_piso: { valor: number }; pe_direito: { valor: number } };

/** Laje entre um andar e o de cima (estimativa, a pessoa ajusta). */
export const LAJE_MM = 150;

/** "Superior 2º" → ``superior-2``; repete com ``-2``, ``-3``... se já existir. */
export function idDoAndar(nome: string, existentes: string[]): string {
  const base =
    nome
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "andar";
  let id = base;
  for (let n = 2; existentes.includes(id); n++) id = `${base}-${n}`;
  return id;
}

/** Cota do piso do andar novo: em cima do mais alto (piso + pé-direito + laje). */
export function cotaSugerida(pavimentos: Pav[]): number {
  if (!pavimentos.length) return 0;
  const topo = pavimentos.reduce((a, b) => (a.cota_piso.valor >= b.cota_piso.valor ? a : b));
  return topo.cota_piso.valor + topo.pe_direito.valor + LAJE_MM;
}

/** Nome sugerido: "Superior", depois "Andar 3", "Andar 4"... */
export function nomeSugerido(quantos: number): string {
  return quantos <= 1 ? "Superior" : `Andar ${quantos + 1}`;
}
