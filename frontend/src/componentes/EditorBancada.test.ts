import { describe, expect, it } from "vitest";
import { idLivre, moduloPronto, posicaoLivre, tipoDoModulo } from "./EditorBancada";
import { comprimentosBancada } from "./Paineis";

const med = (valor: number) => ({ valor, origem: "projeto" as const });

describe("bancada planejada", () => {
  it("módulos prontos voltam a ser reconhecidos pelo tipo", () => {
    for (const tipo of ["gaveteiro", "nicho", "armario"] as const) {
      const m = moduloPronto("x", tipo, "costas", 30, 450);
      expect(tipoDoModulo(m)).toBe(tipo);
      expect(m.distancia.origem).toBe("estimada");
    }
    expect(moduloPronto("x", "armario", "braco", 0, 800).portas).toBe("abrir");
  });

  it("id livre não repete o de outro módulo", () => {
    const mods = [moduloPronto("gaveteiro", "gaveteiro", "costas", 0, 450)];
    expect(idLivre("nicho", mods)).toBe("nicho");
    expect(idLivre("gaveteiro", mods)).toBe("gaveteiro2");
  });

  it("comprimento dos trechos segue o braço do L (padrão de 60 cm, como no core)", () => {
    expect(comprimentosBancada({ largura: med(1600), profundidade: med(1500) })).toEqual({ costas: 1600, braco: 900, faixa: 600 });
    expect(comprimentosBancada({ largura: med(1600), profundidade: med(800) }).braco).toBe(800 - 480);
    expect(comprimentosBancada({ largura: med(1600), profundidade: med(1500), braco: med(700) }).braco).toBe(800);
  });

  it("módulo novo vai para um lugar livre, fora do canto do L", () => {
    expect(posicaoLivre([], 1600, 450, null)).toBe(1120); // ponta direita
    expect(posicaoLivre([], 1600, 450, [1000, 1600])).toBe(30); // canto à direita: vai para a esquerda
    expect(posicaoLivre([[30, 480]], 1600, 450, [1000, 1600])).toBe(510); // ao lado do gaveteiro
    expect(posicaoLivre([[30, 480], [510, 960]], 1600, 450, [1000, 1600])).toBeNull();
  });
});
