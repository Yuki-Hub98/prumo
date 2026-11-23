import { describe, expect, it } from "vitest";
import { caixaPuxada, cenaDoMovel, medidaPuxada, pontoDaAlca, tNoEixo } from "./detalhe";
import type { Cena3D } from "./montarCena";

const m = { largura: 1380, profundidade: 1880, altura: 550, base: 0 };

describe("editar em detalhe", () => {
  it("separa só as peças do móvel", () => {
    const caixa = (nome: string, movel?: string) =>
      ({ nome, material: "x", centro: [0, 0, 0], tamanho: [1, 1, 1], rotacao: 0, extras: movel ? { movel } : null }) as never;
    const cena = { versao: 1, prismas: [], caixas: [caixa("cama-base", "cama"), caixa("parede"), caixa("tv-tela", "tv")], materiais: {}, aviso: null } as unknown as Cena3D;
    expect(cenaDoMovel(cena, "cama").caixas.map((c) => c.nome)).toEqual(["cama-base"]);
  });

  it("alças no meio da face que puxam (frente em −z), acompanhando a caixa puxada", () => {
    const c = caixaPuxada(m, m);
    const [x, y, z] = pontoDaAlca("largura", c);
    expect([x, y, z].map((v) => +v.toFixed(4))).toEqual([0.69, 0.275, 0]);
    expect(pontoDaAlca("profundidade", c)[2]).toBeCloseTo(-0.94);
    expect(pontoDaAlca("altura", caixaPuxada({ ...m, base: 1000 }, { ...m, base: 1000 }))[1]).toBeCloseTo(1.55);
    expect(pontoDaAlca("largura", caixaPuxada(m, { ...m, largura: 1500 }))[0]).toBeCloseTo(0.81);
  });

  it("ponto do eixo mais perto do raio do mouse", () => {
    // eixo x a partir da origem; raio descendo na vertical em x = 0,3
    expect(tNoEixo([0, 0, 0], [1, 0, 0], [0.3, 5, 0], [0, -1, 0])).toBeCloseTo(0.3);
    expect(tNoEixo([0, 0, 0], [1, 0, 0], [0, 0, 0], [1, 0, 0])).toBeNull(); // paralelo
  });

  it("medida puxada em passos de 1 cm, nunca abaixo de 10 cm", () => {
    expect(medidaPuxada("largura", m, 0.123)).toBe(1500); // 1380 + 123 = 1503 → 1500
    expect(medidaPuxada("altura", m, -0.0144)).toBe(540);
    expect(medidaPuxada("profundidade", m, -5)).toBe(100);
  });

  it("caixa fantasma cresce só para o lado da alça", () => {
    const c = caixaPuxada(m, { ...m, largura: 1500, profundidade: 2000 });
    expect(c.min[0]).toBeCloseTo(-0.69); // lado oposto parado
    expect(c.max[0]).toBeCloseTo(0.81);
    expect(c.max[2]).toBeCloseTo(0.94); // costas paradas
    expect(c.min[2]).toBeCloseTo(-1.06);
  });
});
