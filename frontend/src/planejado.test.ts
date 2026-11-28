import { describe, expect, it } from "vitest";
import {
  adicionarEspaco,
  adicionarVao,
  alternarPorta,
  alturaEspaco,
  type Construcao,
  larguraVao,
  moverEspaco,
  puxarAlturaEspaco,
  puxarLarguraVao,
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

describe("puxar no editar em detalhe", () => {
  const mm = (valor: number) => ({ valor, origem: "projeto" as const });
  const c: Construcao = {
    ...base,
    vaos: [
      { espacos: [{ tipo: "gaveta", altura: mm(200) }, { tipo: "cabideiro" }, { tipo: "nicho", altura: mm(400) }], largura: mm(900) },
      { espacos: [{ tipo: "nicho" }] },
      { espacos: [{ tipo: "nicho" }], largura: mm(600) },
    ],
  };

  it("a altura puxada sai do vizinho fixo (como mover a prateleira)", () => {
    const n = puxarAlturaEspaco(c, 0, 1, 2, 1568, 1367.6); // +200 a partir de 1368
    expect(n.vaos[0].espacos[1].altura?.valor).toBe(1568);
    expect(n.vaos[0].espacos[2].altura?.valor).toBe(200);
    expect(c.vaos[0].espacos[2].altura?.valor).toBe(400); // original intacto
  });

  it("vizinho automático cede sozinho", () => {
    const n = puxarAlturaEspaco(c, 0, 2, 1, 300, 400);
    expect(n.vaos[0].espacos.map((e) => e.altura?.valor)).toEqual([200, undefined, 300]);
  });

  it("largura do vão: o vizinho fixo cede, o automático fica automático", () => {
    expect(puxarLarguraVao(c, 1, 2, 700, 650).vaos.map((v) => v.largura?.valor)).toEqual([900, 700, 550]);
    expect(puxarLarguraVao(c, 0, 1, 1000, 900).vaos.map((v) => v.largura?.valor)).toEqual([1000, undefined, 600]);
  });
});
