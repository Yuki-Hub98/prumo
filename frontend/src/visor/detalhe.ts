/** "Editar em detalhe": o móvel sozinho no 3D, no referencial dele, com alças para puxar.
 *
 * Referencial do detalhe (metros, three): centro do móvel na origem do piso, sem o giro da
 * planta. x = x local do móvel (+x é o lado "direita" do redimensionar), y para cima e
 * z = −y local: a frente do móvel (+y local) fica em −z.
 */

import type { Cena3D } from "./montarCena";

export type Alca = "largura" | "profundidade" | "altura";

type V3 = [number, number, number];

/** Medidas do móvel em mm (``base`` = elevação: o fundo fica parado ao puxar a altura). */
export type Medidas = { largura: number; profundidade: number; altura: number; base: number };

const M = 0.001;
/** Passo do arrastar: 1 cm, como na planta. */
export const PASSO_MM = 10;
/** Menor medida aceita (a mesma do redimensionar da API). */
export const MINIMO_MM = 100;

/** Só as peças do móvel ``id`` (prismas e caixas marcados com ``movel``). */
export function cenaDoMovel(cena: Cena3D, id: string): Cena3D {
  const doMovel = (p: { extras?: Record<string, string> | null }) => p.extras?.movel === id;
  return { ...cena, prismas: cena.prismas.filter(doMovel), caixas: cena.caixas.filter(doMovel) };
}

/** Onde fica cada alça (m): no meio da face que ela puxa, na caixa atual do móvel. */
export function pontoDaAlca(alca: Alca, c: { min: V3; max: V3 }): V3 {
  const meio = (i: number) => (c.min[i] + c.max[i]) / 2;
  if (alca === "largura") return [c.max[0], meio(1), meio(2)];
  if (alca === "profundidade") return [meio(0), meio(1), c.min[2]];
  return [meio(0), c.max[1], meio(2)];
}

/** Eixo em que cada alça anda (unitário). */
export function eixoAlca(alca: Alca): [number, number, number] {
  return alca === "largura" ? [1, 0, 0] : alca === "profundidade" ? [0, 0, -1] : [0, 1, 0];
}

const sub = (a: V3, b: V3): V3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: V3, b: V3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

/**
 * Ponto do eixo (``origem + t · eixo``) mais perto do raio do mouse (``raio + s · direcao``):
 * devolve ``t`` em metros. Raio paralelo ao eixo: ``null`` (não dá para saber para onde puxou).
 */
export function tNoEixo(origem: V3, eixo: V3, raio: V3, direcao: V3): number | null {
  const w = sub(origem, raio);
  const a = dot(eixo, eixo);
  const b = dot(eixo, direcao);
  const c = dot(direcao, direcao);
  const d = dot(eixo, w);
  const e = dot(direcao, w);
  const den = a * c - b * b;
  if (Math.abs(den) < 1e-9) return null;
  return (b * e - c * d) / den;
}

/** Medida nova depois de a alça andar ``t`` metros pelo eixo (lado oposto parado), em
 * passos de 1 cm e nunca abaixo do mínimo. */
export function medidaPuxada(alca: Alca, inicial: Medidas, t: number): number {
  const antes = inicial[alca];
  const bruto = antes + t / M;
  return Math.max(MINIMO_MM, Math.round(bruto / PASSO_MM) * PASSO_MM);
}

/** Caixa (m) que o móvel ocupa com as medidas ``m``, do lado oposto das alças parado:
 * esquerda em x = −largura/2 do original, costas em z = +profundidade/2 e base no piso. */
export function caixaPuxada(original: Medidas, m: Medidas): { min: V3; max: V3 } {
  const x0 = -(original.largura / 2) * M;
  const z1 = (original.profundidade / 2) * M;
  return {
    min: [x0, m.base * M, z1 - m.profundidade * M],
    max: [x0 + m.largura * M, (m.base + m.altura) * M, z1],
  };
}

// ------------------------------------------------------------------ porta e janela

/** Alças do vão: ``fim``/``inicio`` = os lados ao longo da parede, ``altura`` = em cima,
 * ``peitoril`` = embaixo (só janela). */
export type AlcaAbertura = "fim" | "inicio" | "altura" | "peitoril";

/** Vão em mm: ``inicio`` = distância do início da parede; ``peitoril`` = 0 na porta. */
export type MedidasAbertura = { inicio: number; largura: number; altura: number; peitoril: number };

/** Só o trecho de parede ``parede`` e as peças de abertura nela (marcados pelo render). */
export function cenaDaParede(cena: Cena3D, parede: string): Cena3D {
  const daParede = (p: { extras?: Record<string, string> | null }) => p.extras?.parede === parede;
  return { ...cena, prismas: cena.prismas.filter(daParede), caixas: cena.caixas.filter(daParede) };
}

/**
 * Referencial do vão (m): centro do vão **original** no eixo da parede, x ao longo da parede
 * (do início para o fim), y para cima e z = −normal: o lado ``a`` da parede fica em −z.
 * Caixa do vão com as medidas ``m`` (a parede inteira na espessura).
 */
export function caixaAbertura(original: MedidasAbertura, m: MedidasAbertura, espessura: number): { min: V3; max: V3 } {
  const x0 = (m.inicio - original.inicio - original.largura / 2) * M;
  return {
    min: [x0, m.peitoril * M, -(espessura / 2) * M],
    max: [x0 + m.largura * M, (m.peitoril + m.altura) * M, (espessura / 2) * M],
  };
}

/** Alça no meio da borda do vão, na face da parede do lado da câmera (``lado`` = sinal de z). */
export function pontoAlcaAbertura(alca: AlcaAbertura, c: { min: V3; max: V3 }, lado: 1 | -1): V3 {
  const z = lado > 0 ? c.max[2] : c.min[2];
  const mx = (c.min[0] + c.max[0]) / 2;
  const my = (c.min[1] + c.max[1]) / 2;
  if (alca === "fim") return [c.max[0], my, z];
  if (alca === "inicio") return [c.min[0], my, z];
  if (alca === "altura") return [mx, c.max[1], z];
  return [mx, c.min[1], z];
}

export function eixoAlcaAbertura(alca: AlcaAbertura): V3 {
  return alca === "fim" ? [1, 0, 0] : alca === "inicio" ? [-1, 0, 0] : alca === "altura" ? [0, 1, 0] : [0, -1, 0];
}

/**
 * Vão depois de a alça andar ``t`` metros para fora (passos de 1 cm), com a borda oposta
 * parada: puxar o ``inicio`` muda a distância e a largura; puxar o ``peitoril``, o peitoril e
 * a altura. Largura e altura nunca abaixo do mínimo; distância e peitoril nunca negativos.
 */
export function aberturaPuxada(alca: AlcaAbertura, a: MedidasAbertura, t: number): MedidasAbertura {
  const d = Math.round(t / M / PASSO_MM) * PASSO_MM;
  if (alca === "fim") return { ...a, largura: Math.max(MINIMO_MM, a.largura + d) };
  if (alca === "altura") return { ...a, altura: Math.max(MINIMO_MM, a.altura + d) };
  if (alca === "inicio") {
    const dd = Math.min(Math.max(d, MINIMO_MM - a.largura), a.inicio);
    return { ...a, inicio: a.inicio - dd, largura: a.largura + dd };
  }
  const dd = Math.min(Math.max(d, MINIMO_MM - a.altura), a.peitoril);
  return { ...a, peitoril: a.peitoril - dd, altura: a.altura + dd };
}

// ------------------------------------------------------------------ partes do planejado

/** Elemento da vista de frente do planejado (mm, x da esquerda de quem olha, y do chão do móvel). */
export type Regiao = { tipo: string; x: number; y: number; largura: number; altura: number; vao?: number | null; espaco?: number | null };

/** Espaço ``espaco`` (de baixo para cima) do vão ``vao`` (da esquerda de quem olha). */
export type Parte = { vao: number; espaco: number };

const ESPACOS = new Set(["gaveta", "nicho", "cabideiro"]);

/** Regiões clicáveis: os espaços e as prateleiras (que escolhem o espaço logo abaixo). */
export function regioesClicaveis(rs: Regiao[]): (Regiao & Parte)[] {
  return rs.filter((r): r is Regiao & Parte => (ESPACOS.has(r.tipo) || r.tipo === "prateleira") && r.vao != null && r.espaco != null);
}

export function regiaoDoEspaco(rs: Regiao[], p: Parte): Regiao | undefined {
  return rs.find((r) => ESPACOS.has(r.tipo) && r.vao === p.vao && r.espaco === p.espaco);
}

/** Retângulo da vista de frente no 3D do detalhe: na frente do móvel (−z), com a esquerda de
 * quem olha em +x (como o render: x = largura/2 − u). Centro e tamanho em m. */
export function naFrente(r: Pick<Regiao, "x" | "y" | "largura" | "altura">, m: Medidas, afastar = 4): { centro: V3; tamanho: [number, number] } {
  const x1 = (m.largura / 2 - r.x) * M;
  const x0 = x1 - r.largura * M;
  const y0 = (m.base + r.y) * M;
  return {
    centro: [(x0 + x1) / 2, y0 + (r.altura * M) / 2, -(m.profundidade / 2 + afastar) * M],
    tamanho: [r.largura * M, r.altura * M],
  };
}

/** ``altura``: do espaço; ``largura``: do vão. */
export type AlcaParte = "altura" | "largura";
/** Borda puxada: ``fim`` = em cima / à direita de quem olha; ``inicio`` = embaixo / à esquerda. */
export type Borda = "fim" | "inicio";

/**
 * Alças da parte escolhida: a borda que tem vizinho para ceder espaço (o último espaço puxa
 * por baixo; o último vão, pela esquerda). Vão com um espaço só não tem alça de altura;
 * móvel com um vão só não tem alça de largura.
 */
export function alcasDaParte(p: Parte, vaos: number, espacos: number): { alca: AlcaParte; borda: Borda }[] {
  const r: { alca: AlcaParte; borda: Borda }[] = [];
  if (espacos > 1) r.push({ alca: "altura", borda: p.espaco < espacos - 1 ? "fim" : "inicio" });
  if (vaos > 1) r.push({ alca: "largura", borda: p.vao < vaos - 1 ? "fim" : "inicio" });
  return r;
}

/** Eixo da alça no 3D: a direita de quem olha de frente é −x. */
export function eixoParte(alca: AlcaParte, borda: Borda): V3 {
  const s = borda === "fim" ? 1 : -1;
  return alca === "altura" ? [0, s, 0] : [-s, 0, 0];
}

/** Região com a medida nova (borda oposta parada). */
export function regiaoPuxada<R extends Pick<Regiao, "x" | "y" | "largura" | "altura">>(r: R, alca: AlcaParte, borda: Borda, valor: number): R {
  if (alca === "altura") return { ...r, altura: valor, y: borda === "fim" ? r.y : r.y + r.altura - valor };
  return { ...r, largura: valor, x: borda === "fim" ? r.x : r.x + r.largura - valor };
}

/** Onde fica a alça da parte (m): no meio da borda puxada, na frente do móvel. */
export function pontoParte(r: Pick<Regiao, "x" | "y" | "largura" | "altura">, alca: AlcaParte, borda: Borda, m: Medidas): V3 {
  const { centro, tamanho } = naFrente(r, m, 30);
  const s = borda === "fim" ? 1 : -1;
  if (alca === "altura") return [centro[0], centro[1] + (s * tamanho[1]) / 2, centro[2]];
  return [centro[0] - (s * tamanho[0]) / 2, centro[1], centro[2]];
}

/** Menor espaço ou vão aceito ao puxar (o core confere o resto: gaveta, chapa). */
export const MINIMO_PARTE_MM = 50;

/** Medida da parte depois de a alça andar ``t`` metros (passos de 1 cm a partir da atual,
 * que pode vir quebrada da divisão automática). */
export function medidaParte(inicial: number, t: number): number {
  return Math.max(MINIMO_PARTE_MM, Math.round(inicial) + Math.round(t / M / PASSO_MM) * PASSO_MM);
}
