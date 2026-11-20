import { opcao } from "../estilo";
import { Line, OrbitControls } from "@react-three/drei";
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
function Contorno({ scene, selecionado }: { scene: Object3D; selecionado: string | null }) {
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
  }, [scene, selecionado]);
  if (!pontos) return null;
  return <Line points={pontos} segments lineWidth={5} color="#0ea5e9" transparent opacity={0.35} depthWrite={false} />;
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

type Controles = { target: Vector3; update: () => void };

const caixa = (b: Box3): Caixa => ({ min: b.min.toArray(), max: b.max.toArray() });

function Modelo({
  cena,
  chave,
  vista,
  teto,
  pintura,
  selecionado,
  aoMovel,
  moveis,
}: {
  moveis: string[];
  cena: Cena3D;
  chave: string;
  vista: Vista3D;
  teto: boolean;
  pintura: Pintura | null;
  selecionado: string | null;
  aoMovel?: (id: string) => void;
}) {
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

  // teto e luminárias: escondidos por padrão, para ver o cômodo por dentro de cima
  useEffect(() => {
    scene.traverse((o) => {
      if (ehTeto(o.name, o.userData)) o.visible = teto;
    });
  }, [scene, teto]);

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
    <Contorno scene={scene} selecionado={selecionado} />
    <primitive
      object={scene}
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
        gl.domElement.style.cursor = aoMovel && movelDe(e.object, moveis) ? "pointer" : "";
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
  moveis = [],
}: {
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
    <div className="relative h-full w-full bg-superficie-2">
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
      </div>
      <p className="absolute bottom-3 left-3 z-10 text-xs text-tinta-suave">
        Clique num móvel para selecionar · arraste para girar · roda para zoom · botão direito para mover
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
          moveis={moveis}
        />
        <OrbitControls makeDefault enableDamping={false} />
      </Canvas>
    </div>
  );
}
