import { useState } from "react";
import type { Medida } from "../api/cliente";
import { formatar, ORIGENS, paraMm, type Origem, type Unidade } from "../unidades";

const COR: Record<Origem, string> = {
  trena: "bg-emerald-100 text-emerald-800",
  projeto: "bg-sky-100 text-sky-800",
  estimada: "bg-amber-100 text-amber-800",
};

export function SeloOrigem({ origem }: { origem: Origem }) {
  const o = ORIGENS.find((x) => x.valor === origem)!;
  return (
    <span title={o.dica} className={`rounded px-1.5 py-0.5 text-xs font-medium ${COR[origem]}`}>
      {o.rotulo}
    </span>
  );
}

/**
 * Mostra uma medida e permite trocá-la. A origem é sempre perguntada (nada vem
 * marcado): só dá para salvar depois de escolher "Medi", "Quero assim" ou "Chute".
 */
export function CampoMedida({
  rotulo,
  medida,
  unidade,
  aoSalvar,
  ocupado,
}: {
  rotulo: string;
  medida?: Medida | null;
  unidade: Unidade;
  aoSalvar: (m: Medida) => void;
  ocupado?: boolean;
}) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState("");
  const [origem, setOrigem] = useState<Origem | null>(null);
  const mm = paraMm(texto, unidade);

  if (!editando)
    return (
      <div className="flex items-center justify-between gap-2 py-1 text-sm">
        <span className="text-stone-500">{rotulo}</span>
        <span className="flex items-center gap-2">
          {medida ? formatar(medida.valor, unidade) : "—"}
          {medida && <SeloOrigem origem={medida.origem as Origem} />}
          <button
            className="text-xs text-sky-700 hover:underline"
            onClick={() => {
              setTexto(medida ? formatar(medida.valor, unidade, false) : "");
              setOrigem(null);
              setEditando(true);
            }}
          >
            Editar
          </button>
        </span>
      </div>
    );

  return (
    <form
      className="my-1 rounded border border-stone-300 bg-white p-2 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        if (mm === null || origem === null) return;
        aoSalvar({ valor: mm, origem });
        setEditando(false);
      }}
    >
      <label className="flex items-center gap-2">
        <span className="w-24 text-stone-500">{rotulo}</span>
        <input
          autoFocus
          className="w-24 rounded border px-1"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
        <span>{unidade}</span>
      </label>
      {texto && mm === null && <p className="text-xs text-red-700">Número inválido</p>}
      <fieldset className="mt-2 flex flex-wrap gap-3">
        <legend className="mb-1 text-xs text-stone-500">De onde veio esse valor?</legend>
        {ORIGENS.map((o) => (
          <label key={o.valor} title={o.dica} className="flex items-center gap-1">
            <input
              type="radio"
              name="origem"
              checked={origem === o.valor}
              onChange={() => setOrigem(o.valor)}
            />
            {o.rotulo}
          </label>
        ))}
      </fieldset>
      <div className="mt-2 flex gap-2">
        <button
          type="submit"
          disabled={mm === null || origem === null || ocupado}
          className="rounded bg-stone-800 px-2 py-0.5 text-white disabled:opacity-40"
        >
          Salvar
        </button>
        <button type="button" onClick={() => setEditando(false)} className="text-stone-600">
          Cancelar
        </button>
      </div>
    </form>
  );
}
