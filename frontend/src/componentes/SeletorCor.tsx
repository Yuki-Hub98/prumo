import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { HexColorPicker } from "react-colorful";
import { lerCor } from "../cores";

const LARGURA = 224;
const MARGEM = 8;

/** Onde abrir a janelinha: à esquerda do botão (a coluna fica na borda direita da tela),
 * sem sair da tela por cima, por baixo nem pela esquerda. */
export function posicaoJanela(
  botao: { left: number; right: number; top: number },
  janela: { largura: number; altura: number },
  tamanho: { largura: number; altura: number },
): { left: number; top: number } {
  let left = botao.left - tamanho.largura - MARGEM;
  if (left < MARGEM) left = Math.min(botao.right + MARGEM, janela.largura - tamanho.largura - MARGEM);
  const top = Math.min(Math.max(MARGEM, botao.top - 40), janela.altura - tamanho.altura - MARGEM);
  return { left: Math.max(MARGEM, left), top: Math.max(MARGEM, top) };
}

/** Um canal (0 a 255): digita livre; só aplica número válido e, fora de foco, mostra a cor atual. */
function CampoCanal({ valor, rotulo, aoMudar }: { valor: number; rotulo: string; aoMudar: (t: string) => void }) {
  const [texto, setTexto] = useState(String(valor));
  const [focado, setFocado] = useState(false);
  useEffect(() => {
    if (!focado) setTexto(String(valor));
  }, [valor, focado]);
  return (
    <input
      value={texto}
      inputMode="numeric"
      aria-label={rotulo}
      className="w-full rounded border border-stone-300 px-1 text-center font-mono text-xs"
      onFocus={() => setFocado(true)}
      onBlur={() => setFocado(false)}
      onChange={(e) => {
        setTexto(e.target.value);
        aoMudar(e.target.value);
      }}
    />
  );
}

const canais = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

/** Quadradinho de cor que abre um seletor dentro da página (degradê, matiz, R/G/B e as
 * cores já usadas). Troca o seletor do navegador, que abria cortado na borda da tela. */
export function SeletorCor({
  valor,
  rotulo,
  usadas,
  aoMudar,
}: {
  valor: string;
  rotulo: string;
  usadas: string[];
  aoMudar: (hex: string) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const botao = useRef<HTMLButtonElement>(null);
  const janela = useRef<HTMLDivElement>(null);
  const hex = (lerCor(valor) ?? "#000000").toLowerCase();

  useLayoutEffect(() => {
    if (!aberto || !botao.current || !janela.current) return;
    const b = botao.current.getBoundingClientRect();
    const j = janela.current.getBoundingClientRect();
    setPos(
      posicaoJanela(b, { largura: window.innerWidth, altura: window.innerHeight }, { largura: LARGURA, altura: j.height }),
    );
  }, [aberto]);

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: PointerEvent) => {
      const alvo = e.target as Node;
      if (!janela.current?.contains(alvo) && !botao.current?.contains(alvo)) setAberto(false);
    };
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setAberto(false);
        botao.current?.focus();
      }
    };
    // a coluna rola: a janelinha ficaria solta no lugar antigo
    const rolar = (e: Event) => {
      if (!janela.current?.contains(e.target as Node)) setAberto(false);
    };
    document.addEventListener("pointerdown", fora);
    document.addEventListener("keydown", tecla);
    window.addEventListener("scroll", rolar, true);
    window.addEventListener("resize", rolar);
    return () => {
      document.removeEventListener("pointerdown", fora);
      document.removeEventListener("keydown", tecla);
      window.removeEventListener("scroll", rolar, true);
      window.removeEventListener("resize", rolar);
    };
  }, [aberto]);

  const mudarCanal = (i: number, texto: string) => {
    const n = Number(texto);
    if (texto === "" || !Number.isInteger(n) || n < 0 || n > 255) return;
    const c = canais(hex);
    c[i] = n;
    aoMudar("#" + c.map((x) => x.toString(16).padStart(2, "0")).join(""));
  };

  return (
    <>
      <button
        ref={botao}
        type="button"
        aria-label={`cor de ${rotulo}`}
        aria-expanded={aberto}
        className="h-6 w-8 cursor-pointer rounded border border-stone-300"
        style={{ background: hex }}
        onClick={() => setAberto((a) => !a)}
      />
      {aberto &&
        createPortal(
          <div
            ref={janela}
            role="dialog"
            aria-label={`escolher a cor de ${rotulo}`}
            className="seletor-cor fixed z-50 grid gap-2 rounded-md border border-stone-300 bg-white p-2.5 shadow-lg"
            style={{ width: LARGURA, left: pos?.left ?? -9999, top: pos?.top ?? 0 }}
          >
            <span className="text-xs font-semibold uppercase tracking-wide text-stone-500">{rotulo}</span>
            <HexColorPicker color={hex} onChange={aoMudar} />
            <div className="grid grid-cols-3 gap-1">
              {["R", "G", "B"].map((nome, i) => (
                <label key={nome} className="grid text-center text-[10px] text-stone-500">
                  <CampoCanal valor={canais(hex)[i]} rotulo={`${rotulo}: ${nome}`} aoMudar={(t) => mudarCanal(i, t)} />
                  {nome}
                </label>
              ))}
            </div>
            {usadas.length > 0 && (
              <>
                <span className="text-[10px] uppercase tracking-wide text-stone-500">usadas neste cômodo</span>
                <div className="flex flex-wrap gap-1">
                  {usadas.map((c) => (
                    <button
                      key={c}
                      type="button"
                      aria-label={`usar ${c}`}
                      title={c}
                      className={`h-5 w-5 rounded border ${c === hex ? "border-stone-800 ring-1 ring-stone-800" : "border-stone-300"}`}
                      style={{ background: c }}
                      onClick={() => aoMudar(c)}
                    />
                  ))}
                </div>
              </>
            )}
          </div>,
          document.body,
        )}
    </>
  );
}
