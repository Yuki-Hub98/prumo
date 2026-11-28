/** Desenho das cotas na planta: onde fica a linha, os risquinhos e o texto (em mm). */

type Pt = [number, number];
export type Cota = { de: number[]; ate: number[]; lado: number[]; fileira: number; tipo: string; valor: number; comodo?: string | null; origem?: string };

/** Afastamento (mm) da linha medida, por fileira: por dentro do cômodo fica perto da parede;
 * as gerais vão por fora, além da parede. */
export function afastamento(c: Cota): number {
  const porFora = c.tipo === "eixo" || c.tipo === "geral";
  return porFora ? 450 + c.fileira * 380 : 220 + c.fileira * 230;
}

/** Quais aparecem: gerais e a face de todo cômodo; a cadeia com as aberturas, só no cômodo
 * escolhido (no resto, a face vai para a fileira de dentro, sem o vão da cadeia). */
export function visiveis(cotas: Cota[], escolhido: string | null): Cota[] {
  return cotas
    .filter((c) => c.tipo !== "trecho" || c.comodo === escolhido)
    .map((c) => (c.tipo === "comodo" && c.comodo !== escolhido ? { ...c, fileira: 0 } : c));
}

/** Cor pela origem da medida (identidade visual): medi, quero assim, chute. */
export function corDaOrigem(origem: string | undefined): string {
  return origem === "trena" ? "var(--medido)" : origem === "estimada" ? "var(--chute)" : "var(--projeto)";
}

/** Geometria pronta (mm, y do pavimento para cima): linha de cota, linhas de chamada,
 * risquinhos a 45° nas pontas e o meio/ângulo do texto (sempre de pé, em graus do SVG). */
export function desenho(c: Cota) {
  const d = afastamento(c);
  const [lx, ly] = c.lado;
  const a: Pt = [c.de[0] + lx * d, c.de[1] + ly * d];
  const b: Pt = [c.ate[0] + lx * d, c.ate[1] + ly * d];
  const tam = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  const u: Pt = [(b[0] - a[0]) / tam, (b[1] - a[1]) / tam];
  const r = 60; // meia perna do risquinho
  const risco = (p: Pt): [Pt, Pt] => {
    const w: Pt = [(u[0] + lx) * Math.SQRT1_2, (u[1] + ly) * Math.SQRT1_2];
    return [
      [p[0] - w[0] * r, p[1] - w[1] * r],
      [p[0] + w[0] * r, p[1] + w[1] * r],
    ];
  };
  const chamada = (de: number[], p: Pt): [Pt, Pt] => [
    [de[0] + lx * 40, de[1] + ly * 40],
    [p[0] + lx * 60, p[1] + ly * 60],
  ];
  // ângulo na tela (y do SVG para baixo); vira 180° para nunca ler de cabeça para baixo
  let ang = (Math.atan2(-u[1], u[0]) * 180) / Math.PI;
  if (ang >= 90) ang -= 180;
  if (ang < -90) ang += 180;
  const meio: Pt = [(a[0] + b[0]) / 2 + lx * 70, (a[1] + b[1]) / 2 + ly * 70];
  return { a, b, riscos: [risco(a), risco(b)], chamadas: [chamada(c.de, a), chamada(c.ate, b)], meio, ang };
}
