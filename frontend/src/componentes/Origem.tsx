import { CircleDashed, PencilRuler, Ruler } from "lucide-react";
import { ORIGENS, type Origem } from "../unidades";

/** Cor nunca anda sozinha: cada origem tem cor, ícone e, no chute, borda tracejada. */
const VISUAL: Record<Origem, { Icone: typeof Ruler; cls: string; ativo: string }> = {
  trena: {
    Icone: Ruler,
    cls: "border-transparent bg-medido-fundo text-medido",
    ativo: "border-medido bg-medido-fundo text-medido ring-1 ring-medido",
  },
  projeto: {
    Icone: PencilRuler,
    cls: "border-transparent bg-projeto-fundo text-projeto",
    ativo: "border-projeto bg-projeto-fundo text-projeto ring-1 ring-projeto",
  },
  estimada: {
    Icone: CircleDashed,
    cls: "border-dashed border-chute bg-chute-fundo text-chute",
    ativo: "border-dashed border-chute bg-chute-fundo text-chute ring-1 ring-chute",
  },
};

const PILULA = "inline-flex h-5 items-center gap-1 rounded-sm border px-1.5 text-[11px] font-semibold uppercase tracking-wider";

/** Selo da origem de uma medida (Medi / Quero assim / Chute). */
export function SeloOrigem({ origem }: { origem: Origem }) {
  const o = ORIGENS.find((x) => x.valor === origem);
  if (!o) return null;
  const { Icone, cls } = VISUAL[origem];
  return (
    <span title={o.dica} className={`${PILULA} ${cls}`}>
      <Icone size={12} strokeWidth={2} aria-hidden="true" /> {o.rotulo}
    </span>
  );
}

/**
 * Pergunta a origem com os três selos. Nada vem marcado (decisão do usuário: sempre
 * perguntar); o escolhido ganha contorno e os outros ficam apagados.
 */
export function EscolhaOrigem({
  valor,
  aoEscolher,
  rotulo = "De onde veio?",
}: {
  valor: Origem | null;
  aoEscolher: (o: Origem) => void;
  rotulo?: string | null;
}) {
  return (
    <div role="radiogroup" aria-label={rotulo ?? "Origem da medida"} className="flex flex-wrap items-center gap-1.5">
      {rotulo && <span className="text-xs text-tinta-suave">{rotulo}</span>}
      {ORIGENS.map((o) => {
        const { Icone, ativo } = VISUAL[o.valor];
        const marcado = valor === o.valor;
        return (
          <button
            key={o.valor}
            type="button"
            role="radio"
            aria-checked={marcado}
            title={o.dica}
            onClick={() => aoEscolher(o.valor)}
            className={`${PILULA} ${marcado ? ativo : `${o.valor === "estimada" ? "border-dashed" : ""} border-linha-forte bg-superficie text-tinta-suave hover:text-tinta`}`}
          >
            <Icone size={12} strokeWidth={2} aria-hidden="true" /> {o.rotulo}
          </button>
        );
      })}
    </div>
  );
}
