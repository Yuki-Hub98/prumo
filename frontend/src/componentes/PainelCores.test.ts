import { describe, expect, it } from "vitest";
import { nomeLivre } from "./PainelCores";

describe("nomeLivre", () => {
  it("primeiro nome de variação livre", () => {
    expect(nomeLivre([])).toBe("minhas-cores");
    expect(nomeLivre(["escura", "minhas-cores"])).toBe("minhas-cores-2");
    expect(nomeLivre(["minhas-cores", "minhas-cores-2"])).toBe("minhas-cores-3");
  });
});
