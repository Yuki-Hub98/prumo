import { describe, expect, it } from "vitest";
import {
  adicionarEspaco,
  adicionarVao,
  alternarPorta,
  alturaEspaco,
  type Construcao,
  larguraVao,
  moverEspaco,
  removerEspaco,
  removerVao,
  tipoEspaco,
} from "./planejado";

const base: Construcao = {
  chapa: { material: "MDF branco", espessura: { valor: 18, origem: "estimada" } },
  fundo: { material: "HDF branco", espessura: { valor: 6, origem: "estimada" } },
  vaos: [{ espacos: [{ tipo: "gaveta" }, { tipo: "nicho" }], porta: true }],
};

describe("editar a construção", () => {
  it("vãos: adiciona, tira (mínimo um), porta e largura", () => {
    const dois = adicionarVao(base);
    expect(dois.vaos).toHaveLength(2);
    expect(base.vaos).toHaveLength(1); // original intacto
    expect(removerVao(dois, 0).vaos).toHaveLength(1);
    expect(removerVao(base, 0)).toBe(base);
    expect(alternarPorta(base, 0).vaos[0].porta).toBe(false);
    expect(alternarPorta(alternarPorta(base, 0), 0).vaos[0].porta).toBe(true);
    expect(larguraVao(base, 0, 600).vaos[0].largura).toEqual({ valor: 600, origem: "projeto" });
    expect(larguraVao(larguraVao(base, 0, 600), 0, null).vaos[0].largura).toBeNull();
  });

  it("espaços: adiciona em cima, troca tipo, altura, sobe/desce e tira (mínimo um)", () => {
    let c = adicionarEspaco(base, 0, "cabideiro");
    expect(c.vaos[0].espacos.map((e) => e.tipo)).toEqual(["gaveta", "nicho", "cabideiro"]);
    c = tipoEspaco(c, 0, 1, "gaveta");
    c = alturaEspaco(c, 0, 0, 180);
    expect(c.vaos[0].espacos[0].altura).toEqual({ valor: 180, origem: "projeto" });
    c = moverEspaco(c, 0, 2, -1);
    expect(c.vaos[0].espacos.map((e) => e.tipo)).toEqual(["gaveta", "cabideiro", "gaveta"]);
    expect(moverEspaco(c, 0, 0, -1)).toBe(c); // já está embaixo
    c = removerEspaco(c, 0, 1);
    expect(c.vaos[0].espacos.map((e) => e.tipo)).toEqual(["gaveta", "gaveta"]);
    const um = removerEspaco(removerEspaco(c, 0, 0), 0, 0);
    expect(um.vaos[0].espacos).toHaveLength(1);
  });
});
