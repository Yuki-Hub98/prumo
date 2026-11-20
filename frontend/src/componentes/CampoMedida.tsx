import { useState } from "react";
import type { Medida } from "../api/cliente";
import { btn } from "../estilo";
import { formatar, paraMm, partes, type Origem, type Unidade } from "../unidades";
import { EscolhaOrigem, SeloOrigem } from "./Origem";

export { SeloOrigem } from "./Origem";

/** Valor de medida em Mono com a unidade apagada depois ("2 450 mm"). */
export function Valor({ mm, unidade }: { mm: number; unidade: Unidade }) {
  const [num, unid] = partes(mm, unidade);
  return (
    <span className="num font-medium whitespace-nowrap">
      {num} <span className="font-normal text-tinta-suave">{unid}</span>
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
        <span className="text-tinta-suave">{rotulo}</span>
        <span className="flex items-center gap-2">
          {medida ? <Valor mm={medida.valor} unidade={unidade} /> : <span className="text-tinta-suave">—</span>}
          {medida && <SeloOrigem origem={medida.origem as Origem} />}
          <button
            className="link text-xs"
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

  const invalido = !!texto && mm === null;
  const borda = invalido
    ? "border-erro"
    : origem === "estimada"
      ? "border-dashed border-chute"
      : "border-linha-forte";
  return (
    <form
      className="my-1 space-y-2 rounded-md border border-linha bg-superficie-2 p-2 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        if (mm === null || origem === null) return;
        aoSalvar({ valor: mm, origem });
        setEditando(false);
      }}
    >
      <label className="block">
        <span className="mb-1 block text-xs font-semibold uppercase tracking-[0.06em] text-tinta-suave">{rotulo}</span>
        <span
          className={`flex h-9 items-center gap-2 rounded-md border bg-superficie px-3 focus-within:border-foco focus-within:ring-1 focus-within:ring-foco ${borda}`}
        >
          <input
            autoFocus
            inputMode="decimal"
            className="num min-w-0 flex-1 border-0 bg-transparent text-right text-sm font-medium outline-none"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
          />
          <span className="text-tinta-suave">{unidade}</span>
        </span>
      </label>
      {invalido && <p className="text-xs text-erro">Número inválido</p>}
      <EscolhaOrigem valor={origem} aoEscolher={setOrigem} />
      <div className="flex gap-2">
        <button type="submit" disabled={mm === null || origem === null || ocupado} className={btn("primario", "xs")}>
          Salvar
        </button>
        <button type="button" onClick={() => setEditando(false)} className={btn("fantasma", "xs")}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
