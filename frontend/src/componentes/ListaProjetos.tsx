import { BotaoTema } from "./BotaoTema";
import { Logo } from "./Logo";
import { btn } from "../estilo";
import { useState } from "react";
import { api, ou } from "../api/cliente";
import { useProjetos, useSalvarUnidade, useUnidade } from "../dados";
import { paraMm, type Unidade } from "../unidades";
import { useQueryClient } from "@tanstack/react-query";

export function ListaProjetos({ aoAbrir }: { aoAbrir: (codigo: string) => void }) {
  const projetos = useProjetos();
  const unidade = useUnidade();
  const salvarUnidade = useSalvarUnidade();
  const qc = useQueryClient();
  const [codigo, setCodigo] = useState("");
  const [imovel, setImovel] = useState<"casa" | "apartamento">("casa");
  const [peDireito, setPeDireito] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  async function criar(e: React.FormEvent) {
    e.preventDefault();
    const mm = paraMm(peDireito, unidade);
    if (mm === null) return setErro("pé-direito inválido");
    try {
      await ou(
        api.POST("/projetos", {
          body: { codigo, imovel, pavimento: { pe_direito: { valor: mm, origem: "estimada" } } },
        }),
      );
      await qc.invalidateQueries({ queryKey: ["projetos"] });
      aoAbrir(codigo);
    } catch (x) {
      setErro((x as Error).message);
    }
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Logo altura={36} />
          <h1 className="text-2xl font-semibold">Projetos</h1>
        </div>
        <div className="flex items-center gap-2">
        <BotaoTema />
        <label className="text-sm text-tinta-suave">
          Unidade{" "}
          <select
            className="rounded-md border"
            value={unidade}
            onChange={(e) => salvarUnidade.mutate(e.target.value as Unidade)}
          >
            <option value="mm">mm</option>
            <option value="cm">cm</option>
            <option value="m">m</option>
          </select>
        </label>
        </div>
      </div>
      {projetos.error && (
        <p className="mb-4 rounded-md bg-erro-fundo p-3 text-erro">
          Não consegui falar com a API ({projetos.error.message}). Ela está rodando? <code>make api</code>
        </p>
      )}
      <ul className="mb-8 grid gap-3 sm:grid-cols-2">
        {projetos.data?.map((p) => (
          <li key={p.codigo}>
            <button
              className="w-full rounded-lg border border-linha bg-superficie p-4 text-left shadow-sm hover:border-linha-forte"
              onClick={() => aoAbrir(p.codigo)}
            >
              <div className="font-medium">{p.apelido ?? p.codigo}</div>
              <div className="text-xs text-tinta-suave">
                {p.codigo} · {p.imovel} · versão {p.versao}
              </div>
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={criar} className="rounded-lg border border-linha bg-superficie p-4">
        <h2 className="mb-3 font-medium">Novo projeto</h2>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="flex flex-col">
            Código
            <input
              className="rounded-md border px-1"
              placeholder="Ex.: ape-centro"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value.toLowerCase())}
            />
          </label>
          <label className="flex flex-col">
            Imóvel
            <select className="rounded-md border" value={imovel} onChange={(e) => setImovel(e.target.value as "casa")}>
              <option value="casa">Casa</option>
              <option value="apartamento">Apartamento</option>
            </select>
          </label>
          <label className="flex flex-col">
            Pé-direito ({unidade}, chute)
            <input className="w-24 rounded-md border px-1" value={peDireito} onChange={(e) => setPeDireito(e.target.value)} />
          </label>
          <button className={btn("primario", "sm")} disabled={!codigo || !peDireito}>
            Criar
          </button>
        </div>
        {erro && <p className="mt-2 text-sm text-erro">{erro}</p>}
      </form>
    </div>
  );
}
