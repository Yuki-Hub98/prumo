import { useState } from "react";
import { btn, opcao } from "../estilo";
import { api, ou, type Esquemas, type Medida } from "../api/cliente";
import { useEditar, usePlanejado } from "../dados";
import { type Unidade } from "../unidades";
import { CampoMedida } from "./CampoMedida";
import { Frente } from "./EditorPlanejado";
import { ListaDeCorte } from "./ListaDeCorte";

type Bancada = Esquemas["Bancada"];
type Modulo = Esquemas["ModuloBancada"];
type Trecho = "costas" | "braco";
type TipoModulo = "gaveteiro" | "nicho" | "armario";

const botao = btn("secundario", "xs");

const PERNAS: { id: Bancada["pernas"]; nome: string }[] = [
  { id: "metal", nome: "Metal 50 × 50" },
  { id: "madeira", nome: "Madeira" },
  { id: "painel", nome: "Painel nas pontas" },
];

const MATERIAIS = ["MDF branco", "MDF amadeirado", "MDF preto", "Granito", "Quartzo", "Madeira maciça"];

const NOME_MODULO: Record<TipoModulo, string> = { gaveteiro: "Gaveteiro", nicho: "Nicho", armario: "Armário" };

const estimada = (valor: number, obs: string): Medida => ({ valor, origem: "estimada", obs: `estimada: ${obs}` });

/** Módulo pronto (o mesmo do core: gaveteiro de 3 gavetas, nicho aberto, armário com porta). */
export function moduloPronto(id: string, tipo: TipoModulo, trecho: Trecho, distancia: number, largura: number): Modulo {
  const espacos =
    tipo === "gaveteiro"
      ? [{ tipo: "gaveta" as const }, { tipo: "gaveta" as const }, { tipo: "gaveta" as const }]
      : tipo === "nicho"
        ? [{ tipo: "nicho" as const }, { tipo: "nicho" as const }, { tipo: "nicho" as const }]
        : [{ tipo: "nicho" as const }, { tipo: "nicho" as const }];
  return {
    id,
    trecho,
    distancia: estimada(distancia, "posição do módulo"),
    largura: estimada(largura, `${tipo} de ${largura} mm`),
    portas: tipo === "armario" ? "abrir" : null,
    construcao: {
      chapa: { material: "MDF branco", espessura: estimada(18, "MDF 18 mm") },
      fundo: { material: "HDF branco", espessura: estimada(6, "fundo em HDF 6 mm") },
      rodape: estimada(80, "rodapé de 80 mm"),
      vaos: [{ espacos, porta: tipo === "armario" }],
    },
  };
}

/** Tipo do módulo pelo jeito que ele foi montado (para marcar o botão certo). */
export function tipoDoModulo(m: Modulo): TipoModulo | null {
  const espacos = m.construcao.vaos.flatMap((v) => v.espacos.map((e) => e.tipo));
  if (m.portas === "abrir") return "armario";
  if (espacos.length && espacos.every((t) => t === "gaveta")) return "gaveteiro";
  if (espacos.every((t) => t === "nicho")) return "nicho";
  return null;
}

/** Id livre para um módulo novo (gaveteiro, gaveteiro2, ...). */
export function idLivre(base: string, modulos: Modulo[]): string {
  const usados = new Set(modulos.map((m) => m.id));
  if (!usados.has(base)) return base;
  let n = 2;
  while (usados.has(`${base}${n}`)) n++;
  return `${base}${n}`;
}

/** Onde cabe um módulo novo de ``largura`` no trecho (mm da ponta), sem cobrir outro módulo
 * nem o ``canto`` do L (o canto fica com as pernas à vista). Prefere a ponta direita, depois a
 * esquerda, depois ao lado dos módulos que já existem; ``null`` se não couber. */
export function posicaoLivre(
  ocupados: [number, number][],
  comprimento: number,
  largura: number,
  canto: [number, number] | null,
): number | null {
  const folga = 30;
  const tudo = [...ocupados, ...(canto ? [canto] : [])];
  const candidatos = [
    comprimento - largura - folga,
    folga,
    ...tudo.flatMap(([a, b]) => [b + folga, a - largura - folga]),
  ];
  const cabe = (d: number) =>
    d >= 0 && d + largura <= comprimento && tudo.every(([a, b]) => d + largura <= a || d >= b);
  return candidatos.find(cabe) ?? null;
}

/** Bancada/mesa planejada: tampo, pernas, módulos embaixo e a vista de frente de cada trecho. */
export function EditorBancada({
  codigo,
  comodo,
  id,
  bancada,
  emL,
  ladoL,
  comprimentos,
  unidade,
}: {
  codigo: string;
  comodo: string;
  id: string;
  bancada: Bancada;
  emL: boolean;
  ladoL: "esquerda" | "direita";
  /** Comprimento de cada trecho (mm): costas e, no L, o braço; ``faixa`` = largura do L. */
  comprimentos: Record<Trecho | "faixa", number>;
  unidade: Unidade;
}) {
  const editar = useEditar(codigo);
  const vista = usePlanejado(codigo, comodo, id, true);
  const caminho = { codigo, comodo, id_: id };
  const gravar = (nova: Bancada) =>
    editar.mutate((versao) =>
      ou(
        api.PUT("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/bancada", {
          params: { path: caminho, query: { versao } },
          body: { bancada: nova },
        }),
      ),
    );
  const modulos = bancada.modulos ?? [];
  const mudarModulo = (i: number, campos: Partial<Modulo>) =>
    gravar({ ...bancada, modulos: modulos.map((m, j) => (j === i ? { ...m, ...campos } : m)) });
  const [semLugar, setSemLugar] = useState<string | null>(null);
  const adicionar = (tipo: TipoModulo, trecho: Trecho) => {
    const largura = tipo === "armario" ? 800 : 450;
    const comp = comprimentos[trecho];
    const ocupados = modulos
      .filter((m) => (m.trecho ?? "costas") === trecho)
      .map((m) => [m.distancia.valor, m.distancia.valor + m.largura.valor] as [number, number]);
    // nas costas do L, o canto (do lado do braço: à esquerda de quem olha, se o braço é à esquerda)
    const canto: [number, number] | null =
      emL && trecho === "costas"
        ? ladoL === "esquerda"
          ? [0, comprimentos.faixa]
          : [comp - comprimentos.faixa, comp]
        : null;
    const distancia = posicaoLivre(ocupados, comp, largura, canto);
    if (distancia === null) {
      setSemLugar(`Não cabe mais um ${NOME_MODULO[tipo].toLowerCase()} de ${largura / 10} cm neste trecho.`);
      return;
    }
    setSemLugar(null);
    gravar({ ...bancada, modulos: [...modulos, moduloPronto(idLivre(tipo, modulos), tipo, trecho, distancia, largura)] });
  };
  const ocupado = editar.isPending;
  const v = vista.data;

  return (
    <section className="border-b border-linha p-3">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-tinta-suave">Bancada planejada</h3>
      {v && (
        <div className="mb-2 space-y-1">
          <Frente vista={v} portas={false} />
          {emL && v.vistas?.braco && (
            <>
              <p className="text-xs text-tinta-suave">Braço do L, visto de dentro</p>
              <Frente vista={{ ...v, largura: comprimentos.braco, retangulos: v.vistas.braco }} portas={false} />
            </>
          )}
        </div>
      )}
      {vista.error && <p className="mb-2 text-sm text-erro">{vista.error.message}</p>}

      <div className="text-sm">
        <span className="text-tinta-suave">Tampo</span>
        <div className="mt-1 flex flex-wrap gap-1">
          {MATERIAIS.map((mat) => (
            <button
              key={mat}
              type="button"
              disabled={ocupado || bancada.tampo.material === mat}
              onClick={() => gravar({ ...bancada, tampo: { ...bancada.tampo, material: mat } })}
              className={`rounded-md px-2 py-0.5 text-xs ${opcao(bancada.tampo.material === mat)}`}
            >
              {mat}
            </button>
          ))}
        </div>
        <CampoMedida
          rotulo="Espessura do tampo"
          medida={bancada.tampo.espessura}
          unidade={unidade}
          ocupado={ocupado}
          aoSalvar={(m) => gravar({ ...bancada, tampo: { ...bancada.tampo, espessura: m } })}
        />
      </div>

      <div className="mt-2 text-sm">
        <span className="text-tinta-suave">Pernas</span>
        <div className="mt-1 flex flex-wrap gap-1">
          {PERNAS.map((p) => (
            <button
              key={p.id}
              type="button"
              disabled={ocupado || bancada.pernas === p.id}
              onClick={() => gravar({ ...bancada, pernas: p.id })}
              className={`rounded-md px-2 py-0.5 text-xs ${opcao(bancada.pernas === p.id)}`}
            >
              {p.nome}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-tinta-suave">
          Entram sozinhas onde o tampo não tem módulo embaixo: nas pontas, no canto do L e no meio de vão longo.
        </p>
      </div>

      <div className="mt-2 border-t border-linha pt-2 text-sm">
        <span className="text-tinta-suave">Módulos embaixo do tampo</span>
        {modulos.length === 0 && <p className="text-xs text-tinta-suave">Nenhum: só tampo e pernas.</p>}
        {modulos.map((m, i) => {
          const tipo = tipoDoModulo(m);
          return (
            <div key={m.id} className="mt-2 rounded-md border border-linha p-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{m.id}</span>
                <button
                  type="button"
                  className="text-xs text-erro hover:underline disabled:opacity-40"
                  disabled={ocupado}
                  onClick={() => gravar({ ...bancada, modulos: modulos.filter((_, j) => j !== i) })}
                >
                  remover
                </button>
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {(Object.keys(NOME_MODULO) as TipoModulo[]).map((t) => (
                  <button
                    key={t}
                    type="button"
                    disabled={ocupado || tipo === t}
                    onClick={() => {
                      const novo = moduloPronto(m.id, t, m.trecho ?? "costas", 0, 0);
                      mudarModulo(i, { portas: novo.portas, construcao: novo.construcao });
                    }}
                    className={`rounded-md px-2 py-0.5 text-xs ${opcao(tipo === t)}`}
                  >
                    {NOME_MODULO[t]}
                  </button>
                ))}
              </div>
              {emL && (
                <div className="mt-1 flex items-center gap-1 text-xs">
                  <span className="text-tinta-suave">Fica</span>
                  {(["costas", "braco"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      disabled={ocupado || (m.trecho ?? "costas") === t}
                      onClick={() => mudarModulo(i, { trecho: t })}
                      className={`rounded-md px-1.5 py-0.5 ${opcao((m.trecho ?? "costas") === t)}`}
                    >
                      {t === "costas" ? "nas costas" : "no braço do L"}
                    </button>
                  ))}
                </div>
              )}
              <CampoMedida
                rotulo={(m.trecho ?? "costas") === "braco" ? "Da ponta do braço" : "Da ponta esquerda"}
                medida={m.distancia}
                unidade={unidade}
                ocupado={ocupado}
                aoSalvar={(med) => mudarModulo(i, { distancia: med })}
              />
              <CampoMedida
                rotulo="Largura"
                medida={m.largura}
                unidade={unidade}
                ocupado={ocupado}
                aoSalvar={(med) => mudarModulo(i, { largura: med })}
              />
            </div>
          );
        })}
        <div className="mt-2 flex flex-wrap items-center gap-1">
          {(Object.keys(NOME_MODULO) as TipoModulo[]).map((t) => (
            <button key={t} className={botao} disabled={ocupado} onClick={() => adicionar(t, "costas")}>
              + {NOME_MODULO[t]}
            </button>
          ))}
          {emL && (
            <button className={botao} disabled={ocupado} onClick={() => adicionar("gaveteiro", "braco")}>
              + Gaveteiro no braço
            </button>
          )}
        </div>
      </div>
      {v && <ListaDeCorte codigo={codigo} comodo={comodo} id={id} vista={v} unidade={unidade} />}
      {semLugar && <p className="mt-1 text-sm text-erro">{semLugar}</p>}
      {editar.error && <p className="mt-1 text-sm text-erro">{editar.error.message}</p>}
    </section>
  );
}
