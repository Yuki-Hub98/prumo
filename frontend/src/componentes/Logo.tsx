/** Marca do PRUMO: fio em grafite e o peso do prumo em amarelo trena (32 × 48). */
export function Marca({ altura = 24 }: { altura?: number }) {
  return (
    <svg viewBox="0 0 32 48" height={altura} width={(altura * 32) / 48} aria-hidden="true">
      <line x1="16" y1="0" x2="16" y2="16" stroke="var(--tinta)" strokeWidth="2" />
      <circle cx="16" cy="17" r="2.5" fill="var(--tinta)" />
      <path
        d="M16 20 L25 27 L25 35 L16 47 L7 35 L7 27 Z"
        fill="var(--trena)"
        stroke="var(--tinta)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Logotipo: marca + PRUMO em Plex Sans Condensed, maiúsculas. */
export function Logo({ altura = 28 }: { altura?: number }) {
  return (
    <span className="inline-flex items-center gap-2" aria-label="PRUMO">
      <Marca altura={altura} />
      <span className="font-cond font-semibold uppercase tracking-[0.04em]" style={{ fontSize: altura * 0.75 }}>
        Prumo
      </span>
    </span>
  );
}
