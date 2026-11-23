import { OrbitControls } from "@react-three/drei";
import { Canvas, type ThreeEvent, useFrame } from "@react-three/fiber";
import { Redo2, Undo2, X } from "lucide-react";
import { type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { Vector3 } from "three";
import { createPortal } from "react-dom";
import { api, ou } from "../api/cliente";
import { btn } from "../estilo";
import { useCena, useEditar, useVersoes } from "../dados";
import { formatar, type Unidade } from "../unidades";
import {
  type Alca,
  caixaPuxada,
  cenaDoMovel,
  eixoAlca,
  type Medidas,
  medidaPuxada,
  pontoDaAlca,
  tNoEixo,
} from "../visor/detalhe";
import { descartar, giroThree, montarCena, paraThree } from "../visor/montarCena";

const NOMES: Record<Alca, string> = { largura: "Largura", profundidade: "Profundidade", altura: "Altura" };
const ALCAS: Alca[] = ["largura", "profundidade", "altura"];

type V3 = [number, number, number];

/** Cor de um token CSS (o three não lê ``var(...)``). */
function corToken(nome: string, padrao: string): string {
  if (typeof document === "undefined") return padrao;
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || padrao;
}

type Controles = { enabled: boolean };

/** Leva cada rótulo (HTML por cima do 3D) para a tela, em cima da alça, a cada quadro. */
function SeguirAlcas({ pontos, rotulos }: { pontos: Record<Alca, V3>; rotulos: RefObject<Record<Alca, HTMLSpanElement | null>> }) {
  const v = useMemo(() => new Vector3(), []);
  useFrame(({ camera, size }) => {
    for (const a of ALCAS) {
      const el = rotulos.current?.[a];
      if (!el) continue;
      v.set(...pontos[a]).project(camera);
      const x = ((v.x + 1) / 2) * size.width;
      const y = ((1 - v.y) / 2) * size.height;
      el.style.transform = `translate(${x}px, ${y}px) translate(-50%, -150%)`;
      el.style.visibility = v.z > 1 ? "hidden" : "visible";
    }
  });
  return null;
}

/**
 * Janela com **só o móvel** em 3D, no centro e girável, com alças para puxar largura,
 * profundidade e altura. As medidas mudam ao vivo enquanto puxa (passo de 1 cm, lado oposto
 * parado); ao soltar, grava como "Quero assim" — Desfazer volta, como qualquer edição.
 */
export function EditarDetalhe({
  codigo,
  comodo,
  id,
  nome,
  centro,
  rotacao,
  medidas,
  unidade,
  aoFechar,
}: {
  codigo: string;
  comodo: string;
  id: string;
  nome: string;
  centro: [number, number];
  rotacao: number;
  medidas: Medidas;
  unidade: Unidade;
  aoFechar: () => void;
}) {
  const cena = useCena(codigo, { comodo });
  const editar = useEditar(codigo);
  const versoes = useVersoes(codigo).data;
  const voltar = (tipo: "desfazer" | "refazer") =>
    editar.mutate((versao) =>
      ou(
        tipo === "desfazer"
          ? api.POST("/projetos/{codigo}/desfazer", { params: { path: { codigo }, query: { versao } } })
          : api.POST("/projetos/{codigo}/refazer", { params: { path: { codigo }, query: { versao } } }),
      ),
    );
  const [atual, setAtual] = useState<Medidas>(medidas);
  const [puxando, setPuxando] = useState<Alca | null>(null);
  const controles = useRef<Controles | null>(null);
  const arrasto = useRef<{ alca: Alca; origem: V3 } | null>(null);
  const rotulos = useRef<Record<Alca, HTMLSpanElement | null>>({ largura: null, profundidade: null, altura: null });

  // medida nova gravada (ou desfeita): volta a acompanhar o projeto
  const chave = `${medidas.largura}|${medidas.profundidade}|${medidas.altura}|${medidas.base}`;
  useEffect(() => setAtual(medidas), [chave]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [aoFechar]);

  const grupo = useMemo(() => (cena.data ? montarCena(cenaDoMovel(cena.data, id)) : null), [cena.data, id]);
  useEffect(() => () => void (grupo && descartar(grupo)), [grupo]);

  const caixa = caixaPuxada(medidas, atual);
  const tam = Math.max(medidas.largura, medidas.profundidade, medidas.base + medidas.altura) / 1000;
  const alvo: V3 = [0, ((medidas.base + medidas.altura) / 2) / 1000, 0];
  const amarelo = corToken("--trena", "#f2b200");
  const mudou = (a: Alca) => atual[a] !== medidas[a];

  const gravar = (alca: Alca, valor: number) =>
    editar.mutate((versao) => {
      const path = { codigo, comodo, id_: id };
      if (alca === "altura")
        return ou(
          api.PATCH("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}", {
            params: { path, query: { versao } },
            body: { altura: { valor, origem: "projeto", obs: "puxada no editar em detalhe" } },
          }),
        );
      return ou(
        api.POST("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/redimensionar", {
          params: { path, query: { versao } },
          body: { lado: alca === "largura" ? "direita" : "frente", tamanho: valor },
        }),
      );
    });

  const comecar = (alca: Alca) => (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    arrasto.current = { alca, origem: pontoDaAlca(alca, caixaPuxada(medidas, medidas)) };
    setPuxando(alca);
    if (controles.current) controles.current.enabled = false;
  };
  const mover = (e: ThreeEvent<PointerEvent>) => {
    const a = arrasto.current;
    if (!a) return;
    const r = e.ray;
    const t = tNoEixo(a.origem, eixoAlca(a.alca), r.origin.toArray() as V3, r.direction.toArray() as V3);
    if (t !== null) setAtual((m) => ({ ...m, [a.alca]: medidaPuxada(a.alca, medidas, t) }));
  };
  const soltar = (e: ThreeEvent<PointerEvent>) => {
    const a = arrasto.current;
    if (!a) return;
    (e.target as Element).releasePointerCapture?.(e.pointerId);
    arrasto.current = null;
    setPuxando(null);
    if (controles.current) controles.current.enabled = true;
    if (atual[a.alca] !== medidas[a.alca]) gravar(a.alca, atual[a.alca]);
  };

  // portal no body: o painel lateral rola e cortaria uma janela "fixed" dentro dele
  return createPortal(
    <div role="dialog" aria-label={`Editar em detalhe: ${nome}`} className="fixed inset-0 z-50 flex flex-col bg-superficie-2">
      <div className="flex items-center gap-3 border-b border-linha bg-superficie px-4 py-2 text-sm">
        <h2 className="font-semibold">Editar em detalhe · {nome}</h2>
        <span className="text-tinta-suave">Puxe as alças amarelas · arraste o fundo para girar · Esc fecha</span>
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
          {grupo ? (
            <Canvas camera={{ fov: 40, near: 0.01, far: 100, position: [tam * 1.1, alvo[1] + tam * 0.8, -tam * 1.8] }}>
              <ambientLight intensity={0.7} />
              <hemisphereLight args={["#ffffff", "#b9a88f", 0.6]} />
              <directionalLight position={[3, 6, -4]} intensity={1.4} />
              <OrbitControls ref={controles as never} target={alvo} makeDefault />
              <gridHelper args={[Math.ceil(tam * 3), Math.ceil(tam * 3) * 10, "#bbb", "#ddd"]} />
              {/* o móvel no referencial dele: sem o giro da planta, centro na origem */}
              <group rotation-y={-giroThree(rotacao)}>
                <group position={paraThree(-centro[0], -centro[1], 0)}>
                  <primitive object={grupo} />
                </group>
              </group>
              {/* caixa do tamanho novo enquanto puxa (ou até a cena nova chegar) */}
              {ALCAS.some(mudou) && (
                <mesh position={caixa.min.map((v, i) => (v + caixa.max[i]) / 2) as V3}>
                  <boxGeometry args={caixa.max.map((v, i) => v - caixa.min[i]) as V3} />
                  <meshBasicMaterial color={amarelo} transparent opacity={0.18} depthWrite={false} />
                </mesh>
              )}
              {ALCAS.map((a) => (
                <mesh
                  key={a}
                  renderOrder={10}
                  position={pontoDaAlca(a, caixa)}
                  onPointerDown={comecar(a)}
                  onPointerMove={mover}
                  onPointerUp={soltar}
                  onPointerOver={() => (document.body.style.cursor = "grab")}
                  onPointerOut={() => (document.body.style.cursor = "")}
                >
                  <sphereGeometry args={[Math.max(0.025, tam * 0.025), 20, 20]} />
                  {/* sempre por cima do móvel: a alça fica no meio da face, meio enterrada */}
                  <meshBasicMaterial color={amarelo} depthTest={false} transparent opacity={0.95} />
                </mesh>
              ))}
              <SeguirAlcas
                pontos={{ largura: pontoDaAlca("largura", caixa), profundidade: pontoDaAlca("profundidade", caixa), altura: pontoDaAlca("altura", caixa) }}
                rotulos={rotulos}
              />
            </Canvas>
          ) : (
            <p className="p-4 text-sm text-tinta-suave">{cena.error ? cena.error.message : "Montando o 3D…"}</p>
          )}
          {grupo &&
            ALCAS.map((a) => (
              <span
                key={a}
                ref={(el) => {
                  rotulos.current[a] = el;
                }}
                className={`pointer-events-none absolute left-0 top-0 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-xs shadow-sm ${
                  puxando === a ? "border-trena bg-trena text-tinta" : "border-linha bg-superficie text-tinta"
                }`}
              >
                {NOMES[a]} {formatar(atual[a], unidade)}
              </span>
            ))}
        </div>
        <aside className="w-64 shrink-0 border-l border-linha bg-superficie p-3 text-sm">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-tinta-suave">Medidas</h3>
          {ALCAS.map((a) => (
            <div key={a} className="flex items-center justify-between py-1">
              <span className="text-tinta-suave">{NOMES[a]}</span>
              <span className={`num ${mudou(a) ? "font-semibold text-tinta" : ""}`}>{formatar(atual[a], unidade)}</span>
            </div>
          ))}
          <p className="mt-2 text-xs text-tinta-suave">
            Puxar muda a medida de 1 em 1 cm com o lado oposto parado, e ela entra como "Quero assim". Desfazer, na
            barra de cima, volta.
          </p>
          {editar.isPending && <p className="mt-2 text-xs text-tinta-suave">Gravando…</p>}
          {editar.error && <p className="mt-2 text-sm text-erro">{editar.error.message}</p>}
        </aside>
      </div>
    </div>,
    document.body,
  );
}
