import { Moon, Sun } from "lucide-react";
import { useState } from "react";
import { btn } from "../estilo";
import { aplicarTema, temaAtual, type Tema } from "../tema";

/** Alterna claro/escuro (fica salvo neste navegador). */
export function BotaoTema() {
  const [tema, setTema] = useState<Tema>(temaAtual);
  const outro: Tema = tema === "escuro" ? "claro" : "escuro";
  return (
    <button
      type="button"
      className={btn("fantasma", "sm")}
      title={outro === "escuro" ? "Tema escuro" : "Tema claro"}
      aria-label={outro === "escuro" ? "Mudar para o tema escuro" : "Mudar para o tema claro"}
      onClick={() => {
        aplicarTema(outro, true);
        setTema(outro);
        window.dispatchEvent(new Event("prumo-tema"));
      }}
    >
      {tema === "escuro" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
