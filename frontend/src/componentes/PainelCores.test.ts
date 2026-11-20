import { describe, expect, it } from "vitest";
import { nomeLivre, trocarAberto } from "./PainelCores";

describe("nomeLivre", () => {
  it("primeiro nome de variação livre", () => {
    expect(nomeLivre([])).toBe("minhas-cores");
    expect(nomeLivre(["escura", "minhas-cores"])).toBe("minhas-cores-2");
    expect(nomeLivre(["minhas-cores", "minhas-cores-2"])).toBe("minhas-cores-3");
  });
});

describe("trocarAberto", () => {
  it("abre o selecionado, fecha o que deixou de ser e mantém os abertos na mão", () => {
    expect([...trocarAberto(new Set(["cama"]), "cama", "armario")]).toEqual(["armario"]);
    expect([...trocarAberto(new Set(["cama", "tv"]), "cama", "armario")].sort()).toEqual(["armario", "tv"]);
    expect([...trocarAberto(new Set(["cama"]), "cama", null)]).toEqual([]);
    expect([...trocarAberto(new Set(), null, "cama")]).toEqual(["cama"]);
  });
});
