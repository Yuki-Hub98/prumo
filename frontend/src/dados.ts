import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, buscar, ErroApi, ou, type ResultadoEdicao } from "./api/cliente";
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

export function useGeometria(codigo: string, pavimento: string) {
  return useQuery({
    queryKey: [...chaves.projeto(codigo), "geometria", pavimento],
    queryFn: () => buscar.geometria(codigo, pavimento),
    placeholderData: (anterior) => anterior,
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

export function useEstimativas() {
  return useQuery({
    queryKey: ["estimativas"],
    queryFn: () => ou(api.GET("/renders/estimativas")),
  });
}

export function usePedirRender(codigo: string, comodo: string) {
  const qc = useQueryClient();
  return useMutation<unknown, ErroApi, { variacao: string; qualidade: "rascunho" | "final" }>({
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
