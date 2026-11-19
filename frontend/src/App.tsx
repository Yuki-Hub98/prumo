import { useEffect, useState } from "react";
import { ListaProjetos } from "./componentes/ListaProjetos";
import { TelaProjeto } from "./componentes/TelaProjeto";

/**
 * Endereço simples por hash, sem biblioteca de rotas:
 * ``#/p/<codigo>`` ou ``#/p/<codigo>?comodo=<id>&variacao=<nome>`` (abre já com o
 * cômodo e a variação de cor escolhidos — dá para mandar o link de uma opção).
 */
function projetoDoHash(): { codigo: string; comodo?: string; variacao?: string } | null {
  const m = window.location.hash.match(/^#\/p\/([a-z0-9][a-z0-9_-]*)(?:\?(.*))?$/);
  if (!m) return null;
  const q = new URLSearchParams(m[2] ?? "");
  return { codigo: m[1], comodo: q.get("comodo") ?? undefined, variacao: q.get("variacao") ?? undefined };
}

export function App() {
  const [local, setLocal] = useState(projetoDoHash);
  useEffect(() => {
    const ouvir = () => setLocal(projetoDoHash());
    window.addEventListener("hashchange", ouvir);
    return () => window.removeEventListener("hashchange", ouvir);
  }, []);
  const ir = (c: string | null) => (window.location.hash = c ? `/p/${c}` : "");
  return local ? (
    <TelaProjeto
      key={local.codigo}
      codigo={local.codigo}
      comodoInicial={local.comodo}
      variacaoInicial={local.variacao}
      aoVoltar={() => ir(null)}
    />
  ) : (
    <ListaProjetos aoAbrir={ir} />
  );
}
