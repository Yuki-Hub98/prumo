import { describe, expect, it } from "vitest";
import { maiuscula } from "./texto";

describe("maiuscula", () => {
  it("só a primeira letra, com acento, e texto vazio intacto", () => {
    expect(maiuscula("área livre")).toBe("Área livre");
    expect(maiuscula("pé-direito do térreo")).toBe("Pé-direito do térreo");
    expect(maiuscula("")).toBe("");
  });
});
