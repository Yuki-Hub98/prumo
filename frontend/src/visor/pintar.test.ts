import { describe, expect, it } from "vitest";
import { type Contexto, corDo, movelDaPeca, papel } from "./pintar";

const comodo: Contexto = {
  comodo: "quarto",
  pavimento: false,
  aberturas: { "janela-quarto": "p1", "porta-banheiro": "p7" },
  moveis: { cama: "cama", "gr-1": "guarda_roupa" },
};
const pavimento: Contexto = { ...comodo, pavimento: true };

describe("papel", () => {
  it("modelo do cômodo: arquitetura e paredes pelo nome do objeto", () => {
    expect(papel("piso", "piso", comodo)).toEqual({ tipo: "piso" });
    expect(papel("teto", "teto", comodo)).toEqual({ tipo: "teto" });
    expect(papel("rodape-3", "rodape", comodo)).toEqual({ tipo: "rodape" });
    expect(papel("parede-p2-0", "parede", comodo)).toEqual({ tipo: "parede", parede: "p2" });
    expect(papel("parede-p-norte-1", "parede", comodo)).toEqual({ tipo: "parede", parede: "p-norte" });
    expect(papel("peitoril-janela-quarto", "parede", comodo)).toEqual({ tipo: "parede", parede: "p1" });
    expect(papel("verga-porta-banheiro", "parede", comodo)).toEqual({ tipo: "parede", parede: "p7" });
    expect(papel("vidro-janela-quarto", "vidro", comodo)).toBeNull();
    expect(papel("batente-porta-banheiro-e", "porta", comodo)).toBeNull();
  });

  it("móveis pelo material, só os do cômodo", () => {
    expect(papel("cama-estrutura", "movel-cama", comodo)).toEqual({ tipo: "movel", id: "cama", parte: "corpo", doCorpo: true });
    expect(papel("cama-colchao", "colchao", comodo)).toBeNull(); // colchão não pinta
    expect(papel("pia-1", "movel-pia", comodo)).toBeNull();
  });

  it("modelo do pavimento: só o que tem o cômodo no nome; paredes não", () => {
    expect(papel("piso-quarto", "piso-quarto", pavimento)).toEqual({ tipo: "piso" });
    expect(papel("piso-banheiro", "piso-banheiro", pavimento)).toBeNull();
    expect(papel("rodape-0-quarto", "rodape", pavimento)).toEqual({ tipo: "rodape" });
    expect(papel("parede-p2-0", "parede", pavimento)).toBeNull();
    expect(papel("cama-estrutura-quarto", "movel-cama", pavimento)).toEqual({
      tipo: "movel",
      id: "cama",
      parte: "corpo",
      doCorpo: true,
    });
  });
});

describe("corDo", () => {
  const cores = { parede: "#111111", paredes: { p2: "#222222" }, piso: "#333333", moveis: { guarda_roupa: "#444444" } };
  it("parede própria vence a geral; móvel por id ou por tipo", () => {
    expect(corDo({ tipo: "parede", parede: "p2" }, cores, comodo)).toBe("#222222");
    expect(corDo({ tipo: "parede", parede: "p1" }, cores, comodo)).toBe("#111111");
    expect(corDo({ tipo: "piso" }, cores, comodo)).toBe("#333333");
    expect(corDo({ tipo: "teto" }, cores, comodo)).toBeNull();
    expect(corDo({ tipo: "movel", id: "gr-1", parte: "corpo", doCorpo: true }, cores, comodo)).toBe("#444444");
    expect(corDo({ tipo: "movel", id: "cama", parte: "corpo", doCorpo: true }, cores, comodo)).toBeNull();
  });
});

describe("movelDaPeca", () => {
  const ids = ["cama", "cama-auxiliar", "gr-1"];
  it("pelo material ou pelo nome da peça; o id mais longo vence", () => {
    expect(movelDaPeca("cama-cabeceira", "movel-cama", ids)).toBe("cama");
    expect(movelDaPeca("cama-colchao", "colchao", ids)).toBe("cama");
    expect(movelDaPeca("cama-auxiliar-colchao", "colchao", ids)).toBe("cama-auxiliar");
    expect(movelDaPeca("gr-1-puxador0-quarto", "metal", ids)).toBe("gr-1");
    expect(movelDaPeca("parede-p1-0", "parede", ids)).toBeNull();
  });
});

describe("partes do móvel (modelo v8, extras do glTF)", () => {
  const porta = { movel: "gr-1", parte: "portas" };
  it("papel pelas extras; peça sem parte e fora do material do móvel não pinta", () => {
    expect(papel("gr-1-folha0", "movel-gr-1", comodo, porta)).toEqual({ tipo: "movel", id: "gr-1", parte: "portas", doCorpo: true });
    expect(papel("gr-1-folha0", "movel-gr-1@gr-1@portas", comodo, porta)).toMatchObject({ parte: "portas", doCorpo: true });
    expect(papel("gr-1-puxador0", "metal", comodo, { movel: "gr-1", parte: "puxadores" })).toMatchObject({ doCorpo: false });
    expect(papel("gr-1-rodape", "sombra", comodo, { movel: "gr-1", parte: "corpo" })).toBeNull();
    expect(papel("pia-1", "movel-pia", comodo, { movel: "pia", parte: "corpo" })).toBeNull(); // outro cômodo
  });
  it("cor da parte (id vence tipo); sem ela, portas ficam com a do móvel e puxador com a sua", () => {
    const portas = { tipo: "movel", id: "gr-1", parte: "portas", doCorpo: true } as const;
    const puxador = { tipo: "movel", id: "gr-1", parte: "puxadores", doCorpo: false } as const;
    const cores = { moveis: { "gr-1": "#111111" }, pecas: { guarda_roupa: { portas: "#eeeeee" }, "gr-1": { puxadores: "#c0a060" } } };
    expect(corDo(portas, cores, comodo)).toBe("#eeeeee");
    expect(corDo(puxador, cores, comodo)).toBe("#c0a060");
    expect(corDo(portas, { moveis: { "gr-1": "#111111" } }, comodo)).toBe("#111111");
    expect(corDo(puxador, { moveis: { "gr-1": "#111111" } }, comodo)).toBeNull();
  });
});
