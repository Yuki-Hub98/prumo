import { opcao } from "../estilo";
import { Line, OrbitControls } from "@react-three/drei";
import { RotateCw } from "lucide-react";
import { Canvas, type ThreeEvent, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import { Box3, Color, Mesh, MeshStandardMaterial, Plane, Vector3, type Object3D } from "three";
import type { Cores } from "../api/cliente";
import { arestas, type Caixa, ehPiso, ehTeto, enquadrar, VISTAS_3D, type Vista3D } from "./enquadrar";
import { type Cena3D, descartar, montarCena } from "./montarCena";
import { type Contexto, corDo, movelDaPeca, papel } from "./pintar";

/** Cores do painel aplicadas ao vivo (``cores`` nulo = as cores com que o modelo saiu). */
export type Pintura = { cores: Cores | null; ctx: Contexto };

/** Cada malha com material próprio e a cor original guardada (uma vez por modelo). */
function prepararPintura(scene: Object3D) {
  scene.traverse((o) => {
    if (!(o instanceof Mesh) || o.userData.corOriginal) return;
    const mat = o.material;
    if (!(mat instanceof MeshStandardMaterial)) return;
    // material próprio: cada parede pode ter a sua cor, mesmo saindo do mesmo material
    o.material = mat.clone();
    o.userData.corOriginal = mat.color.clone();
    o.userData.material = mat.name;
  });
}

function pintar(scene: Object3D, pintura: Pintura | null) {
  scene.traverse((o) => {
    if (!(o instanceof Mesh) || !o.userData.corOriginal) return;
    const original = o.userData.corOriginal as Color;
    const p = pintura ? papel(o.name, o.userData.material as string, pintura.ctx, o.userData) : null;
    const cor = p && pintura?.cores ? corDo(p, pintura.cores, pintura.ctx) : null;
    const mat = o.material as MeshStandardMaterial;
    mat.color.copy(cor ? new Color(cor) : original);
  });
}

/** Folga do contorno em volta do móvel (m). */
const FOLGA_CONTORNO = 0.03;

/** Móvel selecionado: uma linha grossa e quase transparente em volta, sem mudar a cor
 * dele (a cor escolhida continua aparecendo como é). */
function Contorno({ scene, selecionado, versao }: { scene: Object3D; selecionado: string | null; versao: number }) {
  const pontos = useMemo(() => {
    if (!selecionado) return null;
    const caixa = new Box3();
    scene.traverse((o) => {
      if (
        o instanceof Mesh &&
        (o.userData.movel === selecionado || movelDaPeca(o.name, (o.userData.material as string) ?? "", [selecionado]))
      )
        caixa.expandByObject(o);
    });
    if (caixa.isEmpty()) return null;
    caixa.expandByScalar(FOLGA_CONTORNO);
    return arestas({ min: caixa.min.toArray(), max: caixa.max.toArray() });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ``versao``: o móvel andou
  }, [scene, selecionado, versao]);
  if (!pontos) return null;
  // amarelo trena (o mesmo da seleção na planta), quase transparente para não esconder a cor
  return <Line points={pontos} segments lineWidth={5} color={corToken("--trena", "#f2b200")} transparent opacity={0.5} depthWrite={false} />;
}

/** Cor de um token CSS (para o three.js, que não lê ``var(...)``). */
function corToken(nome: string, padrao: string): string {
  if (typeof document === "undefined") return padrao;
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || padrao;
}

/** Id do móvel de uma malha clicada, subindo até achar. */
function movelDe(o: Object3D | null, ids: string[]): string | null {
  for (let x = o; x; x = x.parent) {
    if (typeof x.userData.movel === "string" && ids.includes(x.userData.movel)) return x.userData.movel;
    const id = movelDaPeca(x.name, (x.userData.material as string | undefined) ?? "", ids);
    if (id) return id;
  }
  return null;
}

type Controles = { target: Vector3; update: () => void; enabled: boolean };

/** Passo do arrastar no 3D (m): 1 cm, como na planta. */
const PASSO_3D = 0.01;
const PISO = new Plane(new Vector3(0, 1, 0), 0);

/** Malhas de um móvel (para mover juntas). */
function pecasDo(scene: Object3D, id: string): Object3D[] {
  const pecas: Object3D[] = [];
  scene.traverse((o) => {
    if (o instanceof Mesh && (o.userData.movel === id || movelDaPeca(o.name, (o.userData.material as string) ?? "", [id])))
      pecas.push(o);
  });
  return pecas;
}

const caixa = (b: Box3): Caixa => ({ min: b.min.toArray(), max: b.max.toArray() });

function Modelo({
  cena,
  chave,
  vista,
  teto,
  pintura,
  selecionado,
  aoMovel,
  aoArrastar,
  moveis,
  andares,
  ate,
}: {
  moveis: string[];
  andares: string[];
  ate: string | null;
  cena: Cena3D;
  chave: string;
  vista: Vista3D;
  teto: boolean;
  pintura: Pintura | null;
  selecionado: string | null;
  aoMovel?: (id: string) => void;
  aoArrastar?: (id: string, d: [number, number]) => void;
}) {
  // arrastar o móvel selecionado pelo piso: as peças andam juntas; ao soltar, grava (mm)
  const arrasto = useRef<{ id: string; ini: Vector3; pecas: Object3D[]; bases: Vector3[]; d: Vector3 } | null>(null);
  const [andou, setAndou] = useState(0);
  // remontado a cada versão do projeto: muda junto com a planta, sem esperar render
  const scene = useMemo(() => montarCena(cena), [cena]);
  useEffect(() => () => descartar(scene), [scene]);
  const camera = useThree((s) => s.camera);
  const gl = useThree((s) => s.gl);
  const controles = useThree((s) => s.controls) as unknown as Controles | null;

  const [todo, piso] = useMemo(() => {
    const t = new Box3().setFromObject(scene);
    // no pavimento são vários pisos (um por cômodo): a caixa junta todos
    const pisos: Object3D[] = [];
    scene.traverse((o) => {
      if (ehPiso(o.name)) pisos.push(o);
    });
    const p = new Box3();
    for (const o of pisos) p.expandByObject(o);
    return [caixa(t), pisos.length ? caixa(p) : caixa(t)];
  }, [scene]);

  useEffect(() => {
    prepararPintura(scene);
    pintar(scene, pintura);
  }, [scene, pintura]);

  // teto e luminárias: escondidos por padrão, para ver o cômodo por dentro de cima. Na casa
  // toda, os andares acima do "mostrar até" somem e só o teto (laje) do último mostrado segue
  // o botão: os de baixo ficam (são o piso do de cima)
  useEffect(() => {
    const topo = ate ? andares.indexOf(ate) : -1;
    scene.traverse((o) => {
      const pav = o.userData.pavimento as string | undefined;
      const i = pav ? andares.indexOf(pav) : -1;
      if (topo >= 0 && i > topo) o.visible = false;
      else if (ehTeto(o.name, o.userData)) o.visible = teto || (topo >= 0 && i < topo);
      else if (o.userData.pavimento) o.visible = true;
    });
  }, [scene, teto, ate, andares]);

  // a câmera só volta para a vista pronta quando ela muda (ou outro cômodo): editar o projeto
  // não pode tirar a câmera de onde a pessoa girou
  const caixas = useRef({ todo, piso });
  caixas.current = { todo, piso };
  useEffect(() => {
    const e = enquadrar(vista, caixas.current.todo, caixas.current.piso);
    camera.position.set(...e.posicao);
    camera.lookAt(...e.alvo);
    if (controles) {
      controles.target.set(...e.alvo);
      controles.update();
    }
  }, [vista, chave, camera, controles]);
  useEffect(() => {
    const e = enquadrar(vista, todo, piso);
    gl.clippingPlanes = e.corte ? [new Plane(new Vector3(...e.corte.normal), e.corte.constante)] : [];
  }, [vista, todo, piso, gl]);

  return (
    <>
    <Contorno scene={scene} selecionado={selecionado} versao={andou} />
    <primitive
      object={scene}
      onPointerDown={(e: ThreeEvent<PointerEvent>) => {
        if (!aoArrastar || !selecionado || e.button !== 0) return;
        const id = movelDe(e.object, moveis);
        if (id !== selecionado) return;
        const ini = e.ray.intersectPlane(PISO, new Vector3());
        if (!ini) return;
        e.stopPropagation();
        (e.target as Element).setPointerCapture?.(e.pointerId);
        if (controles) controles.enabled = false; // não gira a câmera enquanto arrasta
        const pecas = pecasDo(scene, id);
        arrasto.current = { id, ini, pecas, bases: pecas.map((p) => p.position.clone()), d: new Vector3() };
      }}
      onPointerUp={(e: ThreeEvent<PointerEvent>) => {
        const a = arrasto.current;
        if (!a) return;
        e.stopPropagation();
        arrasto.current = null;
        if (controles) controles.enabled = true;
        // x do 3D = x da planta; z do 3D = −y da planta (m → mm)
        const dx = Math.round(a.d.x * 1000);
        const dy = Math.round(-a.d.z * 1000);
        if (dx || dy) aoArrastar?.(a.id, [dx, dy]);
      }}
      onClick={(e: ThreeEvent<MouseEvent>) => {
        if (e.delta > 4 || !aoMovel) return; // arrastou para girar: não é clique
        const id = movelDe(e.object, moveis);
        if (id) {
          e.stopPropagation();
          aoMovel(id);
        }
      }}
      // mãozinha em cima de móvel (clicável); fora dele, o cursor de girar/arrastar de sempre
      onPointerMove={(e: ThreeEvent<PointerEvent>) => {
        e.stopPropagation(); // só o objeto mais perto (o que o clique pegaria)
        const a = arrasto.current;
        if (a) {
          const p = e.ray.intersectPlane(PISO, new Vector3());
          if (!p) return;
          const passo = (v: number) => Math.round(v / PASSO_3D) * PASSO_3D;
          a.d.set(passo(p.x - a.ini.x), 0, passo(p.z - a.ini.z));
          a.pecas.forEach((o, i) => o.position.set(a.bases[i].x + a.d.x, a.bases[i].y, a.bases[i].z + a.d.z));
          setAndou((n) => n + 1);
          gl.domElement.style.cursor = "grabbing";
          return;
        }
        const id = movelDe(e.object, moveis);
        gl.domElement.style.cursor = !id || !aoMovel ? "" : id === selecionado && aoArrastar ? "grab" : "pointer";
      }}
      onPointerOut={() => {
        gl.domElement.style.cursor = "";
      }}
    />
    </>
  );
}

const botao = (ativo: boolean) =>
  `px-2 py-0.5 text-sm ${opcao(ativo)}`;

/** Visor 3D ao vivo do cômodo ou do pavimento (montado da cena do core): girar (arrastar),
 * zoom (roda), mover (botão direito), vistas prontas com corte da parede do lado da câmera,
 * teto liga/desliga e as cores do painel aplicadas ao vivo (``pintura``). */
export default function Visor3D({
  cena,
  chave,
  pintura = null,
  selecionado = null,
  aoMovel,
  aoArrastar,
  aoGirar,
  moveis = [],
  andares = [],
  ate = null,
}: {
  /** Casa toda: os andares, de baixo para cima, e até qual mostrar. */
  andares?: string[];
  ate?: string | null;
  /** Arrastar o móvel selecionado pelo piso (deslocamento em mm na planta). */
  aoArrastar?: (id: string, d: [number, number]) => void;
  /** Girar o móvel selecionado 90°. */
  aoGirar?: (id: string) => void;
  /** Ids de todos os móveis (para achar o móvel de uma peça clicada). */
  moveis?: string[];
  cena: Cena3D;
  /** Cômodo ou pavimento mostrado: trocar recoloca a câmera na vista pronta. */
  chave: string;
  pintura?: Pintura | null;
  /** Móvel selecionado: aparece com um contorno em volta. */
  selecionado?: string | null;
  /** Clique num móvel do modelo. */
  aoMovel?: (id: string) => void;
}) {
  const [vista, setVista] = useState<Vista3D>("cima");
  const [teto, setTeto] = useState(false);
  return (
    <div className="relative h-full w-full bg-visor">
      <div className="absolute left-3 top-3 z-10 flex flex-wrap gap-1">
        {VISTAS_3D.map((v) => (
          <button key={v.nome} className={botao(vista === v.nome)} onClick={() => setVista(v.nome)}>
            {v.titulo}
          </button>
        ))}
        <label className="ml-2 flex items-center gap-1 rounded-md border border-linha-forte bg-superficie px-2 py-0.5 text-sm">
          <input type="checkbox" checked={teto} onChange={(e) => setTeto(e.target.checked)} />
          Teto
        </label>
        {selecionado && aoGirar && (
          <button className={`ml-2 px-2 py-0.5 text-sm ${opcao(false)}`} onClick={() => aoGirar(selecionado)} title="Girar o móvel selecionado 90°">
            <RotateCw size={14} className="mr-1 inline" />
            Girar 90°
          </button>
        )}
      </div>
      <p className="absolute bottom-3 left-3 z-10 text-xs text-tinta-suave">
        Clique num móvel para selecionar{aoArrastar && " · arraste o selecionado para mover"} · arraste o fundo para girar · roda para zoom · botão direito para deslocar a vista
        {vista !== "cima" && vista !== "perspectiva" && " · parede da frente cortada"}
      </p>
      <Canvas camera={{ fov: 45, near: 0.05, far: 200 }} gl={{ localClippingEnabled: true, logarithmicDepthBuffer: true }}>
        <ambientLight intensity={0.7} />
        <hemisphereLight args={["#ffffff", "#b9a88f", 0.6]} />
        <directionalLight position={[4, 9, 6]} intensity={1.4} />
        <Modelo
          cena={cena}
          chave={chave}
          vista={vista}
          teto={teto}
          pintura={pintura}
          selecionado={selecionado}
          aoMovel={aoMovel}
          aoArrastar={aoArrastar}
          moveis={moveis}
          andares={andares}
          ate={ate}
        />
        <OrbitControls makeDefault enableDamping={false} />
      </Canvas>
    </div>
  );
}
