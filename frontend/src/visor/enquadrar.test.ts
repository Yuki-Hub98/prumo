import { describe, expect, it } from "vitest";
import { arestas, type Caixa, ehPiso, ehTeto, enquadrar } from "./enquadrar";

// quarto de 4,6 × 3,35 m (piso) com paredes de 15 cm, pé-direito 2,7 m
const piso: Caixa = { min: [0, -0.02, -3.35], max: [4.6, 0, 0] };
const modelo: Caixa = { min: [-0.15, -0.02, -3.5], max: [4.75, 2.72, 0.15] };

const visivel = (c: { normal: number[]; constante: number }, p: number[]) =>
  c.normal[0] * p[0] + c.normal[1] * p[1] + c.normal[2] * p[2] + c.constante >= 0;

describe("enquadrar", () => {
  it("de cima olha para baixo, sem corte", () => {
    const e = enquadrar("cima", modelo, piso);
    expect(e.corte).toBeNull();
    expect(e.posicao[1]).toBeGreaterThan(modelo.max[1]);
    expect(e.alvo[1]).toBe(0);
  });

  it("de frente corta a parede da frente e mantém o cômodo", () => {
    const e = enquadrar("frente", modelo, piso);
    expect(e.posicao[2]).toBeGreaterThan(piso.max[2]); // câmera fora, do lado de baixo da planta
    const c = e.corte!;
    expect(visivel(c, [2, 1, 0.07])).toBe(false); // meio da parede da frente
    expect(visivel(c, [2, 1, 0])).toBe(false); // face de dentro dela também
    expect(visivel(c, [2, 1, -0.3])).toBe(true); // móvel encostado
    expect(visivel(c, [2, 1, -3.4])).toBe(true); // parede do fundo continua
  });

  it("cada lado corta a parede do seu lado", () => {
    const meioDaParede = { fundo: [2, 1, -3.42], esquerda: [-0.07, 1, -1], direita: [4.67, 1, -1] };
    for (const [vista, p] of Object.entries(meioDaParede)) {
      const c = enquadrar(vista as "fundo", modelo, piso).corte!;
      expect(visivel(c, p)).toBe(false);
      expect(visivel(c, [2.3, 1, -1.6])).toBe(true); // centro do cômodo
    }
  });

  it("reconhece o teto pelos extras ou pelo nome", () => {
    expect(ehTeto("luminaria-l1", { oculto_em: "superior" })).toBe(true);
    expect(ehTeto("teto", undefined)).toBe(true);
    expect(ehTeto("cama", undefined)).toBe(false);
    expect(ehTeto("teto", { oculto_em: "porta" })).toBe(false);
  });
});

describe("ehPiso", () => {
  it("acha o piso do cômodo e os do pavimento", () => {
    expect(ehPiso("piso")).toBe(true);
    expect(ehPiso("piso-quarto")).toBe(true);
    expect(ehPiso("teto-quarto")).toBe(false);
    expect(ehPiso("pisoteado")).toBe(false);
  });
});

describe("arestas", () => {
  it("12 arestas da caixa, cada uma mudando um eixo só", () => {
    const pares = arestas({ min: [0, 0, 0], max: [2, 1, 3] });
    expect(pares).toHaveLength(24);
    for (let i = 0; i < 24; i += 2) {
      const mudam = [0, 1, 2].filter((k) => pares[i][k] !== pares[i + 1][k]);
      expect(mudam).toHaveLength(1);
    }
    const chaves = new Set(pares.map((p) => p.join()));
    expect(chaves.size).toBe(8); // os 8 cantos
  });
});
