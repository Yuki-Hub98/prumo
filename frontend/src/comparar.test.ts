import { describe, expect, it } from "vitest";
import type { InfoRender } from "./api/cliente";
import { ultimasImagens, vistasEmComum } from "./comparar";

const r = (id: number, variacao: string, status: string, vistas: string[], qualidade = "rascunho") =>
  ({
    id,
    variacao,
    status,
    qualidade,
    versao_projeto: id,
    criado_em: `2026-11-20T10:0${id}:00`,
    imagens_url: vistas.map((v) => `/renders/${id}/imagens/render-${v}.png`),
  }) as unknown as InfoRender;

describe("comparador", () => {
  // a API lista da mais nova para a mais velha
  const lista = [
    r(5, "escura", "rodando", ["perspectiva"]),
    r(4, "escura", "pronto", ["perspectiva"], "final"),
    r(3, "base", "pronto", ["perspectiva", "superior"]),
    r(2, "escura", "pronto", ["perspectiva", "superior"]),
    r(1, "clara", "erro", ["perspectiva"]),
  ];
  it("a imagem pronta mais recente de cada variação, por vista", () => {
    const img = ultimasImagens(lista);
    expect(Object.keys(img).sort()).toEqual(["base", "escura"]);
    expect(img.escura.perspectiva.url).toBe("/renders/4/imagens/render-perspectiva.png");
    expect(img.escura.perspectiva.qualidade).toBe("final");
    expect(img.escura.superior.url).toBe("/renders/2/imagens/render-superior.png");
  });
  it("vistas que dá para comparar entre as escolhidas", () => {
    const img = ultimasImagens(lista);
    expect(vistasEmComum(img, ["base", "escura"]).sort()).toEqual(["perspectiva", "superior"]);
    expect(vistasEmComum(img, ["base", "clara"])).toEqual([]);
  });
});
