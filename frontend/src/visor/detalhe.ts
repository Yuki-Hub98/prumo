/** "Editar em detalhe": o móvel sozinho no 3D, no referencial dele, com alças para puxar.
 *
 * Referencial do detalhe (metros, three): centro do móvel na origem do piso, sem o giro da
 * planta. x = x local do móvel (+x é o lado "direita" do redimensionar), y para cima e
 * z = −y local: a frente do móvel (+y local) fica em −z.
 */

import type { Cena3D } from "./montarCena";

export type Alca = "largura" | "profundidade" | "altura";

type V3 = [number, number, number];

/** Medidas do móvel em mm (``base`` = elevação: o fundo fica parado ao puxar a altura). */
export type Medidas = { largura: number; profundidade: number; altura: number; base: number };

const M = 0.001;
/** Passo do arrastar: 1 cm, como na planta. */
export const PASSO_MM = 10;
/** Menor medida aceita (a mesma do redimensionar da API). */
export const MINIMO_MM = 100;

/** Só as peças do móvel ``id`` (prismas e caixas marcados com ``movel``). */
export function cenaDoMovel(cena: Cena3D, id: string): Cena3D {
  const doMovel = (p: { extras?: Record<string, string> | null }) => p.extras?.movel === id;
  return { ...cena, prismas: cena.prismas.filter(doMovel), caixas: cena.caixas.filter(doMovel) };
}

/** Onde fica cada alça (m): no meio da face que ela puxa, na caixa atual do móvel. */
export function pontoDaAlca(alca: Alca, c: { min: V3; max: V3 }): V3 {
  const meio = (i: number) => (c.min[i] + c.max[i]) / 2;
  if (alca === "largura") return [c.max[0], meio(1), meio(2)];
  if (alca === "profundidade") return [meio(0), meio(1), c.min[2]];
  return [meio(0), c.max[1], meio(2)];
}

/** Eixo em que cada alça anda (unitário). */
export function eixoAlca(alca: Alca): [number, number, number] {
  return alca === "largura" ? [1, 0, 0] : alca === "profundidade" ? [0, 0, -1] : [0, 1, 0];
}

const sub = (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: V3, b: V3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

/**
 * Ponto do eixo (``origem + t · eixo``) mais perto do raio do mouse (``raio + s · direcao``):
 * devolve ``t`` em metros. Raio paralelo ao eixo: ``null`` (não dá para saber para onde puxou).
 */
export function tNoEixo(origem: V3, eixo: V3, raio: V3, direcao: V3): number | null {
  const w = sub(origem, raio);
  const a = dot(eixo, eixo);
  const b = dot(eixo, direcao);
  const c = dot(direcao, direcao);
  const d = dot(eixo, w);
  const e = dot(direcao, w);
  const den = a * c - b * b;
  if (Math.abs(den) < 1e-9) return null;
  return (b * e - c * d) / den;
}

/** Medida nova depois de a alça andar ``t`` metros pelo eixo (lado oposto parado), em
 * passos de 1 cm e nunca abaixo do mínimo. */
export function medidaPuxada(alca: Alca, inicial: Medidas, t: number): number {
  const antes = inicial[alca];
  const bruto = antes + t / M;
  return Math.max(MINIMO_MM, Math.round(bruto / PASSO_MM) * PASSO_MM);
}

/** Caixa (m) que o móvel ocupa com as medidas ``m``, do lado oposto das alças parado:
 * esquerda em x = −largura/2 do original, costas em z = +profundidade/2 e base no piso. */
export function caixaPuxada(original: Medidas, m: Medidas): { min: V3; max: V3 } {
  const x0 = -(original.largura / 2) * M;
  const z1 = (original.profundidade / 2) * M;
  return {
    min: [x0, m.base * M, z1 - m.profundidade * M],
    max: [x0 + m.largura * M, (m.base + m.altura) * M, z1],
  };
}
