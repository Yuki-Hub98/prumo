import createClient from "openapi-fetch";
import type { components, paths } from "./esquema";

export const URL_API: string = import.meta.env.VITE_API_URL ?? "http://localhost:8010";

export const api = createClient<paths>({ baseUrl: URL_API });

export type Esquemas = components["schemas"];
/** Medida enviada à API (mm inteiros + origem). */
export type Medida = Esquemas["Medida"];

/** Buscas tipadas; os tipos de resposta saem delas (iguais ao que a API devolve). */
export const buscar = {
  geometria: (codigo: string, pavimento: string) =>
    ou(
      api.GET("/projetos/{codigo}/pavimentos/{pavimento}/geometria", {
        params: { path: { codigo, pavimento } },
      }),
    ),
  problemas: (codigo: string) =>
    ou(api.GET("/projetos/{codigo}/problemas", { params: { path: { codigo } } })),
  projeto: (codigo: string) =>
    ou(api.GET("/projetos/{codigo}", { params: { path: { codigo } } })),
  variacoes: (codigo: string, comodo: string) =>
    ou(
      api.GET("/projetos/{codigo}/comodos/{comodo}/variacoes", {
        params: { path: { codigo, comodo } },
      }),
    ),
  renders: (codigo: string, comodo: string) =>
    ou(api.GET("/projetos/{codigo}/renders", { params: { path: { codigo }, query: { comodo } } })),
  moverMovel: (codigo: string, comodo: string, id_: string, versao: number, body: object) =>
    ou(
      api.POST("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/mover", {
        params: { path: { codigo, comodo, id_ }, query: { versao } },
        body,
      }),
    ),
};

export type PavimentoTela = Awaited<ReturnType<typeof buscar.geometria>>;
export type MovelTela = PavimentoTela["moveis"][number];
export type Problema = Awaited<ReturnType<typeof buscar.problemas>>[number];
export type ProjetoCompleto = Awaited<ReturnType<typeof buscar.projeto>>;
export type ResultadoEdicao = Awaited<ReturnType<typeof buscar.moverMovel>>;
export type Variacao = Awaited<ReturnType<typeof buscar.variacoes>>[string];
export type Cores = Esquemas["CoresVariacao"];
export type InfoRender = Awaited<ReturnType<typeof buscar.renders>>[number];

/** Erro da API num texto para mostrar (409 de versão, 422 de edição inválida...). */
export class ErroApi extends Error {
  constructor(
    mensagem: string,
    readonly status: number,
  ) {
    super(mensagem);
  }
}

export function mensagemDe(erro: unknown, status: number): ErroApi {
  const e = erro as { mensagem?: string; detail?: { msg: string; loc: string[] }[] | string };
  if (e?.mensagem) return new ErroApi(e.mensagem, status);
  if (Array.isArray(e?.detail))
    return new ErroApi(e.detail.map((d) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; "), status);
  return new ErroApi(typeof e?.detail === "string" ? e.detail : `erro ${status}`, status);
}

/** Desembrulha a resposta do openapi-fetch: dado ou exceção legível. */
export async function ou<T>(
  pedido: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await pedido;
  if (error !== undefined || data === undefined) throw mensagemDe(error, response.status);
  return data;
}
