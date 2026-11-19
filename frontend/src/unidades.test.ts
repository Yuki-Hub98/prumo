import { describe, expect, it } from "vitest";
import { formatar, paraMm } from "./unidades";

describe("unidades", () => {
  it("formata mm na unidade escolhida", () => {
    expect(formatar(3150, "mm")).toBe("3150 mm");
    expect(formatar(3150, "cm")).toBe("315 cm");
    expect(formatar(3155, "cm")).toBe("315,5 cm");
    expect(formatar(3150, "m")).toBe("3,15 m");
    expect(formatar(2600, "m", false)).toBe("2,6");
    expect(formatar(0, "cm")).toBe("0 cm");
  });

  it("converte o digitado para mm inteiros", () => {
    expect(paraMm("315", "cm")).toBe(3150);
    expect(paraMm("315,5", "cm")).toBe(3155);
    expect(paraMm("3.15", "m")).toBe(3150);
    expect(paraMm(" 2,605 ", "m")).toBe(2605);
    expect(paraMm("12.34", "mm")).toBe(12);
    expect(paraMm("", "cm")).toBeNull();
    expect(paraMm("-3", "cm")).toBeNull();
    expect(paraMm("abc", "cm")).toBeNull();
  });
});
