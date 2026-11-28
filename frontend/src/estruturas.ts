/** Aba Estruturas: pilares, vigas e lajes do andar (o que se manda para a API).
 *
 * Tamanho que ninguém mediu entra como chute ("estimada") com a obs dizendo de onde veio;
 * a pessoa ajusta depois (Medi / Quero assim / Chute).
 */

import type { Esquemas } from "./api/cliente";

export type Pilar = Esquemas["Pilar"];
export type Viga = Esquemas["Viga"];
export type Laje = Esquemas["Laje"];
export type Escada = Esquemas["Escada"];
export type Elemento = Pilar | Viga | Laje | Escada;
type Pt = [number, number];

const chute = (valor: number, obs: string) => ({ valor, origem: "estimada" as const, obs: `estimada: ${obs}` });

export const NOMES: Record<Elemento["tipo"], string> = { laje: "Laje", escada: "Escada", viga: "Viga", pilar: "Pilar" };
export const FORMAS: Record<NonNullable<Escada["forma"]>, string> = {
  reta: "Reta",
  L: "Em L (com patamar)",
  U: "Em U (com patamar)",
  caracol: "Caracol / leque",
};
export const SISTEMAS: Record<NonNullable<Laje["sistema"]>, string> = {
  pre_moldada: "Pré-moldada (vigotas e lajotas/EPS)",
  macica: "Maciça (concreto no local)",
};

export function novoPilar(id: string, centro: Pt): Pilar {
  return {
    id,
    tipo: "pilar",
    centro: [Math.round(centro[0]), Math.round(centro[1])],
    largura: chute(200, "pilar comum de 20 × 20 cm"),
    profundidade: chute(200, "pilar comum de 20 × 20 cm"),
  };
}

/** Viga em cima de uma parede: o eixo dela, da largura da parede. */
export function novaViga(id: string, parede: { eixo: Pt[] | [Pt, Pt]; espessura: number }): Viga {
  const [a, b] = parede.eixo;
  return {
    id,
    tipo: "viga",
    inicio: [a[0], a[1]],
    fim: [b[0], b[1]],
    largura: chute(parede.espessura, "da largura da parede"),
    altura: chute(300, "viga comum desce 30 cm da laje"),
  };
}

export function novaLaje(id: string): Laje {
  return { id, tipo: "laje", espessura: chute(120, "laje pré-moldada H8 + capa de 4 cm"), sistema: "pre_moldada" };
}

/** Escada nova com o pé em ``inicio`` (no caracol, o centro), subindo para +x. */
export function novaEscada(id: string, inicio: Pt, forma: NonNullable<Escada["forma"]>): Escada {
  return {
    id,
    tipo: "escada",
    forma,
    inicio: [Math.round(inicio[0] / 10) * 10, Math.round(inicio[1] / 10) * 10],
    direcao: 0,
    largura: chute(900, "largura comum de escada de casa"),
  };
}

/** Gira a subida 90° no sentido anti-horário. */
export const girar90 = (direcao: number | undefined) => ((direcao ?? 0) + 90) % 360;

/** O que o painel mostra da conta da escada (vem da API, em ``EstruturaTela.escada``). */
export type ContaEscada = {
  espelhos: number;
  espelho: number;
  piso: number;
  blondel: number;
  desnivel: number;
  lances: number[];
  giro?: number | null;
};

/** Resumo da conta da escada para o painel ("16 espelhos de 17,6 cm..."). */
export function resumoEscada(c: ContaEscada, cm: (mm: number) => string): string[] {
  const linhas = [
    `${c.espelhos} espelhos de ${cm(c.espelho)} para vencer ${cm(c.desnivel)}`,
    `piso de ${cm(c.piso)} · 2 × espelho + piso = ${cm(c.blondel)}`,
  ];
  if (c.lances.length === 2) linhas.push(`${c.lances[0]} degraus + patamar + ${c.lances[1]} degraus`);
  if (c.giro != null) linhas.push(`gira ${c.giro}° subindo`);
  return linhas;
}

/** Retângulo (canto de baixo à esquerda, largura em x, comprimento em y) ↔ contorno do furo. */
export type Retangulo = { x: number; y: number; largura: number; comprimento: number };

export function furoParaRetangulo(pts: number[][]): Retangulo {
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, largura: Math.max(...xs) - x, comprimento: Math.max(...ys) - y };
}

export function retanguloParaFuro(r: Retangulo): Pt[] {
  const { x, y, largura: l, comprimento: c } = r;
  return [
    [x, y],
    [x + l, y],
    [x + l, y + c],
    [x, y + c],
  ];
}

/** Furo novo de ``largura`` × ``comprimento`` centrado em ``centro`` (na grade de 1 cm). */
export function furoNoCentro(centro: Pt, largura = 1000, comprimento = 2500): Pt[] {
  const r = (v: number) => Math.round(v / 10) * 10;
  return retanguloParaFuro({ x: r(centro[0] - largura / 2), y: r(centro[1] - comprimento / 2), largura, comprimento });
}

/** Lista na ordem da aba: lajes, escadas, vigas e pilares. */
export function ordenar<T extends { tipo: string; id: string }>(itens: T[]): T[] {
  const ordem = { laje: 0, escada: 1, viga: 2, pilar: 3 } as Record<string, number>;
  return [...itens].sort((a, b) => (ordem[a.tipo] ?? 9) - (ordem[b.tipo] ?? 9) || a.id.localeCompare(b.id));
}
