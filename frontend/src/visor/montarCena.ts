/** Monta o 3D direto da cena calculada pelo core (``GET .../cena``), sem Blender.
 *
 * Mesmos eixos do .glb que o visor já usava: metros, Y para cima, x da planta = x e y da
 * planta = −z. Mesmos nomes de objeto e as mesmas marcas em ``userData`` (``material``,
 * ``oculto_em``, ``movel``, ``parte``): pintura ao vivo, teto, cortes e seleção de móvel
 * continuam valendo. Os chanfros viram cantos arredondados (``RoundedBoxGeometry``).
 */

import {
  BoxGeometry,
  type BufferGeometry,
  Color,
  ExtrudeGeometry,
  Group,
  type Material,
  Mesh,
  MeshStandardMaterial,
  Shape,
} from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import type { Esquemas } from "../api/cliente";

export type Cena3D = Esquemas["Cena3D"];
type Prisma = Esquemas["Prisma3D"];
type Caixa = Esquemas["Caixa3D"];
type Mat = Esquemas["Material3D"];

const M = 0.001;

/** Ponto da cena (mm, z para cima) → posição no three (m, Y para cima, −z = y da planta). */
export function paraThree(x: number, y: number, z: number): [number, number, number] {
  return [x * M, z * M, -y * M];
}

/** Giro da planta (graus, anti-horário visto de cima) → giro em torno do Y do three. */
export function giroThree(graus: number): number {
  return (graus * Math.PI) / 180;
}

function material(nome: string, m: Mat | undefined): MeshStandardMaterial {
  const cor = new Color(m?.cor ?? "#cccccc");
  const mat = new MeshStandardMaterial({
    color: cor,
    roughness: m?.rugosidade ?? 0.6,
    metalness: m?.metal ? 0.6 : 0,
    transparent: !!m?.vidro,
    opacity: m?.vidro ? 0.35 : 1,
    emissive: m?.emissao ? cor : new Color("#000000"),
    emissiveIntensity: m?.emissao ? 0.8 : 1,
  });
  mat.name = nome;
  return mat;
}

function prisma(p: Prisma, mat: Material): Mesh {
  // contorno da planta no plano XY da forma; extruda em +Z e gira: (x, y) → (x, −z), +Z → +Y
  const forma = new Shape(p.contorno.map(([x, y]) => ({ x: x * M, y: y * M }) as never));
  const geo = new ExtrudeGeometry(forma, { depth: (p.z1 - p.z0) * M, bevelEnabled: false });
  geo.rotateX(-Math.PI / 2);
  geo.translate(0, p.z0 * M, 0);
  return new Mesh(geo, mat);
}

function caixa(c: Caixa, mat: Material): Mesh {
  const [w, d, h] = c.tamanho.map((v) => v * M);
  const raio = Math.min((c.chanfro ?? 0) * M, w / 2, d / 2, h / 2);
  // BoxGeometry(x, y, z): largura em X, altura em Y, profundidade em Z
  const geo: BufferGeometry = raio > 0.0005 ? new RoundedBoxGeometry(w, h, d, 2, raio) : new BoxGeometry(w, h, d);
  const malha = new Mesh(geo, mat);
  malha.position.set(...paraThree(c.centro[0], c.centro[1], c.centro[2]));
  malha.rotation.y = giroThree(c.rotacao);
  return malha;
}

/** Grupo three com tudo da cena. Quem chama descarta o anterior com :func:`descartar`. */
export function montarCena(cena: Cena3D): Group {
  const grupo = new Group();
  const mats = new Map<string, MeshStandardMaterial>();
  const mat = (nome: string) => {
    let m = mats.get(nome);
    if (!m) mats.set(nome, (m = material(nome, cena.materiais[nome])));
    return m;
  };
  const marcar = (o: Mesh, nome: string, material: string, oculto?: string[], extras?: Record<string, string>) => {
    o.name = nome;
    o.userData.material = material;
    if (oculto?.length) o.userData.oculto_em = oculto.join(",");
    Object.assign(o.userData, extras ?? {});
    grupo.add(o);
  };
  for (const p of cena.prismas) marcar(prisma(p, mat(p.material)), p.nome, p.material, p.oculto_em);
  for (const c of cena.caixas) marcar(caixa(c, mat(c.material)), c.nome, c.material, c.oculto_em, c.extras);
  return grupo;
}

/** Libera geometrias e materiais (a cena é remontada a cada versão do projeto). */
export function descartar(grupo: Group): void {
  grupo.traverse((o) => {
    if (o instanceof Mesh) {
      o.geometry.dispose();
      (Array.isArray(o.material) ? o.material : [o.material]).forEach((m: Material) => m.dispose());
    }
  });
}
