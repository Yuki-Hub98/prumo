import { describe, expect, it } from "vitest";
import { alternar, vistaDaImagem, vistasValidas } from "./vistas";

const DISP = ["perspectiva", "porta", "cama", "canto-1", "superior"];

describe("vistas", () => {
  it("usa o padrão e descarta as que sumiram", () => {
    expect(vistasValidas(null, DISP)).toEqual(["perspectiva", "superior"]);
    expect(vistasValidas(["superior", "cama"], DISP)).toEqual(["cama", "superior"]); // ordem da API
    expect(vistasValidas(["cama"], ["perspectiva", "superior"])).toEqual(["perspectiva", "superior"]);
    expect(vistasValidas(["x"], ["porta"])).toEqual(["porta"]);
    expect(vistasValidas(null, [])).toEqual([]);
  });

  it("liga e desliga sem esvaziar", () => {
    expect(alternar(["perspectiva"], "cama", DISP)).toEqual(["perspectiva", "cama"]);
    expect(alternar(["perspectiva", "cama"], "perspectiva", DISP)).toEqual(["cama"]);
    expect(alternar(["cama"], "cama", DISP)).toEqual(["cama"]);
  });

  it("acha a vista pelo nome do arquivo", () => {
    expect(vistaDaImagem("/renders/7/imagens/render-canto-2.png")).toBe("canto-2");
  });
});
