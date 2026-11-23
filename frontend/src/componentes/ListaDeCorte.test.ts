import { describe, expect, it } from "vitest";
import { porMaterial, textoFita, textoMetrosFita, urlPlanejado } from "./ListaDeCorte";

const peca = (nome: string, material: string, espessura: number) => ({
  nome, material, espessura, comprimento: 100, largura: 50, quantidade: 1, fita: "", obs: "",
});

describe("lista de corte na tela", () => {
  it("fita de borda por extenso", () => {
    expect(textoFita("2C2L")).toBe("2 compridos e 2 curtos");
    expect(textoFita("1C")).toBe("1 comprido");
    expect(textoFita("2C1L")).toBe("2 compridos e 1 curto");
    expect(textoFita("")).toBe("—");
    expect(textoMetrosFita(11.5)).toBe(" (11,5 m de fita)");
    expect(textoMetrosFita(0)).toBe("");
  });

  it("agrupa por material e espessura, na ordem em que aparecem", () => {
    const grupos = porMaterial([peca("Tampo", "MDF", 25), peca("Lateral", "MDF", 18), peca("Base", "MDF", 18)]);
    expect(grupos.map(([m, ps]) => [m, ps.length])).toEqual([["MDF 25 mm", 1], ["MDF 18 mm", 2]]);
  });

  it("endereço dos arquivos do móvel", () => {
    expect(urlPlanejado("casa", "quarto", "mesa", "pdf")).toMatch(/\/projetos\/casa\/comodos\/quarto\/moveis\/mesa\/planejado\.pdf$/);
  });
});
