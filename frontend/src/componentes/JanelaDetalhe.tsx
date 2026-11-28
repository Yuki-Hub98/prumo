import { OrbitControls } from "@react-three/drei";
import { Canvas, type ThreeEvent, useFrame } from "@react-three/fiber";
import { Redo2, Undo2, X } from "lucide-react";
import { type ReactNode, type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Vector3 } from "three";
import { api, ou } from "../api/cliente";
import { type useEditar, useVersoes } from "../dados";
import { btn } from "../estilo";
import { tNoEixo } from "../visor/detalhe";

type V3 = [number, number, number];

/** Alça amarela: onde está (m), para onde anda (unitário) e o rótulo que aparece em cima. */
export type AlcaTela = { id: string; ponto: V3; eixo: V3; rotulo: string };

/** Cor de um token CSS (o three não lê ``var(...)``). */
export function corToken(nome: string, padrao: string): string {
  if (typeof document === "undefined") return padrao;
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || padrao;
}

type Controles = { enabled: boolean };

/** Leva cada rótulo (HTML por cima do 3D) para a tela, em cima da alça, a cada quadro. */
function SeguirAlcas({ alcas, rotulos }: { alcas: AlcaTela[]; rotulos: RefObject<Record<string, HTMLSpanElement | null>> }) {
  const v = useMemo(() => new Vector3(), []);
  useFrame(({ camera, size }) => {
    for (const a of alcas) {
      const el = rotulos.current?.[a.id];
      if (!el) continue;
      v.set(...a.ponto).project(camera);
      const x = ((v.x + 1) / 2) * size.width;
      const y = ((1 - v.y) / 2) * size.height;
      el.style.transform = `translate(${x}px, ${y}px) translate(-50%, -150%)`;
      el.style.visibility = v.z > 1 ? "hidden" : "visible";
    }
  });
  return null;
}

/**
 * Casca do "Editar em detalhe": janela por cima da tela toda com o objeto em 3D (girável),
 * alças amarelas para puxar, Desfazer/Refazer e um painel à direita. Quem usa diz o que
 * aparece (``children``, já no referencial do detalhe), as alças e o que fazer ao puxar:
 * ``aoPuxar`` recebe quanto a alça andou (m) pelo eixo desde que começou a puxar.
 */
export function JanelaDetalhe({
  codigo,
  editar,
  titulo,
  dica,
  aviso,
  tam,
  alvo,
  ladoCamera = -1,
  alcas,
  aoComecar,
  aoPuxar,
  aoSoltar,
  aoClicarFundo,
  painel,
  aoFechar,
  children,
}: {
  codigo: string;
  /** A edição de quem usa: Desfazer/Refazer, "Gravando…" e o erro aparecem aqui. */
  editar: ReturnType<typeof useEditar>;
  titulo: string;
  dica: string;
  /** Texto no lugar do 3D enquanto ele não está pronto (``null`` = pronto). */
  aviso: string | null;
  /** Maior medida do objeto (m): enquadra a câmera e a malha do piso. */
  tam: number;
  alvo: V3;
  /** De que lado (sinal de z) a câmera começa: −1 = de frente (−z). */
  ladoCamera?: 1 | -1;
  alcas: AlcaTela[];
  aoComecar?: (id: string) => void;
  aoPuxar: (id: string, t: number) => void;
  aoSoltar: (id: string) => void;
  aoClicarFundo?: () => void;
  painel: ReactNode;
  aoFechar: () => void;
  children: ReactNode;
}) {
  const versoes = useVersoes(codigo).data;
  const voltar = (tipo: "desfazer" | "refazer") =>
    editar.mutate((versao) =>
      ou(
        tipo === "desfazer"
          ? api.POST("/projetos/{codigo}/desfazer", { params: { path: { codigo }, query: { versao } } })
          : api.POST("/projetos/{codigo}/refazer", { params: { path: { codigo }, query: { versao } } }),
      ),
    );
  const [puxando, setPuxando] = useState<string | null>(null);
  const controles = useRef<Controles | null>(null);
  const arrasto = useRef<{ id: string; origem: V3; eixo: V3 } | null>(null);
  const rotulos = useRef<Record<string, HTMLSpanElement | null>>({});
  const amarelo = corToken("--trena", "#f2b200");

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [aoFechar]);

  const comecar = (a: AlcaTela) => (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    arrasto.current = { id: a.id, origem: a.ponto, eixo: a.eixo };
    setPuxando(a.id);
    if (controles.current) controles.current.enabled = false;
    aoComecar?.(a.id);
  };
  const mover = (e: ThreeEvent<PointerEvent>) => {
    const a = arrasto.current;
    if (!a) return;
    const r = e.ray;
    const t = tNoEixo(a.origem, a.eixo, r.origin.toArray() as V3, r.direction.toArray() as V3);
    if (t !== null) aoPuxar(a.id, t);
  };
  const soltar = (e: ThreeEvent<PointerEvent>) => {
    const a = arrasto.current;
    if (!a) return;
    (e.target as Element).releasePointerCapture?.(e.pointerId);
    arrasto.current = null;
    setPuxando(null);
    if (controles.current) controles.current.enabled = true;
    aoSoltar(a.id);
  };

  // portal no body: o painel lateral rola e cortaria uma janela "fixed" dentro dele
  return createPortal(
    <div role="dialog" aria-label={`Editar em detalhe: ${titulo}`} className="fixed inset-0 z-50 flex flex-col bg-superficie-2">
      <div className="flex items-center gap-3 border-b border-linha bg-superficie px-4 py-2 text-sm">
        <h2 className="font-semibold">Editar em detalhe · {titulo}</h2>
        <span className="text-tinta-suave">{dica}</span>
        <span className="ml-auto flex items-center gap-1">
          {(["desfazer", "refazer"] as const).map((tipo) => (
            <button
              key={tipo}
              className={btn("fantasma", "sm")}
              disabled={editar.isPending || versoes?.[tipo] == null}
              onClick={() => voltar(tipo)}
              title={tipo === "desfazer" ? "Desfazer (Ctrl+Z)" : "Refazer (Ctrl+Shift+Z)"}
            >
              {tipo === "desfazer" ? <Undo2 size={16} /> : <Redo2 size={16} />}
              {tipo === "desfazer" ? "Desfazer" : "Refazer"}
            </button>
          ))}
        </span>
        <button className={btn("secundario", "sm")} onClick={aoFechar} aria-label="Fechar">
          <X size={16} /> Fechar
        </button>
      </div>
      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          {aviso === null ? (
            <Canvas
              camera={{ fov: 40, near: 0.01, far: 100, position: [tam * 1.1, alvo[1] + tam * 0.8, ladoCamera * tam * 1.8] }}
              onCreated={({ gl }) => void (gl.localClippingEnabled = true)}
              onPointerMissed={(e) => e.type === "click" && aoClicarFundo?.()}
            >
              <ambientLight intensity={0.7} />
              <hemisphereLight args={["#ffffff", "#b9a88f", 0.6]} />
              <directionalLight position={[3, 6, ladoCamera * 4]} intensity={1.4} />
              <OrbitControls ref={controles as never} target={alvo} makeDefault />
              <gridHelper args={[Math.ceil(tam * 3), Math.ceil(tam * 3) * 10, "#bbb", "#ddd"]} />
              {children}
              {alcas.map((a) => (
                <mesh
                  key={a.id}
                  renderOrder={10}
                  position={a.ponto}
                  onPointerDown={comecar(a)}
                  onPointerMove={mover}
                  onPointerUp={soltar}
                  onPointerOver={() => (document.body.style.cursor = "grab")}
                  onPointerOut={() => (document.body.style.cursor = "")}
                >
                  <sphereGeometry args={[Math.max(0.025, tam * 0.025), 20, 20]} />
                  {/* sempre por cima do objeto: a alça fica no meio da face, meio enterrada */}
                  <meshBasicMaterial color={amarelo} depthTest={false} transparent opacity={0.95} />
                </mesh>
              ))}
              <SeguirAlcas alcas={alcas} rotulos={rotulos} />
            </Canvas>
          ) : (
            <p className="p-4 text-sm text-tinta-suave">{aviso}</p>
          )}
          {aviso === null &&
            alcas.map((a) => (
              <span
                key={a.id}
                ref={(el) => {
                  rotulos.current[a.id] = el;
                }}
                className={`pointer-events-none absolute left-0 top-0 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-xs shadow-sm ${
                  puxando === a.id ? "border-trena bg-trena text-tinta" : "border-linha bg-superficie text-tinta"
                }`}
              >
                {a.rotulo}
              </span>
            ))}
        </div>
        <aside className="w-72 shrink-0 overflow-y-auto border-l border-linha bg-superficie p-3 text-sm">
          {painel}
          {editar.isPending && <p className="mt-2 text-xs text-tinta-suave">Gravando…</p>}
          {editar.error && <p className="mt-2 text-sm text-erro">{editar.error.message}</p>}
        </aside>
      </div>
    </div>,
    document.body,
  );
}

/** Caixa translúcida amarela (tamanho novo enquanto puxa, ou até a cena nova chegar). */
export function CaixaFantasma({ min, max }: { min: V3; max: V3 }) {
  return (
    <mesh position={min.map((v, i) => (v + max[i]) / 2) as V3}>
      <boxGeometry args={max.map((v, i) => v - min[i]) as V3} />
      <meshBasicMaterial color={corToken("--trena", "#f2b200")} transparent opacity={0.18} depthWrite={false} />
    </mesh>
  );
}

/** Linha de medida no painel: nome à esquerda, valor à direita (em negrito se mudou). */
export function LinhaMedida({ nome, valor, mudou }: { nome: string; valor: string; mudou?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-tinta-suave">{nome}</span>
      <span className={`num ${mudou ? "font-semibold text-tinta" : ""}`}>{valor}</span>
    </div>
  );
}
