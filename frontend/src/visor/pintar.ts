/** Pintar o modelo 3D ao vivo com as cores do painel (rascunho da variação).
 *
 * O .glb do render tem nomes previsíveis (``cena.py``): ``piso``, ``teto``, ``rodape-N``,
 * ``parede-<id>-N``, ``peitoril-<abertura>``, ``verga-<abertura>`` e, nos móveis, o material
 * ``movel-<id>``. No modelo do pavimento inteiro piso, teto e rodapé levam ``-<cômodo>`` no
 * fim. Pintar pelo objeto (não pelo material) deixa cada parede ter a sua cor.
 *
 * Modelos a partir da cena v8 trazem em cada peça de móvel ``movel`` e ``parte`` (extras do
 * glTF) e, com cor de parte, o material ``<base>@<móvel>@<parte>``: dá para pintar portas,
 * gavetas, travesseiros... e voltar à cor da base quando a parte fica sem cor.
 */

import type { Cores } from "../api/cliente";

export type Papel =
  | { tipo: "piso" | "teto" | "rodape" }
  | { tipo: "parede"; parede: string }
  | {
      tipo: "movel";
      id: string;
      /** ``corpo`` ou uma parte (``portas``, ``gavetas``...). */
      parte: string;
      /** A peça usa o material do móvel (sem cor de parte, fica com a cor geral dele). */
      doCorpo: boolean;
    };

/** O que o render grava em cada peça de móvel (extras do glTF). */
export type Extras = { movel?: unknown; parte?: unknown };

export type Contexto = {
  /** Cômodo pintado. */
  comodo: string;
  /** Modelo do pavimento inteiro (nomes com ``-<cômodo>``; paredes não são pintadas). */
  pavimento: boolean;
  /** Abertura → parede onde ela fica (peitoril e verga são pedaços da parede). */
  aberturas: Record<string, string>;
  /** Móveis do cômodo: id → tipo (a cor pode vir pelo tipo). */
  moveis: Record<string, string>;
};

/** O que é este objeto do modelo, para o cômodo do contexto (``null`` = não se pinta). */
export function papel(objeto: string, material: string, ctx: Contexto, extras: Extras = {}): Papel | null {
  if (typeof extras.movel === "string") {
    const id = extras.movel;
    if (!(id in ctx.moveis)) return null;
    const parte = typeof extras.parte === "string" ? extras.parte : "corpo";
    const doCorpo = material.split("@")[0] === `movel-${id}`;
    if (parte === "corpo" && !doCorpo) return null; // sombra do rodapé, colchão sem parte...
    return { tipo: "movel", id, parte, doCorpo };
  }
  const mov = /^movel-(.+)$/.exec(material); // modelos antigos: só o corpo
  if (mov) return mov[1] in ctx.moveis ? { tipo: "movel", id: mov[1], parte: "corpo", doCorpo: true } : null;

  let nome = objeto;
  if (ctx.pavimento) {
    const fim = `-${ctx.comodo}`;
    if (!nome.endsWith(fim)) return null;
    nome = nome.slice(0, -fim.length);
  }
  if (nome === "piso" || nome === "teto") return { tipo: nome };
  if (/^rodape-\d+$/.test(nome)) return { tipo: "rodape" };
  // a parede do pavimento é uma peça só entre dois cômodos: pintar um lado pintaria o outro
  if (ctx.pavimento) return null;
  const par = /^parede-(.+)-\d+$/.exec(objeto);
  if (par) return { tipo: "parede", parede: par[1] };
  const vao = /^(?:peitoril|verga)-(.+)$/.exec(objeto);
  if (vao && ctx.aberturas[vao[1]]) return { tipo: "parede", parede: ctx.aberturas[vao[1]] };
  return null;
}

/** Móvel de uma peça do modelo: pelo material ``movel-<id>`` ou pelo nome ``<id>-<peça>``
 * (colchão, travesseiro e puxador têm material próprio). O id mais longo vence. */
export function movelDaPeca(objeto: string, material: string, ids: string[]): string | null {
  const m = /^movel-(.+)$/.exec(material);
  if (m && ids.includes(m[1])) return m[1];
  const achados = ids.filter((id) => objeto.startsWith(`${id}-`));
  return achados.sort((a, b) => b.length - a.length)[0] ?? null;
}

/** Cor do rascunho para o papel, ou ``null`` (fica a cor com que o modelo foi gerado). */
export function corDo(p: Papel, cores: Cores, ctx: Contexto): string | null {
  switch (p.tipo) {
    case "piso":
      return cores.piso ?? null;
    case "teto":
      return cores.teto ?? null;
    case "rodape":
      return cores.rodape ?? null;
    case "parede":
      return cores.paredes?.[p.parede] ?? cores.parede ?? null;
    case "movel": {
      const tipo = ctx.moveis[p.id];
      if (p.parte !== "corpo") {
        const daParte = cores.pecas?.[p.id]?.[p.parte] ?? cores.pecas?.[tipo]?.[p.parte];
        if (daParte) return daParte;
        if (!p.doCorpo) return null;
      }
      return cores.moveis?.[p.id] ?? cores.moveis?.[tipo] ?? null;
    }
  }
}
