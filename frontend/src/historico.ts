/** Textos do histórico de versões (desfazer, refazer, voltar para uma versão). */

const NOMES: Record<string, string> = {
  importar: "Importou dos arquivos",
  criar_projeto: "Criou o projeto",
  renomear: "Renomeou o projeto",
  alterar_imovel: "Alterou o imóvel",
  adicionar_pavimento: "Adicionou pavimento",
  alterar_pavimento: "Alterou pavimento",
  remover_pavimento: "Removeu pavimento",
  adicionar_parede: "Desenhou parede",
  alterar_parede: "Alterou parede",
  dividir_parede: "Dividiu parede",
  remover_parede: "Removeu parede",
  mover_vertice: "Moveu canto",
  adicionar_abertura: "Adicionou porta/janela",
  alterar_abertura: "Alterou porta/janela",
  remover_abertura: "Removeu porta/janela",
  adicionar_comodo: "Criou cômodo",
  alterar_comodo: "Alterou cômodo",
  remover_comodo: "Removeu cômodo",
  adicionar_instalacao: "Adicionou instalação",
  alterar_instalacao: "Alterou instalação",
  remover_instalacao: "Removeu instalação",
  adicionar_movel: "Adicionou móvel",
  alterar_movel: "Alterou móvel",
  mover_movel: "Moveu móvel",
  remover_movel: "Removeu móvel",
  salvar_variacao: "Salvou cores",
  remover_variacao: "Removeu variação de cores",
};

const VOLTAS: Record<string, string> = {
  desfazer: "Desfez",
  refazer: "Refez",
  reverter: "Voltou",
};

/** "Moveu móvel", "Desfez (voltou à versão 9)", ou o nome cru se for desconhecido. */
export function nomeOperacao(operacao: string | null | undefined): string {
  if (!operacao) return "Alteração";
  const [tipo, para] = operacao.split(":");
  if (para !== undefined && VOLTAS[tipo]) return `${VOLTAS[tipo]} (conteúdo da versão ${para})`;
  return NOMES[operacao] ?? operacao.replaceAll("_", " ");
}

/** O que mudou, pelo caminho: ``comodos.quarto.moveis[cama]`` → ``quarto · cama``. */
export function resumoCaminho(caminho: string): string {
  const partes = [...caminho.matchAll(/\[([^\]]+)\]|\.?([^.[\]]+)/g)].map((m) => m[1] ?? m[2]);
  const nomes = partes.filter(
    (p) => !["projeto", "pavimentos", "comodos", "moveis", "paredes", "aberturas", "instalacoes", "variacoes"].includes(p),
  );
  return nomes.slice(0, 3).join(" · ") || caminho;
}
