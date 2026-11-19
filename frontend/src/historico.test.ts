import { describe, expect, it } from "vitest";
import { nomeOperacao, resumoCaminho } from "./historico";

describe("histórico", () => {
  it("dá nome às operações e às voltas", () => {
    expect(nomeOperacao("mover_movel")).toBe("Moveu móvel");
    expect(nomeOperacao("desfazer:9")).toBe("Desfez (conteúdo da versão 9)");
    expect(nomeOperacao("reverter:2")).toBe("Voltou (conteúdo da versão 2)");
    expect(nomeOperacao("coisa_nova")).toBe("coisa nova");
    expect(nomeOperacao(null)).toBe("Alteração");
  });

  it("resume o caminho alterado", () => {
    expect(resumoCaminho("comodos.quarto.moveis[cama].centro")).toBe("quarto · cama · centro");
    expect(resumoCaminho("projeto.pavimentos[terreo].comodos[quarto]")).toBe("terreo · quarto");
  });
});
