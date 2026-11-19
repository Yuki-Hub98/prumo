import { describe, expect, it } from "vitest";
import { hexParaRgb, lerCor, rgbParaHex, rgbTexto } from "./cores";

describe("cores", () => {
  it("converte hex e RGB nos dois sentidos", () => {
    expect(hexParaRgb("#c46b4f")).toEqual([196, 107, 79]);
    expect(rgbParaHex([196, 107, 79])).toBe("#c46b4f");
    expect(rgbParaHex([0, 5, 255])).toBe("#0005ff");
    expect(rgbTexto("#2f5d62")).toBe("47, 93, 98");
  });

  it("lê o que a pessoa digita ou cola", () => {
    expect(lerCor("196, 107, 79")).toBe("#c46b4f");
    expect(lerCor("196 107 79")).toBe("#c46b4f");
    expect(lerCor("rgb(196, 107, 79)")).toBe("#c46b4f");
    expect(lerCor("RGB(196,107,79)")).toBe("#c46b4f");
    expect(lerCor("#C46B4F")).toBe("#c46b4f");
    expect(lerCor("#f75")).toBe("#ff7755");
    expect(lerCor("c46b4f")).toBe("#c46b4f");
    expect(lerCor("256, 0, 0")).toBeNull();
    expect(lerCor("10, 20")).toBeNull();
    expect(lerCor("azul")).toBeNull();
  });
});
