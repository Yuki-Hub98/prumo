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

export function useCatalogo() {
  return useQuery({
    queryKey: ["catalogo"],
    queryFn: () => ou(api.GET("/catalogo")),
    staleTime: Infinity,
  });
}

/**
 * Edição sobre a versão que a tela tem. Tudo do projeto é recarregado depois; num
 * 409 (alguém gravou antes) a tela recarrega e a mensagem explica.
 */
export function useEditar(codigo: string) {
  const qc = useQueryClient();
  return useMutation<ResultadoEdicao, ErroApi, (versao: number) => Promise<ResultadoEdicao>>({
    mutationFn: async (fazer) => {
      const projeto = await qc.ensureQueryData({
        queryKey: chaves.projeto(codigo),
        queryFn: () => buscar.projeto(codigo),
      });
      return fazer(projeto.versao);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: chaves.projeto(codigo) }),
    onError: (e) => {
      if (e.status === 409)
        e.message = "Outra pessoa (ou aba) alterou o projeto antes. Recarreguei: confira e refaça.";
    },
  });
}
