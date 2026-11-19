import { useState } from "react";
import { api, ou, type Medida, type PavimentoTela, type Problema } from "../api/cliente";
import { useCatalogo, useEditar, useEstimadas, useProjeto } from "../dados";
import { formatar, paraMm, type Unidade } from "../unidades";
import { CampoMedida } from "./CampoMedida";

type ItemCatalogo = {
  tipo: string;
  nome: string;
  categoria: string;
  modelos: { id: string; nome: string; largura: number; profundidade: number; altura: number }[];
  modelo_padrao: string;
};

function Caixa({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-stone-200 p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">{titulo}</h2>
      {children}
    </section>
  );
}

const botao = "rounded border border-stone-300 px-2 py-0.5 text-sm hover:bg-stone-100 disabled:opacity-40";

// ------------------------------------------------------------------ móvel selecionado

export function PainelMovel({
  codigo,
  comodo,
  id,
  geometria,
  unidade,
  aoRemovido,
}: {
  codigo: string;
  comodo: string;
  id: string;
  geometria: PavimentoTela;
  unidade: Unidade;
  aoRemovido: () => void;
}) {
  const projeto = useProjeto(codigo).data;
  const editar = useEditar(codigo);
  const [parede, setParede] = useState("");
  const [distancia, setDistancia] = useState("0");
  const movel = projeto?.comodos[comodo]?.moveis?.find((m) => m.id === id);
  if (!movel) return null;
  const caminho = { codigo, comodo, id_: id };
  const paredesDoComodo = geometria.paredes.filter((p) => p.lado_a === comodo || p.lado_b === comodo);

  const mover = (corpo: { rotacao?: 0 | 90 | 180 | 270; parede?: string; distancia?: number }) =>
    editar.mutate((versao) =>
      ou(
        api.POST("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/mover", {
          params: { path: caminho, query: { versao } },
          body: corpo,
        }),
      ),
    );
  const alterar = (campo: string, m: Medida) =>
    editar.mutate((versao) =>
      ou(
        api.PATCH("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}", {
          params: { path: caminho, query: { versao } },
          body: { [campo]: m },
        }),
      ),
    );

  return (
    <Caixa titulo={`Móvel: ${movel.nome ?? movel.tipo}`}>
      <p className="mb-2 text-xs text-stone-500">
        {movel.tipo}
        {movel.modelo ? ` · ${movel.modelo}` : ""} · arraste na planta para mover
      </p>
      <div className="mb-2 flex flex-wrap gap-2">
        <button
          className={botao}
          disabled={editar.isPending}
          onClick={() => mover({ rotacao: (((movel.rotacao ?? 0) + 90) % 360) as 0 | 90 | 180 | 270 })}
        >
          girar 90°
        </button>
        <button
          className={`${botao} text-red-700`}
          disabled={editar.isPending}
          onClick={() =>
            editar.mutate(
              (versao) =>
                ou(
                  api.DELETE("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}", {
                    params: { path: caminho, query: { versao } },
                  }),
                ),
              { onSuccess: aoRemovido },
            )
          }
        >
          remover
        </button>
      </div>
      <form
        className="mb-2 flex flex-wrap items-center gap-1 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          const mm = paraMm(distancia, unidade);
          if (parede && mm !== null) mover({ parede, distancia: mm });
        }}
      >
        <span className="text-stone-500">encostar na</span>
        <select className="rounded border" value={parede} onChange={(e) => setParede(e.target.value)}>
          <option value="">parede…</option>
          {paredesDoComodo.map((p) => (
            <option key={p.id} value={p.id}>
              {p.id}
            </option>
          ))}
        </select>
        <span className="text-stone-500">a</span>
        <input className="w-16 rounded border px-1" value={distancia} onChange={(e) => setDistancia(e.target.value)} />
        <span className="text-stone-500">{unidade} do início</span>
        <button className={botao} disabled={!parede || editar.isPending}>
          ok
        </button>
      </form>
      {(["largura", "profundidade", "altura", "elevacao"] as const).map((campo) => (
        <CampoMedida
          key={campo}
          rotulo={campo}
          medida={movel[campo]}
          unidade={unidade}
          ocupado={editar.isPending}
          aoSalvar={(m) => alterar(campo, m)}
        />
      ))}
      {editar.error && <p className="mt-1 text-sm text-red-700">{editar.error.message}</p>}
    </Caixa>
  );
}

// ------------------------------------------------------------------ adicionar móvel

export function AdicionarMovel({ codigo, geometria }: { codigo: string; geometria: PavimentoTela }) {
  const catalogo = useCatalogo().data as { itens: ItemCatalogo[] } | undefined;
  const editar = useEditar(codigo);
  const comodos = geometria.comodos.filter((c) => c.centro);
  const [comodo, setComodo] = useState("");
  const [tipo, setTipo] = useState("");
  const [modelo, setModelo] = useState("");
  const item = catalogo?.itens.find((i) => i.tipo === tipo);
  const alvo = comodo || comodos[0]?.id || "";
  const centro = comodos.find((c) => c.id === alvo)?.centro;

  return (
    <Caixa titulo="Adicionar móvel">
      <div className="flex flex-col gap-1 text-sm">
        <select className="rounded border" value={alvo} onChange={(e) => setComodo(e.target.value)}>
          {comodos.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </select>
        <select
          className="rounded border"
          value={tipo}
          onChange={(e) => {
            setTipo(e.target.value);
            setModelo("");
          }}
        >
          <option value="">tipo…</option>
          {catalogo?.itens.map((i) => (
            <option key={i.tipo} value={i.tipo}>
              {i.nome}
            </option>
          ))}
        </select>
        {item && (
          <select className="rounded border" value={modelo || item.modelo_padrao} onChange={(e) => setModelo(e.target.value)}>
            {item.modelos.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nome} ({m.largura} × {m.profundidade} mm)
              </option>
            ))}
          </select>
        )}
        <button
          className={botao}
          disabled={!item || !centro || editar.isPending}
          onClick={() =>
            editar.mutate((versao) =>
              ou(
                api.POST("/projetos/{codigo}/comodos/{comodo}/moveis", {
                  params: { path: { codigo, comodo: alvo }, query: { versao } },
                  body: {
                    tipo,
                    modelo: modelo || null,
                    centro: [Math.round(centro![0]), Math.round(centro![1])],
                  },
                }),
              ),
            )
          }
        >
          pôr no centro do cômodo
        </button>
        <p className="text-xs text-stone-500">As medidas do catálogo entram como chute; ajuste depois.</p>
        {editar.error && <p className="text-red-700">{editar.error.message}</p>}
      </div>
    </Caixa>
  );
}

// ------------------------------------------------------------------ problemas e falta medir

const COR_SEV: Record<string, string> = {
  erro: "text-red-700",
  aviso: "text-amber-700",
  info: "text-stone-500",
};

export function PainelProblemas({ problemas, novos }: { problemas: Problema[]; novos: Problema[] }) {
  const chave = (p: Problema) => `${p.codigo}|${p.comodo}|${p.elemento}`;
  const recentes = new Set(novos.map(chave));
  return (
    <Caixa titulo={`Problemas (${problemas.length})`}>
      {problemas.length === 0 && <p className="text-sm text-stone-500">nenhum</p>}
      <ul className="space-y-1 text-sm">
        {problemas.map((p, i) => (
          <li key={i} className={COR_SEV[p.severidade]}>
            {recentes.has(chave(p)) && <span className="mr-1 rounded bg-red-100 px-1 text-xs">novo</span>}
            <b>{p.severidade}</b> {p.mensagem}
            {p.comodo && <span className="text-stone-400"> · {p.comodo}</span>}
          </li>
        ))}
      </ul>
    </Caixa>
  );
}

export function FaltaMedir({ codigo, unidade }: { codigo: string; unidade: Unidade }) {
  const estimadas = useEstimadas(codigo).data ?? [];
  const [aberto, setAberto] = useState(false);
  return (
    <Caixa titulo={`Falta medir (${estimadas.length})`}>
      {estimadas.length === 0 ? (
        <p className="text-sm text-emerald-700">tudo medido: os desenhos saem sem PRELIMINAR</p>
      ) : (
        <>
          <p className="text-sm text-amber-800">
            Enquanto houver chute, os desenhos saem PRELIMINAR — NÃO USAR PARA OBRA.
          </p>
          <button className="text-xs text-sky-700 hover:underline" onClick={() => setAberto(!aberto)}>
            {aberto ? "esconder" : "ver lista"}
          </button>
          {aberto && (
            <ul className="mt-1 max-h-64 space-y-0.5 overflow-auto text-xs">
              {estimadas.map((e) => (
                <li key={e.caminho}>
                  {e.entidade_codigo ?? e.entidade} · {e.campo}: {formatar(e.valor, unidade)}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Caixa>
  );
}
