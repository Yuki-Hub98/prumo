import { describe, expect, it } from "vitest";
import { encaixar, paraId, proximoId, vertices } from "./geometria";

describe("editor", () => {
  const cantos = vertices([
    [[0, 0], [4000, 0]],
    [[4000, 0], [4000, 3000]],
  ]);

  it("acha os cantos únicos", () => {
    expect(cantos).toEqual([[0, 0], [4000, 0], [4000, 3000]]);
  });

  it("gruda no canto, arredonda na grade e alinha reto", () => {
    expect(encaixar([3920, 60], cantos)).toEqual([4000, 0]);
    expect(encaixar([1234, 5678], cantos)).toEqual([1230, 5680]);
    expect(encaixar([2003, 104], cantos, [0, 0])).toEqual([2000, 0]); // quase horizontal
    expect(encaixar([60, 2504], cantos, [0, 0])).toEqual([0, 2500]); // quase vertical
    expect(encaixar([1500, 900], cantos, [0, 0])).toEqual([1500, 900]); // diagonal fica
    expect(encaixar([3990, 10], cantos, null, [4000, 0])).toEqual([3990, 10]); // ignora o próprio
  });

  it("gera ids", () => {
    expect(proximoId("p", ["p1", "p2", "p4"])).toBe("p3");
    expect(paraId("Área de Serviço 2")).toBe("area-de-servico-2");
  });
});
