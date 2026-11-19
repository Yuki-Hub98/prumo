import { describe, expect, it } from "vitest";
import { formatarTempo } from "./tempo";

describe("tempo", () => {
  it("formata segundos para estimativa", () => {
    expect(formatarTempo(12.4)).toBe("12 s");
    expect(formatarTempo(70)).toBe("1 min 10 s");
    expect(formatarTempo(120)).toBe("2 min");
    expect(formatarTempo(7500)).toBe("2 h 05 min");
    expect(formatarTempo(-3)).toBe("0 s");
    expect(formatarTempo(null)).toBe("—");
  });
});
