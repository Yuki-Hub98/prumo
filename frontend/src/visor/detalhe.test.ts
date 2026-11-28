import { describe, expect, it } from "vitest";
import {
  aberturaPuxada,
  caixaAbertura,
  caixaPuxada,
  cenaDaParede,
  cenaDoMovel,
  eixoAlcaAbertura,
  medidaPuxada,
  pontoAlcaAbertura,
  pontoDaAlca,
  tNoEixo,
} from "./detalhe";
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

describe("editar em detalhe: porta e janela", () => {
  const j = { inicio: 800, largura: 1200, altura: 1000, peitoril: 1100 };

  it("isola o trecho da parede com as aberturas dela", () => {
    const p = (nome: string, extras: Record<string, string> | null) => ({ nome, extras }) as never;
    const cena = { versao: 1, prismas: [p("parede-p1-0", { parede: "p1" }), p("parede-p2-0", { parede: "p2" }), p("piso", null)], caixas: [p("caixilho-j1-b", { parede: "p1", abertura: "j1" })], materiais: {}, aviso: null } as unknown as Cena3D;
    const so = cenaDaParede(cena, "p1");
    expect([...so.prismas, ...so.caixas].map((x) => x.nome)).toEqual(["parede-p1-0", "caixilho-j1-b"]);
  });

  it("caixa do vão centrada no vão original, lado a em −z", () => {
    const c = caixaAbertura(j, j, 150);
    expect(c.min.map((v) => +v.toFixed(3))).toEqual([-0.6, 1.1, -0.075]);
    expect(c.max.map((v) => +v.toFixed(3))).toEqual([0.6, 2.1, 0.075]);
    expect(pontoAlcaAbertura("inicio", c, -1).map((v) => +v.toFixed(3))).toEqual([-0.6, 1.6, -0.075]);
    expect(pontoAlcaAbertura("peitoril", c, 1)[1]).toBeCloseTo(1.1);
    // depois de puxar o início 10 cm para fora, a caixa cresce para −x
    expect(caixaAbertura(j, { ...j, inicio: 700, largura: 1300 }, 150).min[0]).toBeCloseTo(-0.7);
  });

  it("puxar mantém a borda oposta parada, com limites", () => {
    expect(aberturaPuxada("fim", j, 0.203)).toEqual({ ...j, largura: 1400 });
    expect(aberturaPuxada("inicio", j, 0.1)).toEqual({ ...j, inicio: 700, largura: 1300 });
    expect(aberturaPuxada("inicio", j, 5)).toEqual({ ...j, inicio: 0, largura: 2000 }); // não passa do início da parede
    expect(aberturaPuxada("inicio", j, -5)).toEqual({ ...j, inicio: 1900, largura: 100 });
    expect(aberturaPuxada("altura", j, -5).altura).toBe(100);
    expect(aberturaPuxada("peitoril", j, 0.2)).toEqual({ ...j, peitoril: 900, altura: 1200 });
    expect(aberturaPuxada("peitoril", j, 5)).toEqual({ ...j, peitoril: 0, altura: 2100 }); // não passa do piso
    expect(eixoAlcaAbertura("inicio")).toEqual([-1, 0, 0]);
  });
});
