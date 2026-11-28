import { describe, expect, it } from "vitest";
import { furoNoCentro, furoParaRetangulo, novaLaje, novaViga, novoPilar, ordenar, retanguloParaFuro } from "./estruturas";

describe("estruturas", () => {
  it("novos elementos com chute e obs dizendo de onde veio", () => {
    const p = novoPilar("pilar-1", [1234.4, 99.6]);
    expect(p.centro).toEqual([1234, 100]);
    expect(p.largura).toMatchObject({ valor: 200, origem: "estimada" });
    expect(p.largura.obs).toContain("estimada");
    const v = novaViga("viga-1", { eixo: [[0, 0], [3000, 0]], espessura: 150 });
    expect([v.inicio, v.fim, v.largura.valor, v.altura.valor]).toEqual([[0, 0], [3000, 0], 150, 300]);
    expect(novaLaje("laje-1")).toMatchObject({ tipo: "laje", espessura: { valor: 120, origem: "estimada" } });
  });

  it("furo ↔ retângulo", () => {
    const furo = furoNoCentro([2000, 3000]);
    expect(furo).toEqual([[1500, 1750], [2500, 1750], [2500, 4250], [1500, 4250]]);
    const r = furoParaRetangulo(furo);
    expect(r).toEqual({ x: 1500, y: 1750, largura: 1000, comprimento: 2500 });
    expect(retanguloParaFuro({ ...r, largura: 1200 })[1]).toEqual([2700, 1750]);
  });

  it("ordem da aba: lajes, vigas, pilares", () => {
    const itens = [{ tipo: "pilar", id: "b" }, { tipo: "laje", id: "z" }, { tipo: "viga", id: "a" }, { tipo: "pilar", id: "a" }];
    expect(ordenar(itens).map((i) => `${i.tipo}:${i.id}`)).toEqual(["laje:z", "viga:a", "pilar:a", "pilar:b"]);
  });
});
