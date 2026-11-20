import { describe, expect, it } from "vitest";
import { cotaSugerida, idDoAndar, LAJE_MM, nomeSugerido } from "./andares";

const pav = (id: string, cota: number, pe: number) => ({ id, cota_piso: { valor: cota }, pe_direito: { valor: pe } });

describe("andar novo", () => {
  it("id a partir do nome, sem acento e sem repetir", () => {
    expect(idDoAndar("Superior", ["terreo"])).toBe("superior");
    expect(idDoAndar("Ático / Sótão", [])).toBe("atico-sotao");
    expect(idDoAndar("Superior", ["terreo", "superior"])).toBe("superior-2");
    expect(idDoAndar("!!!", [])).toBe("andar");
  });
  it("cota em cima do andar mais alto, com a laje", () => {
    expect(cotaSugerida([pav("terreo", 0, 2700)])).toBe(2700 + LAJE_MM);
    expect(cotaSugerida([pav("terreo", 0, 2700), pav("superior", 2850, 2600)])).toBe(2850 + 2600 + LAJE_MM);
    expect(cotaSugerida([])).toBe(0);
  });
  it("nome sugerido", () => {
    expect(nomeSugerido(1)).toBe("Superior");
    expect(nomeSugerido(2)).toBe("Andar 3");
  });
});
