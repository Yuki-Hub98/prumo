import { useEffect, useRef, useState } from "react";
import { api, ou } from "../api/cliente";
import { cotaSugerida, idDoAndar, LAJE_MM, nomeSugerido } from "../andares";
import { useEditar } from "../dados";
import { formatar, ORIGENS, type Origem, paraMm, type Unidade } from "../unidades";

type Pav = { id: string; nome?: string | null; cota_piso: { valor: number }; pe_direito: { valor: number } };

/** Botão "+ andar" no topo: nome, pé-direito e cota do piso (cada medida com a origem).
 * Cria o andar no fim e abre ele para desenhar as paredes. */
export function NovoAndar({
  codigo,
  pavimentos,
  atual,
  unidade,
  aoCriado,
}: {
  codigo: string;
  pavimentos: Pav[];
  atual: string;
  unidade: Unidade;
  aoCriado: (id: string) => void;
}) {
  const editar = useEditar(codigo);
  const [aberto, setAberto] = useState(false);
  const [nome, setNome] = useState("");
  const [pe, setPe] = useState("");
  const [cota, setCota] = useState("");
  const [origemPe, setOrigemPe] = useState<Origem | null>(null);
  const caixa = useRef<HTMLDivElement>(null);
  const base = pavimentos.find((p) => p.id === atual) ?? pavimentos[pavimentos.length - 1];

  const abrir = () => {
    setNome(nomeSugerido(pavimentos.length));
    setPe(base ? formatar(base.pe_direito.valor, unidade, false) : "");
    setCota(formatar(cotaSugerida(pavimentos), unidade, false));
    setOrigemPe(null);
    setAberto(true);
  };
  useEffect(() => {
    if (!aberto) return;
    const fora = (e: PointerEvent) => !caixa.current?.contains(e.target as Node) && setAberto(false);
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    document.addEventListener("pointerdown", fora);
    document.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("pointerdown", fora);
      document.removeEventListener("keydown", tecla);
    };
  }, [aberto]);

  const peMm = paraMm(pe, unidade);
  const cotaMm = paraMm(cota, unidade);
  const sugerida = cotaSugerida(pavimentos);
  const pronto = !!nome.trim() && !!peMm && cotaMm !== null && !!origemPe;
  const id = idDoAndar(nome, pavimentos.map((p) => p.id));

  return (
    <div className="relative" ref={caixa}>
      <button
        type="button"
        className="rounded border border-stone-300 px-2 py-0.5 text-sm hover:bg-stone-100"
        onClick={() => (aberto ? setAberto(false) : abrir())}
        aria-expanded={aberto}
        title="Criar um andar novo (sobrado, mezanino...)"
      >
        + andar
      </button>
      {aberto && (
        <form
          className="absolute left-0 top-full z-30 mt-1 grid w-72 gap-1.5 rounded-md border border-stone-300 bg-white p-3 text-sm shadow-lg"
          onSubmit={(e) => {
            e.preventDefault();
            if (!pronto) return;
            editar.mutate(
              (versao) =>
                ou(
                  api.POST("/projetos/{codigo}/pavimentos", {
                    params: { path: { codigo }, query: { versao } },
                    body: {
                      pavimento: {
                        id,
                        nome: nome.trim(),
                        pe_direito: { valor: peMm!, origem: origemPe! },
                        cota_piso:
                          cotaMm === sugerida
                            ? {
                                valor: cotaMm!,
                                origem: "estimada",
                                obs: `sugerida: piso + pé-direito do andar de baixo + laje de ${LAJE_MM} mm`,
                              }
                            : { valor: cotaMm!, origem: origemPe! },
                      },
                      depois_de: pavimentos[pavimentos.length - 1]?.id ?? null,
                    },
                  }),
                ),
              {
                onSuccess: () => {
                  setAberto(false);
                  aoCriado(id);
                },
              },
            );
          }}
        >
          <h3 className="text-xs font-semibold uppercase tracking-wide text-stone-500">Andar novo</h3>
          <label className="grid text-xs text-stone-500">
            nome
            <input className="rounded border px-1 text-sm text-stone-900" value={nome} onChange={(e) => setNome(e.target.value)} />
          </label>
          <div className="grid grid-cols-2 gap-1">
            <label className="grid min-w-0 text-xs text-stone-500">
              pé-direito ({unidade})
              <input className="w-full min-w-0 rounded border px-1 text-sm text-stone-900" inputMode="decimal" value={pe} onChange={(e) => setPe(e.target.value)} />
            </label>
            <label className="grid min-w-0 text-xs text-stone-500">
              cota do piso ({unidade})
              <input className="w-full min-w-0 rounded border px-1 text-sm text-stone-900" inputMode="decimal" value={cota} onChange={(e) => setCota(e.target.value)} />
            </label>
          </div>
          <p className="text-[11px] text-stone-500">
            Cota: altura do piso do andar novo em relação ao térreo; a sugerida soma a laje ({formatar(LAJE_MM, unidade)}) e
            entra como chute se você não mudar.
          </p>
          <div className="flex flex-wrap items-center gap-1 text-xs">
            <span className="text-stone-500">as medidas são:</span>
            {ORIGENS.map((o) => (
              <button
                key={o.valor}
                type="button"
                className={`rounded px-1.5 py-0.5 ${origemPe === o.valor ? "bg-stone-800 text-white" : "border border-stone-300"}`}
                onClick={() => setOrigemPe(o.valor)}
              >
                {o.rotulo}
              </button>
            ))}
          </div>
          <button className="rounded bg-stone-800 px-3 py-1 text-sm text-white disabled:opacity-40" disabled={!pronto || editar.isPending}>
            criar e desenhar as paredes
          </button>
          {editar.error && <p className="text-xs text-red-700">{editar.error.message}</p>}
        </form>
      )}
    </div>
  );
}
