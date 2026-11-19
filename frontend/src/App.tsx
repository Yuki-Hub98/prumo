import { useEffect, useState } from "react";
import { ListaProjetos } from "./componentes/ListaProjetos";
import { TelaProjeto } from "./componentes/TelaProjeto";

/** Endereço simples por hash (#/p/<codigo>), sem biblioteca de rotas. */
function projetoDoHash(): string | null {
  const m = window.location.hash.match(/^#\/p\/([a-z0-9][a-z0-9_-]*)$/);
  return m ? m[1] : null;
}

export function App() {
  const [codigo, setCodigo] = useState(projetoDoHash);
  useEffect(() => {
    const ouvir = () => setCodigo(projetoDoHash());
    window.addEventListener("hashchange", ouvir);
    return () => window.removeEventListener("hashchange", ouvir);
  }, []);
  const ir = (c: string | null) => (window.location.hash = c ? `/p/${c}` : "");
  return codigo ? (
    <TelaProjeto key={codigo} codigo={codigo} aoVoltar={() => ir(null)} />
  ) : (
    <ListaProjetos aoAbrir={ir} />
  );
}
