import { Box3, Mesh } from "three";
import { describe, expect, it } from "vitest";
import { type Cena3D, giroThree, montarCena, paraThree } from "./montarCena";

const cena: Cena3D = {
  versao: 3,
  prismas: [
    { nome: "piso", contorno: [[0, 0], [3000, 0], [3000, 4000], [0, 4000]], z0: -20, z1: 0, material: "piso", oculto_em: [] },
    { nome: "teto", contorno: [[0, 0], [3000, 0], [3000, 4000], [0, 4000]], z0: 2700, z1: 2720, material: "teto", oculto_em: ["superior"] },
  ],
  caixas: [
    { nome: "cama-cabeceira", centro: [1000, 500, 600], tamanho: [1400, 80, 1200], rotacao: 90, material: "movel-cama", chanfro: 35, oculto_em: [], extras: { movel: "cama", parte: "cabeceira" } },
  ],
  materiais: {
    piso: { cor: "#a67c52", rugosidade: 0.45, metal: false, vidro: false },
    teto: { cor: "#fafafa", rugosidade: 0.6, metal: false, vidro: false },
    "movel-cama": { cor: "#d6d3d1", rugosidade: 0.55, metal: false, vidro: false },
  },
};

describe("montarCena", () => {
  it("eixos do .glb: metros, Y para cima, y da planta = −z", () => {
    expect(paraThree(1000, 2000, 300)).toEqual([1, 0.3, -2]);
    expect(giroThree(90)).toBeCloseTo(Math.PI / 2);
  });

  it("prisma extrudado no lugar certo e com as marcas para pintura, teto e seleção", () => {
    const g = montarCena(cena);
    const piso = g.getObjectByName("piso") as Mesh;
    const b = new Box3().setFromObject(piso);
    expect(b.min.x).toBeCloseTo(0);
    expect(b.max.x).toBeCloseTo(3);
    expect(b.min.y).toBeCloseTo(-0.02);
    expect(b.max.y).toBeCloseTo(0);
    expect(b.min.z).toBeCloseTo(-4); // y da planta 0..4 m → z 0..−4
    expect(b.max.z).toBeCloseTo(0);
    expect(g.getObjectByName("teto")?.userData.oculto_em).toBe("superior");
    const cab = g.getObjectByName("cama-cabeceira") as Mesh;
    expect(cab.userData).toMatchObject({ material: "movel-cama", movel: "cama", parte: "cabeceira" });
    expect(cab.position.toArray()).toEqual([1, 0.6, -0.5]);
    expect(cab.rotation.y).toBeCloseTo(Math.PI / 2);
    expect((cab.material as { name: string }).name).toBe("movel-cama");
  });
});
