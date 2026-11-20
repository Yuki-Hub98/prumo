import { describe, expect, it } from "vitest";
import { aplicar, valorDe } from "./variacao";

const base = { parede: "#111111", paredes: { p1: "#222222" }, moveis: { cama: "#333333" } };

describe("aplicar", () => {
  it("uma chave de cada tipo", () => {
    expect(aplicar(base, ["piso"], "#aaaaaa").piso).toBe("#aaaaaa");
    expect(aplicar(base, ["p:p2"], "#aaaaaa").paredes).toEqual({ p1: "#222222", p2: "#aaaaaa" });
    expect(aplicar(base, ["m:gr"], "#aaaaaa").moveis).toEqual({ cama: "#333333", gr: "#aaaaaa" });
  });

  it("várias de uma vez, sem mexer no original", () => {
    const novo = aplicar(base, ["parede", "p:p1", "m:cama", "m:gr"], "#0000ff");
    expect(novo.parede).toBe("#0000ff");
    expect(novo.paredes).toEqual({ p1: "#0000ff" });
    expect(novo.moveis).toEqual({ cama: "#0000ff", gr: "#0000ff" });
    expect(base.moveis).toEqual({ cama: "#333333" });
  });

  it("null volta ao padrão", () => {
    const novo = aplicar(base, ["p:p1", "m:cama", "parede"], null);
    expect(novo.paredes).toEqual({});
    expect(novo.moveis).toEqual({});
    expect(novo.parede).toBeNull();
  });
});

describe("valorDe", () => {
  it("lê cada chave; móvel também pelo tipo", () => {
    expect(valorDe(base, "p:p1")).toBe("#222222");
    expect(valorDe(base, "p:p9")).toBeUndefined();
    expect(valorDe(base, "parede")).toBe("#111111");
    expect(valorDe({ moveis: { guarda_roupa: "#444444" } }, "m:gr-1", { "gr-1": "guarda_roupa" })).toBe("#444444");
  });
});

describe("partes do móvel (q:<móvel>:<parte>)", () => {
  it("aplica, lê (id ou tipo) e limpa sem deixar móvel vazio", () => {
    const c = aplicar({}, ["q:gr-1:portas", "q:gr-1:puxadores"], "#ffffff");
    expect(c.pecas).toEqual({ "gr-1": { portas: "#ffffff", puxadores: "#ffffff" } });
    expect(valorDe(c, "q:gr-1:portas")).toBe("#ffffff");
    expect(valorDe({ pecas: { guarda_roupa: { gavetas: "#123456" } } }, "q:gr-1:gavetas", { "gr-1": "guarda_roupa" })).toBe("#123456");
    const sem = aplicar(aplicar(c, ["q:gr-1:portas"], null), ["q:gr-1:puxadores"], null);
    expect(sem.pecas).toEqual({});
    expect(c.pecas).toEqual({ "gr-1": { portas: "#ffffff", puxadores: "#ffffff" } }); // original intacto
  });
});
