import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, buscar, ErroApi, type Esquemas, ou, type ResultadoEdicao } from "./api/cliente";
import type { Unidade } from "./unidades";

export const chaves = {
  projetos: ["projetos"] as const,
  projeto: (p: string) => ["projeto", p] as const,
};

export function usePreferencias() {
  return useQuery({ queryKey: ["preferencias"], queryFn: () => ou(api.GET("/preferencias")) });
}

export function useUnidade(): Unidade {
  return usePreferencias().data?.unidade ?? "cm";
}

export function useSalvarUnidade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (unidade: Unidade) => ou(api.PATCH("/preferencias", { body: { unidade } })),
    onSuccess: (dados) => qc.setQueryData(["preferencias"], dados),
  });
}

export function useProjetos() {
  return useQuery({ queryKey: chaves.projetos, queryFn: () => ou(api.GET("/projetos")) });
}

export function useProjeto(codigo: string) {
  return useQuery({
    queryKey: chaves.projeto(codigo),
    queryFn: () => buscar.projeto(codigo),
  });
}

export function useGeometria(codigo: string, pavimento: string, ativo = true) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "geometria", pavimento],
    queryFn: () => buscar.geometria(codigo, pavimento),
    placeholderData: (anterior) => anterior,
    enabled: ativo,
  });
}

export function useProblemas(codigo: string) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "problemas"],
    queryFn: () => buscar.problemas(codigo),
  });
}

export function useEstimadas(codigo: string) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "estimadas"],
    queryFn: () =>
      ou(api.GET("/projetos/{codigo}/estimadas", { params: { path: { codigo } } })),
  });
}

/** Versões do projeto e para onde o desfazer/refazer levariam (recarrega a cada edição). */
export function useVersoes(codigo: string) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "versoes"],
    queryFn: () => ou(api.GET("/projetos/{codigo}/versoes", { params: { path: { codigo } } })),
  });
}

/** Móveis guardados como modelo próprio (valem para todos os projetos). */
export function useModelosProprios() {
  return useQuery({
    queryKey: ["modelos-proprios"],
    queryFn: () => ou(api.GET("/modelos-proprios")),
  });
}

/** Portas e janelas prontas (tipos e tamanhos comerciais). */
export function useCatalogoAberturas() {
  return useQuery({
    queryKey: ["catalogo", "aberturas"],
    queryFn: () => ou(api.GET("/catalogo/aberturas")),
    staleTime: Infinity,
  });
}

export function useCatalogo() {
  return useQuery({
    queryKey: ["catalogo"],
    queryFn: () => ou(api.GET("/catalogo")),
    staleTime: Infinity,
  });
}

/** Fila de edições por projeto: uma de cada vez (desenhar paredes em sequência rápida
 * não pode mandar duas edições sobre a mesma versão). */
const filas = new Map<string, Promise<unknown>>();

/**
 * Edição sobre a versão que a tela tem. As edições do mesmo projeto vão em fila, cada
 * uma com a versão devolvida pela anterior. Tudo do projeto é recarregado depois; num
 * 409 (outra aba gravou antes) a tela recarrega e a mensagem explica.
 */
export function useEditar(codigo: string) {
  const qc = useQueryClient();
  return useMutation<ResultadoEdicao, ErroApi, (versao: number) => Promise<ResultadoEdicao>>({
    mutationFn: (fazer) => {
      const anterior = filas.get(codigo) ?? Promise.resolve();
      const esta = anterior
        .catch(() => undefined)
        .then(async () => {
          const projeto = await qc.ensureQueryData({
            queryKey: chaves.projeto(codigo),
            queryFn: () => buscar.projeto(codigo),
          });
          const r = await fazer(projeto.versao);
          qc.setQueryData(chaves.projeto(codigo), { ...projeto, versao: r.versao });
          return r;
        });
      filas.set(codigo, esta);
      return esta;
    },
    onSettled: () => qc.invalidateQueries({ queryKey: chaves.projeto(codigo) }),
    onError: (e) => {
      if (e.status === 409)
        e.message = "Outra pessoa (ou aba) alterou o projeto antes. Recarreguei: confira e refaça.";
    },
  });
}

export function useVariacoes(codigo: string, comodo: string | null) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "variacoes", comodo],
    queryFn: () => buscar.variacoes(codigo, comodo!),
    enabled: comodo !== null,
  });
}

const ATIVO = new Set(["na_fila", "rodando"]);

/** Renders do cômodo; enquanto algum estiver na fila/rodando, atualiza a cada segundo. */
export function useRenders(codigo: string, comodo: string) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "renders", comodo],
    queryFn: () => buscar.renders(codigo, comodo),
    refetchInterval: (q) => (q.state.data?.some((r) => ATIVO.has(r.status)) ? 1000 : false),
  });
}

/** Renders do pavimento inteiro (modelo 3D da casa com o teto cortado). */
export function useRendersPavimento(codigo: string, pavimento: string, ativo = true) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "renders-pavimento", pavimento],
    queryFn: () => buscar.rendersPavimento(codigo, pavimento),
    enabled: ativo,
    refetchInterval: (q) => (q.state.data?.some((r) => ATIVO.has(r.status)) ? 1000 : false),
  });
}

export function usePedirRenderPavimento(codigo: string, pavimento: string) {
  const qc = useQueryClient();
  return useMutation<unknown, ErroApi, { qualidade: "rascunho" | "final" }>({
    mutationFn: (corpo) =>
      ou(
        api.POST("/projetos/{codigo}/pavimentos/{pavimento}/renders", {
          params: { path: { codigo, pavimento } },
          body: corpo,
        }),
      ),
    onSettled: () =>
      qc.invalidateQueries({ queryKey: [...chaves.projeto(codigo), "renders-pavimento", pavimento] }),
  });
}

/** Cena 3D ao vivo do cômodo ou do pavimento (refaz a cada versão do projeto). */
/** Cena 3D ao vivo do cômodo, do pavimento ou da casa toda (os andares empilhados). */
export function useCena(codigo: string, alvo: { comodo: string } | { pavimento: string } | { casa: true }, ativo = true) {
  const chave = "casa" in alvo ? ["casa", "toda"] : "pavimento" in alvo ? ["pavimento", alvo.pavimento] : ["comodo", alvo.comodo];
  return useQuery<Esquemas["Cena3D"], ErroApi>({
    queryKey: [...chaves.projeto(codigo), "cena", ...chave],
    // o openapi-fetch tipa pares/trincas como listas: a forma é a do esquema Cena3D
    queryFn: async () => {
      const r =
        "casa" in alvo
          ? await ou(api.GET("/projetos/{codigo}/cena", { params: { path: { codigo } } }))
          : "pavimento" in alvo
          ? await ou(api.GET("/projetos/{codigo}/pavimentos/{pavimento}/cena", { params: { path: { codigo, pavimento: alvo.pavimento } } }))
          : await ou(api.GET("/projetos/{codigo}/comodos/{comodo}/cena", { params: { path: { codigo, comodo: alvo.comodo } } }));
      return r as unknown as Esquemas["Cena3D"];
    },
    enabled: ativo,
    placeholderData: (anterior, consulta) =>
      // enquanto a versão nova chega, mostra a anterior do mesmo cômodo (sem piscar)
      consulta?.queryKey.slice(-2).join() === chave.join() ? anterior : undefined,
  });
}

/** Tinta do pavimento com a variação escolhida em cada cômodo (refaz a cada versão). */
export function useTinta(codigo: string, pavimento: string, escolhas: Record<string, string>) {
  const variacao = Object.entries(escolhas)
    .filter(([, v]) => v !== "base")
    .map(([c, v]) => `${c}:${v}`)
    .sort();
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "tinta", pavimento, ...variacao],
    queryFn: () =>
      ou(
        api.GET("/projetos/{codigo}/pavimentos/{pavimento}/tinta", {
          params: { path: { codigo, pavimento }, query: { variacao } },
        }),
      ),
    placeholderData: (anterior) => anterior,
  });
}

/** Vista de frente calculada de um móvel planejado (atualiza junto com o projeto). */
export function usePlanejado(codigo: string, comodo: string, id: string, ativo: boolean) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "planejado", comodo, id],
    queryFn: () =>
      ou(
        api.GET("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/planejado", {
          params: { path: { codigo, comodo, id_: id } },
        }),
      ),
    enabled: ativo,
  });
}

/** Segundos estimados (rascunho, final) para ``imagens`` vistas, pelo histórico da máquina. */
export function useEstimativas(imagens = 2) {
  return useQuery({
    queryKey: ["estimativas", imagens],
    queryFn: () => ou(api.GET("/renders/estimativas", { params: { query: { imagens } } })),
    placeholderData: (anterior) => anterior,
  });
}

/** Câmeras que fazem sentido no cômodo (perspectiva, porta, cama, canto-N, superior). */
export function useVistas(codigo: string, comodo: string) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "vistas", comodo],
    queryFn: () =>
      ou(api.GET("/projetos/{codigo}/comodos/{comodo}/vistas", { params: { path: { codigo, comodo } } })),
  });
}

export function usePedirRender(codigo: string, comodo: string) {
  const qc = useQueryClient();
  return useMutation<unknown, ErroApi, { variacao: string; qualidade: "rascunho" | "final"; vistas: string[] }>({
    mutationFn: (corpo) =>
      ou(
        api.POST("/projetos/{codigo}/comodos/{comodo}/renders", {
          params: { path: { codigo, comodo } },
          body: corpo,
        }),
      ),
    onSettled: () => qc.invalidateQueries({ queryKey: [...chaves.projeto(codigo), "renders", comodo] }),
  });
}
