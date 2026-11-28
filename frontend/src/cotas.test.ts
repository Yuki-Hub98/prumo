import { describe, expect, it } from "vitest";
import { afastamento, corDaOrigem, desenho, visiveis } from "./cotas";

const face = { de: [0, 0], ate: [3000, 0], lado: [0, 1], fileira: 1, tipo: "comodo", valor: 3000, comodo: "quarto", origem: "trena" };
const trecho = { ...face, ate: [1000, 0], fileira: 0, tipo: "trecho", valor: 1000 };
const geral = { de: [0, 0], ate: [0, 4000], lado: [-1, 0], fileira: 1, tipo: "geral", valor: 4000, origem: "estimada" };

describe("cotas na planta", () => {
  it("cadeia só no cômodo escolhido; nos outros a face vem para perto", () => {
    expect(visiveis([face, trecho, geral], "quarto")).toHaveLength(3);
    const outros = visiveis([face, trecho, geral], null);
    expect(outros.map((c) => c.tipo)).toEqual(["comodo", "geral"]);
    expect(outros[0].fileira).toBe(0);
  });

  it("por dentro perto da parede; gerais por fora", () => {
    expect(afastamento({ ...face, fileira: 0 })).toBe(220);
    expect(afastamento(face)).toBe(450);
    expect(afastamento(geral)).toBe(830);
  });

  it("linha afastada para o lado e texto sempre de pé", () => {
    const d = desenho({ ...face, fileira: 0 });
    expect(d.a).toEqual([0, 220]);
    expect(d.b).toEqual([3000, 220]);
    expect(d.ang).toBeCloseTo(0);
    // de cima para baixo vira de baixo para cima (lê da esquerda)
    expect(desenho({ ...geral, de: [0, 4000], ate: [0, 0] }).ang).toBeCloseTo(-90);
    expect(desenho(geral).ang).toBeCloseTo(-90);
  });

  it("cor pela origem", () => {
    expect([corDaOrigem("trena"), corDaOrigem("projeto"), corDaOrigem("estimada"), corDaOrigem(undefined)]).toEqual([
      "var(--medido)",
      "var(--projeto)",
      "var(--chute)",
      "var(--projeto)",
    ]);
  });
});
