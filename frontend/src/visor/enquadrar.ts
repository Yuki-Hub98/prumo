/** Vistas prontas do visor 3D: posição da câmera, alvo e corte da parede da frente.
 *
 * O .glb vem em metros com Y para cima (o exportador do Blender converte): x da planta = x,
 * y da planta = -z. "Frente" é olhar o cômodo pelo lado de baixo da planta, como na tela.
 */

export type Vista3D = "cima" | "perspectiva" | "frente" | "fundo" | "esquerda" | "direita";

export const VISTAS_3D: { nome: Vista3D; titulo: string }[] = [
  { nome: "cima", titulo: "De cima" },
  { nome: "perspectiva", titulo: "Perspectiva" },
  { nome: "frente", titulo: "Frente" },
  { nome: "fundo", titulo: "Fundo" },
  { nome: "esquerda", titulo: "Esquerda" },
  { nome: "direita", titulo: "Direita" },
];

/** Caixa alinhada aos eixos: ``[x, y, z]`` mínimo e máximo, em metros. */
export type Caixa = { min: [number, number, number]; max: [number, number, number] };

/** Plano de corte no formato do three (``normal · p + constante >= 0`` fica visível). */
export type Corte = { normal: [number, number, number]; constante: number };

export type Enquadramento = {
  posicao: [number, number, number];
  alvo: [number, number, number];
  corte: Corte | null;
};

/** O corte entra 5 mm no cômodo: some a parede inteira (inclusive a face de dentro). */
const RECUO = 0.005;

/**
 * ``modelo``: caixa do modelo inteiro; ``piso``: caixa do piso (o vão livre do cômodo),
 * usada para cortar exatamente a parede do lado da câmera.
 */
export function enquadrar(vista: Vista3D, modelo: Caixa, piso: Caixa): Enquadramento {
  const cx = (modelo.min[0] + modelo.max[0]) / 2;
  const cz = (modelo.min[2] + modelo.max[2]) / 2;
  const altura = modelo.max[1] - modelo.min[1];
  const d = Math.max(modelo.max[0] - modelo.min[0], modelo.max[2] - modelo.min[2], 1);
  const olho = altura * 0.55;
  const alvoMeio: [number, number, number] = [cx, altura * 0.4, cz];
  switch (vista) {
    case "cima":
      return { posicao: [cx, altura + d * 1.5, cz + 0.001], alvo: [cx, 0, cz], corte: null };
    case "perspectiva":
      return { posicao: [cx + d * 0.8, altura + d * 0.9, cz + d * 1.1], alvo: [cx, 0, cz], corte: null };
    case "frente":
      return {
        posicao: [cx, olho, piso.max[2] + d * 1.3],
        alvo: alvoMeio,
        corte: { normal: [0, 0, -1], constante: piso.max[2] - RECUO },
      };
    case "fundo":
      return {
        posicao: [cx, olho, piso.min[2] - d * 1.3],
        alvo: alvoMeio,
        corte: { normal: [0, 0, 1], constante: -(piso.min[2] + RECUO) },
      };
    case "direita":
      return {
        posicao: [piso.max[0] + d * 1.3, olho, cz],
        alvo: alvoMeio,
        corte: { normal: [-1, 0, 0], constante: piso.max[0] - RECUO },
      };
    case "esquerda":
      return {
        posicao: [piso.min[0] - d * 1.3, olho, cz],
        alvo: alvoMeio,
        corte: { normal: [1, 0, 0], constante: -(piso.min[0] + RECUO) },
      };
  }
}

/** Piso de um cômodo: ``piso`` no modelo do cômodo, ``piso-<cômodo>`` no do pavimento.
 * A caixa dos pisos é o vão livre usado para cortar a parede do lado da câmera. */
export function ehPiso(nome: string): boolean {
  return nome === "piso" || nome.startsWith("piso-");
}

/** Some na vista de cima (teto, luminária)? Vem do .glb (``extras.oculto_em``); modelos
 * antigos, sem extras, só têm o nome ``teto``. */
export function ehTeto(nome: string, extras: Record<string, unknown> | undefined): boolean {
  const oculto = extras?.oculto_em;
  if (typeof oculto === "string") return oculto.split(",").includes("superior");
  return nome === "teto";
}
