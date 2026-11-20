/** Classes dos botões e alternadores da identidade visual (sem lib: só strings do Tailwind).
 *
 * - **primario** (amarelo trena): uma vez por tela, a ação principal ("Salvar", "Criar");
 * - **secundario**: ações comuns;
 * - **fantasma**: barras de ferramentas e ações discretas;
 * - **perigo**: remover/apagar.
 */

export type Variante = "primario" | "secundario" | "fantasma" | "perigo";
export type Tamanho = "xs" | "sm" | "md" | "lg";

const BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-md border font-semibold whitespace-nowrap transition-colors " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-foco " +
  "disabled:cursor-not-allowed disabled:opacity-45";

const VARIANTES: Record<Variante, string> = {
  primario: "border-trena-forte bg-trena text-trena-sobre hover:bg-trena-forte",
  secundario: "border-linha-forte bg-superficie text-tinta hover:bg-superficie-2",
  fantasma: "border-transparent bg-transparent text-tinta-suave hover:bg-superficie-2 hover:text-tinta",
  perigo: "border-erro bg-erro text-erro-sobre hover:brightness-95",
};

const TAMANHOS: Record<Tamanho, string> = {
  xs: "h-6 px-2 text-xs",
  sm: "h-7 px-3 text-sm",
  md: "h-9 px-4 text-sm",
  lg: "h-11 px-5 text-base",
};

export function btn(variante: Variante = "secundario", tamanho: Tamanho = "sm"): string {
  return `${BASE} ${VARIANTES[variante]} ${TAMANHOS[tamanho]}`;
}

/** Botão de alternar (grupo de opções, ferramenta): o ativo é escuro, nunca amarelo — o
 * amarelo fica para o que está selecionado na planta. */
export function alternar(ativo: boolean): string {
  return ativo
    ? "bg-tinta text-papel"
    : "text-tinta-suave hover:bg-superficie-2 hover:text-tinta";
}

/** Alternador com borda própria (opções soltas, fora de um grupo). */
export function opcao(ativo: boolean): string {
  return `rounded-md border ${ativo ? "border-tinta bg-tinta text-papel" : "border-linha-forte bg-superficie text-tinta hover:bg-superficie-2"}`;
}
