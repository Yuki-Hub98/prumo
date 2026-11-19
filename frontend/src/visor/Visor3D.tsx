import { OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas, useThree } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useState } from "react";
import { Box3, Plane, Vector3, type Object3D } from "three";
import { type Caixa, ehPiso, ehTeto, enquadrar, VISTAS_3D, type Vista3D } from "./enquadrar";

type Controles = { target: Vector3; update: () => void };

const caixa = (b: Box3): Caixa => ({ min: b.min.toArray(), max: b.max.toArray() });

function Modelo({ url, vista, teto }: { url: string; vista: Vista3D; teto: boolean }) {
  const { scene } = useGLTF(url);
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

  // teto e luminárias: escondidos por padrão, para ver o cômodo por dentro de cima
  useEffect(() => {
    scene.traverse((o) => {
      if (ehTeto(o.name, o.userData)) o.visible = teto;
    });
  }, [scene, teto]);

  useEffect(() => {
    const e = enquadrar(vista, todo, piso);
    camera.position.set(...e.posicao);
    camera.lookAt(...e.alvo);
    if (controles) {
      controles.target.set(...e.alvo);
      controles.update();
    }
    gl.clippingPlanes = e.corte ? [new Plane(new Vector3(...e.corte.normal), e.corte.constante)] : [];
  }, [vista, todo, piso, camera, controles, gl]);

  return <primitive object={scene} />;
}

const botao = (ativo: boolean) =>
  `rounded border px-2 py-0.5 text-sm ${ativo ? "border-stone-800 bg-stone-800 text-white" : "border-stone-300 bg-white hover:bg-stone-100"}`;

/** Visor do .glb do cômodo ou do pavimento: girar (arrastar), zoom (roda), mover (botão direito),
 * vistas prontas com corte da parede do lado da câmera e teto liga/desliga. */
export default function Visor3D({ url }: { url: string }) {
  const [vista, setVista] = useState<Vista3D>("cima");
  const [teto, setTeto] = useState(false);
  return (
    <div className="relative h-full w-full bg-stone-100">
      <div className="absolute left-3 top-3 z-10 flex flex-wrap gap-1">
        {VISTAS_3D.map((v) => (
          <button key={v.nome} className={botao(vista === v.nome)} onClick={() => setVista(v.nome)}>
            {v.titulo}
          </button>
        ))}
        <label className="ml-2 flex items-center gap-1 rounded border border-stone-300 bg-white px-2 py-0.5 text-sm">
          <input type="checkbox" checked={teto} onChange={(e) => setTeto(e.target.checked)} />
          teto
        </label>
      </div>
      <p className="absolute bottom-3 left-3 z-10 text-xs text-stone-500">
        arraste para girar · roda para zoom · botão direito para mover
        {vista !== "cima" && vista !== "perspectiva" && " · parede da frente cortada"}
      </p>
      <Canvas camera={{ fov: 45, near: 0.05, far: 200 }} gl={{ localClippingEnabled: true }}>
        <ambientLight intensity={0.7} />
        <hemisphereLight args={["#ffffff", "#b9a88f", 0.6]} />
        <directionalLight position={[4, 9, 6]} intensity={1.4} />
        <Suspense fallback={null}>
          <Modelo url={url} vista={vista} teto={teto} />
        </Suspense>
        <OrbitControls makeDefault enableDamping={false} />
      </Canvas>
    </div>
  );
}
