import { describe, expect, it } from "vitest";
import { idCriado } from "./Paineis";

describe("idCriado", () => {
  it("acha o id do móvel novo no caminho da alteração", () => {
    expect(idCriado(["comodos.quarto.moveis[sob-medida-2]"])).toBe("sob-medida-2");
    expect(idCriado(["comodos.quarto.moveis[cama].centro", "comodos.quarto.moveis[gr]"])).toBe("gr");
    expect(idCriado(["projeto.pavimentos[terreo]"])).toBeNull();
  });
});
