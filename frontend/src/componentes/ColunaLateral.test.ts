import { describe, expect, it } from "vitest";
import { limitarLargura } from "./ColunaLateral";
import { posicaoJanela } from "./SeletorCor";

describe("limitarLargura", () => {
  it("fica entre 280 px e metade da janela", () => {
    expect(limitarLargura(400, 1600)).toBe(400);
    expect(limitarLargura(100, 1600)).toBe(280);
    expect(limitarLargura(1200, 1600)).toBe(800);
    expect(limitarLargura(500, 400)).toBe(280); // janela estreita: o mínimo vence
  });
});

describe("posicaoJanela", () => {
  const janela = { largura: 1400, altura: 900 };
  const tamanho = { largura: 224, altura: 300 };
  it("abre à esquerda do botão (coluna na borda direita)", () => {
    expect(posicaoJanela({ left: 1300, right: 1332, top: 400 }, janela, tamanho)).toEqual({ left: 1068, top: 360 });
  });
  it("não sai pela parte de baixo nem de cima", () => {
    expect(posicaoJanela({ left: 1300, right: 1332, top: 850 }, janela, tamanho).top).toBe(592);
    expect(posicaoJanela({ left: 1300, right: 1332, top: 10 }, janela, tamanho).top).toBe(8);
  });
  it("sem espaço à esquerda, abre à direita", () => {
    expect(posicaoJanela({ left: 100, right: 132, top: 400 }, janela, tamanho).left).toBe(140);
  });
});
