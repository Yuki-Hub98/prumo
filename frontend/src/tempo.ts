/** Segundos → texto curto para estimativas ("12 s", "1 min 10 s", "2 h 05 min"). */
export function formatarTempo(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s)) return "—";
  const t = Math.max(0, Math.round(s));
  if (t < 60) return `${t} s`;
  if (t < 3600) {
    const m = Math.floor(t / 60);
    const r = t % 60;
    return r ? `${m} min ${r} s` : `${m} min`;
  }
  const h = Math.floor(t / 3600);
  return `${h} h ${String(Math.round((t % 3600) / 60)).padStart(2, "0")} min`;
}
