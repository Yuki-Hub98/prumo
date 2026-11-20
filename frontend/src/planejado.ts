/** Editar a construção de um móvel planejado (vãos e espaços), sem mudar o original.
 *
 * Quem confere se cabe (larguras, alturas, gavetas) é o core, ao gravar: aqui só se monta
 * o pedido. Medida digitada aqui é de projeto ("quero assim"); vazio = divide o que sobra.
 */

import type { Esquemas } from "./api/cliente";

export type Construcao = Esquemas["Construcao"];
export type Vao = Esquemas["Vao"];
export type TipoEspaco = Esquemas["Espaco"]["tipo"];

export const TIPOS_ESPACO: { id: TipoEspaco; nome: string }[] = [
  { id: "nicho", nome: "Nicho / prateleira" },
  { id: "gaveta", nome: "Gaveta" },
  { id: "cabideiro", nome: "Cabideiro" },
];

const medida = (mm: number | null) => (mm === null ? null : { valor: mm, origem: "projeto" as const });

function copiar(c: Construcao): Construcao {
  return { ...c, vaos: c.vaos.map((v) => ({ ...v, espacos: v.espacos.map((e) => ({ ...e })) })) };
}

function mudarVao(c: Construcao, i: number, f: (v: Vao) => Vao): Construcao {
  const n = copiar(c);
  n.vaos[i] = f(n.vaos[i]);
  return n;
}

export function adicionarVao(c: Construcao): Construcao {
  const n = copiar(c);
  n.vaos.push({ espacos: [{ tipo: "nicho" }, { tipo: "nicho" }], porta: true });
  return n;
}

/** Tira o vão ``i`` (o móvel precisa de pelo menos um). */
export function removerVao(c: Construcao, i: number): Construcao {
  if (c.vaos.length <= 1) return c;
  const n = copiar(c);
  n.vaos.splice(i, 1);
  return n;
}

export function alternarPorta(c: Construcao, i: number): Construcao {
  return mudarVao(c, i, (v) => ({ ...v, porta: v.porta === false }));
}

/** Largura livre do vão em mm; ``null`` divide igualmente o que sobra. */
export function larguraVao(c: Construcao, i: number, mm: number | null): Construcao {
  return mudarVao(c, i, (v) => ({ ...v, largura: medida(mm) }));
}

export function adicionarEspaco(c: Construcao, i: number, tipo: TipoEspaco): Construcao {
  return mudarVao(c, i, (v) => ({ ...v, espacos: [...v.espacos, { tipo }] }));
}

/** Tira o espaço ``j`` do vão ``i`` (o vão precisa de pelo menos um). */
export function removerEspaco(c: Construcao, i: number, j: number): Construcao {
  if (c.vaos[i].espacos.length <= 1) return c;
  return mudarVao(c, i, (v) => ({ ...v, espacos: v.espacos.filter((_, k) => k !== j) }));
}

export function tipoEspaco(c: Construcao, i: number, j: number, tipo: TipoEspaco): Construcao {
  return mudarVao(c, i, (v) => ({ ...v, espacos: v.espacos.map((e, k) => (k === j ? { ...e, tipo } : e)) }));
}

/** Altura do espaço em mm; ``null`` divide o que sobra no vão. */
export function alturaEspaco(c: Construcao, i: number, j: number, mm: number | null): Construcao {
  return mudarVao(c, i, (v) => ({
    ...v,
    espacos: v.espacos.map((e, k) => (k === j ? { ...e, altura: medida(mm) } : e)),
  }));
}

/** Sobe (``+1``) ou desce (``-1``) o espaço dentro do vão (a lista é de baixo para cima). */
export function moverEspaco(c: Construcao, i: number, j: number, passo: 1 | -1): Construcao {
  const k = j + passo;
  if (k < 0 || k >= c.vaos[i].espacos.length) return c;
  return mudarVao(c, i, (v) => {
    const espacos = [...v.espacos];
    [espacos[j], espacos[k]] = [espacos[k], espacos[j]];
    return { ...v, espacos };
  });
}
