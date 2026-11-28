import { useState } from "react";
import { api, ou, type Medida, type PavimentoTela } from "../api/cliente";
import { useEditar, useProjeto } from "../dados";
import { proximoId } from "../editor/geometria";
import {
  type ContaEscada,
  type Elemento,
  type Escada,
  FORMAS,
  furoNoCentro,
  furoParaRetangulo,
  girar90,
  NOMES,
  novaEscada,
  novaLaje,
  novaViga,
  novoPilar,
  ordenar,
  type Retangulo,
  resumoEscada,
  retanguloParaFuro,
  SISTEMAS,
} from "../estruturas";
import { btn } from "../estilo";
import { formatar, paraMm, type Unidade } from "../unidades";
import { CampoMedida } from "./CampoMedida";

type Pt = [number, number];
const botao = btn("secundario", "xs");
const titulo = "mb-2 text-xs font-semibold uppercase tracking-wide text-tinta-suave";

/** Número em mm mostrado na unidade da pessoa; Enter ou sair do campo aplica. */
function CampoNumero({ rotulo, mm, unidade, aoMudar }: { rotulo: string; mm: number; unidade: Unidade; aoMudar: (mm: number) => void }) {
  const atual = formatar(mm, unidade, false);
  const [texto, setTexto] = useState<string | null>(null);
  const aplicar = () => {
    const novo = texto === null ? null : paraMm(texto, unidade);
    setTexto(null);
    if (novo !== null && novo !== mm) aoMudar(novo);
  };
  return (
    <label className="flex items-center gap-1 text-xs text-tinta-suave">
      {rotulo}
      <input
        aria-label={rotulo}
        className="w-16 rounded-md border px-1 text-right text-sm text-tinta"
        value={texto ?? atual}
        onFocus={() => setTexto(atual)}
        onChange={(e) => setTexto(e.target.value)}
        onBlur={aplicar}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      />
    </label>
  );
}

/** Ponto (x, y) em mm, coordenadas do andar. */
function CampoPonto({ rotulo, p, unidade, aoMudar }: { rotulo: string; p: number[]; unidade: Unidade; aoMudar: (p: Pt) => void }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1 text-sm">
      <span className="text-tinta-suave">{rotulo}</span>
      <span className="flex gap-2">
        <CampoNumero rotulo="x" mm={p[0]} unidade={unidade} aoMudar={(x) => aoMudar([x, p[1]])} />
        <CampoNumero rotulo="y" mm={p[1]} unidade={unidade} aoMudar={(y) => aoMudar([p[0], y])} />
      </span>
    </div>
  );
}

/** Medida que pode ficar automática (sem valor = a conta decide). */
function MedidaAuto({ rotulo, medida, auto, unidade, ocupado, aoSalvar }: {
  rotulo: string;
  medida?: Medida | null;
  auto: string;
  unidade: Unidade;
  ocupado: boolean;
  aoSalvar: (m: Medida | null) => void;
}) {
  return (
    <div>
      <CampoMedida rotulo={rotulo} medida={medida} unidade={unidade} ocupado={ocupado} aoSalvar={aoSalvar} />
      {medida ? (
        <button className="mb-1 text-xs text-tinta-suave hover:underline" disabled={ocupado} onClick={() => aoSalvar(null)}>
          Voltar ao automático
        </button>
      ) : (
        <p className="-mt-1 mb-1 text-right text-xs text-tinta-suave">automático: {auto}</p>
      )}
    </div>
  );
}

/** Painel da escada: forma, largura, sentido, lances, piso e desnível, e a conta. */
function PainelEscada({ e, conta, unidade, ocupado, alterar }: {
  e: Escada;
  conta: ContaEscada | null;
  unidade: Unidade;
  ocupado: boolean;
  alterar: (campos: Record<string, unknown>) => void;
}) {
  const cm = (mm: number) => formatar(Math.round(mm), unidade);
  const forma = e.forma ?? "reta";
  return (
    <>
      <label className="flex items-center justify-between gap-2 py-1 text-sm">
        <span className="text-tinta-suave">Forma</span>
        <select className="rounded-md border text-sm" value={forma} disabled={ocupado} onChange={(ev) => alterar({ forma: ev.target.value })}>
          {Object.entries(FORMAS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <CampoMedida rotulo={forma === "caracol" ? "Largura do degrau" : "Largura"} medida={e.largura} unidade={unidade} ocupado={ocupado} aoSalvar={(m: Medida) => alterar({ largura: m })} />
      <CampoPonto rotulo={forma === "caracol" ? "Centro" : "Pé da escada"} p={e.inicio} unidade={unidade} aoMudar={(p) => alterar({ inicio: p })} />
      <div className="flex flex-wrap items-center gap-2 py-1">
        <button className={botao} disabled={ocupado} onClick={() => alterar({ direcao: girar90(e.direcao) })} title="Gira o sentido da subida">
          Girar 90°
        </button>
        {forma !== "reta" && (
          <button className={botao} disabled={ocupado} onClick={() => alterar({ gira: e.gira === "direita" ? "esquerda" : "direita" })}>
            Virar para a {e.gira === "direita" ? "esquerda" : "direita"}
          </button>
        )}
      </div>
      {(forma === "L" || forma === "U") && (
        <label className="flex items-center justify-between gap-2 py-1 text-sm">
          <span className="text-tinta-suave">Degraus antes do patamar</span>
          <input
            type="number"
            min={1}
            className="w-16 rounded-md border px-1 text-right"
            placeholder={conta ? String(conta.lances[0]) : ""}
            defaultValue={e.degraus_primeiro_lance ?? ""}
            key={`${e.id}-${e.degraus_primeiro_lance ?? ""}`}
            onBlur={(ev) => {
              const n = ev.target.value === "" ? null : Math.max(1, Math.round(Number(ev.target.value)));
              if (n !== (e.degraus_primeiro_lance ?? null)) alterar({ degraus_primeiro_lance: n });
            }}
          />
        </label>
      )}
      <MedidaAuto rotulo="Piso do degrau" medida={e.piso} auto={conta ? `${cm(conta.piso)} (Blondel)` : "—"} unidade={unidade} ocupado={ocupado} aoSalvar={(m) => alterar({ piso: m })} />
      <MedidaAuto rotulo="Desnível" medida={e.desnivel} auto={conta ? `${cm(conta.desnivel)} (pé-direito + laje)` : "—"} unidade={unidade} ocupado={ocupado} aoSalvar={(m) => alterar({ desnivel: m })} />
      {conta && (
        <div className="mt-2 rounded-md bg-papel p-2 text-xs">
          {resumoEscada(conta, cm).map((l) => (
            <p key={l}>{l}</p>
          ))}
          <p className="mt-1 text-tinta-suave">A laje deste andar ganha o furo sozinha onde a cabeça bateria (menos de 2,10 m).</p>
        </div>
      )}
    </>
  );
}

/**
 * Aba **Estruturas**: lajes, vigas e pilares do andar. Lista, acrescenta e edita o escolhido
 * (medidas com a origem, posição, tipo de laje e furos). Na planta, o pilar se arrasta (gruda
 * nos cantos das paredes) e clicar num pilar ou viga escolhe.
 */
export function PainelEstruturas({
  codigo,
  pavimento,
  geometria,
  comodo,
  unidade,
  sel,
  aoSelecionar,
}: {
  codigo: string;
  pavimento: string;
  geometria: PavimentoTela;
  /** Cômodo escolhido: pilar e furo novos nascem no centro dele. */
  comodo: string | null;
  unidade: Unidade;
  sel: string | null;
  aoSelecionar: (id: string | null) => void;
}) {
  const projeto = useProjeto(codigo).data;
  const editar = useEditar(codigo);
  const [paredeViga, setParedeViga] = useState("");
  const [formaEscada, setFormaEscada] = useState<NonNullable<Escada["forma"]>>("reta");
  const pav = projeto?.projeto.pavimentos.find((p) => p.id === pavimento);
  const itens = ordenar((pav?.estrutura ?? []) as Elemento[]);
  const base = { codigo, pavimento };
  const ids = itens.map((e) => e.id);
  const centroComodo = (): Pt => {
    const c = geometria.comodos.find((x) => x.id === comodo)?.centro ?? geometria.comodos.find((x) => x.centro)?.centro;
    if (c) return [c[0], c[1]];
    const [[x0, y0], [x1, y1]] = geometria.limites ?? [[0, 0], [0, 0]];
    return [(x0 + x1) / 2, (y0 + y1) / 2];
  };

  const criar = (e: Elemento) =>
    editar.mutate(
      (versao) => ou(api.POST("/projetos/{codigo}/pavimentos/{pavimento}/estrutura", { params: { path: base, query: { versao } }, body: e })),
      { onSuccess: () => aoSelecionar(e.id) },
    );
  const alterar = (id: string, campos: Record<string, unknown>) =>
    editar.mutate((versao) =>
      ou(api.PATCH("/projetos/{codigo}/pavimentos/{pavimento}/estrutura/{id_}", { params: { path: { ...base, id_: id }, query: { versao } }, body: campos })),
    );
  const remover = (id: string) =>
    editar.mutate(
      (versao) => ou(api.DELETE("/projetos/{codigo}/pavimentos/{pavimento}/estrutura/{id_}", { params: { path: { ...base, id_: id }, query: { versao } } })),
      { onSuccess: () => aoSelecionar(null) },
    );

  const e = itens.find((x) => x.id === sel);
  const tela = geometria.estrutura?.find((x) => x.id === sel);
  const temLaje = itens.some((x) => x.tipo === "laje");
  const paredes = geometria.paredes;

  return (
    <>
      <section className="border-b border-linha p-3">
        <h2 className={titulo}>Estrutura do andar</h2>
        {itens.length ? (
          <ul className="mb-2 flex flex-col gap-0.5 text-sm">
            {itens.map((x) => {
              const est = geometria.estrutura?.find((t) => t.id === x.id)?.estimada;
              return (
                <li key={x.id}>
                  <button
                    className={`flex w-full items-center justify-between rounded-md px-2 py-1 text-left ${x.id === sel ? "bg-trena/30 font-medium" : "hover:bg-superficie-2"}`}
                    onClick={() => aoSelecionar(x.id === sel ? null : x.id)}
                  >
                    <span>
                      {NOMES[x.tipo]} <span className="text-tinta-suave">{x.id}</span>
                    </span>
                    {est && <span className="text-xs text-chute">chute</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="mb-2 text-sm text-tinta-suave">Nenhum pilar, viga ou laje neste andar ainda.</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {!temLaje && (
            <button className={botao} disabled={editar.isPending} onClick={() => criar(novaLaje(proximoId("laje-", ids)))} title="Cobre o andar inteiro por fora das paredes">
              + Laje do andar
            </button>
          )}
          <button className={botao} disabled={editar.isPending} onClick={() => criar(novoPilar(proximoId("pilar-", ids), centroComodo()))} title="No centro do cômodo escolhido; arraste na planta">
            + Pilar
          </button>
          <span className="flex items-center gap-1">
            <select className="rounded-md border text-xs" value={formaEscada} onChange={(ev) => setFormaEscada(ev.target.value as typeof formaEscada)} aria-label="forma da escada nova">
              {Object.entries(FORMAS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <button
              className={botao}
              disabled={editar.isPending}
              title="No centro do cômodo escolhido, subindo para a direita; arraste na planta"
              onClick={() => criar(novaEscada(proximoId("escada-", ids), centroComodo(), formaEscada))}
            >
              + Escada
            </button>
          </span>
          <span className="flex items-center gap-1">
            <select className="rounded-md border text-xs" value={paredeViga} onChange={(ev) => setParedeViga(ev.target.value)} aria-label="parede da viga nova">
              <option value="">viga sobre a parede…</option>
              {paredes.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id}
                </option>
              ))}
            </select>
            <button
              className={botao}
              disabled={editar.isPending || !paredeViga}
              onClick={() => {
                const p = paredes.find((x) => x.id === paredeViga);
                if (p) criar(novaViga(proximoId("viga-", ids), { eixo: p.eixo as [Pt, Pt], espessura: p.espessura }));
              }}
            >
              + Viga
            </button>
          </span>
        </div>
        <p className="mt-2 text-xs text-tinta-suave">
          Tamanho novo entra como chute; ajuste com Medi / Quero assim. O sistema aponta restrições, não substitui o
          engenheiro.
        </p>
        {editar.error && <p className="mt-1 text-sm text-erro">{editar.error.message}</p>}
      </section>

      {e && (
        <section className="border-b border-linha p-3">
          <h2 className={titulo}>
            {NOMES[e.tipo]} {e.id}
          </h2>
          {e.tipo === "pilar" && (
            <>
              <CampoMedida rotulo="Largura (x)" medida={e.largura} unidade={unidade} ocupado={editar.isPending} aoSalvar={(m: Medida) => alterar(e.id, { largura: m })} />
              <CampoMedida rotulo="Profundidade (y)" medida={e.profundidade} unidade={unidade} ocupado={editar.isPending} aoSalvar={(m: Medida) => alterar(e.id, { profundidade: m })} />
              <CampoPonto rotulo="Centro" p={e.centro} unidade={unidade} aoMudar={(p) => alterar(e.id, { centro: p })} />
              <p className="text-xs text-tinta-suave">Arraste o pilar na planta: ele gruda nos cantos das paredes.</p>
            </>
          )}
          {e.tipo === "viga" && (
            <>
              <CampoMedida rotulo="Largura" medida={e.largura} unidade={unidade} ocupado={editar.isPending} aoSalvar={(m: Medida) => alterar(e.id, { largura: m })} />
              <CampoMedida rotulo="Altura (desce da laje)" medida={e.altura} unidade={unidade} ocupado={editar.isPending} aoSalvar={(m: Medida) => alterar(e.id, { altura: m })} />
              <CampoPonto rotulo="Início" p={e.inicio} unidade={unidade} aoMudar={(p) => alterar(e.id, { inicio: p })} />
              <CampoPonto rotulo="Fim" p={e.fim} unidade={unidade} aoMudar={(p) => alterar(e.id, { fim: p })} />
            </>
          )}
          {e.tipo === "escada" && (
            <PainelEscada e={e} conta={tela?.escada ?? null} unidade={unidade} ocupado={editar.isPending} alterar={(campos) => alterar(e.id, campos)} />
          )}
          {e.tipo === "laje" && (
            <>
              <CampoMedida rotulo="Espessura" medida={e.espessura} unidade={unidade} ocupado={editar.isPending} aoSalvar={(m: Medida) => alterar(e.id, { espessura: m })} />
              <label className="flex items-center justify-between gap-2 py-1 text-sm">
                <span className="text-tinta-suave">Tipo</span>
                <select className="rounded-md border text-sm" value={e.sistema ?? "pre_moldada"} disabled={editar.isPending} onChange={(ev) => alterar(e.id, { sistema: ev.target.value })}>
                  {Object.entries(SISTEMAS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <p className="py-1 text-sm text-tinta-suave">{e.contorno ? "Contorno próprio" : "Cobre o andar inteiro, por fora das paredes"}</p>
              <h3 className="mb-1 mt-2 text-xs font-semibold text-tinta-suave">Furos (escada, shaft, claraboia)</h3>
              {(e.furos ?? []).map((f, i) => {
                const r = furoParaRetangulo(f);
                const mudar = (novo: Partial<Retangulo>) =>
                  alterar(e.id, { furos: (e.furos ?? []).map((g, k) => (k === i ? retanguloParaFuro({ ...r, ...novo }) : g)) });
                return (
                  <div key={i} className="mb-1 rounded-md bg-papel p-1.5">
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span>Furo {i + 1}</span>
                      <button className="text-erro hover:underline" disabled={editar.isPending} onClick={() => alterar(e.id, { furos: (e.furos ?? []).filter((_, k) => k !== i) })}>
                        Tirar
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <CampoNumero rotulo="x" mm={r.x} unidade={unidade} aoMudar={(x) => mudar({ x })} />
                      <CampoNumero rotulo="y" mm={r.y} unidade={unidade} aoMudar={(y) => mudar({ y })} />
                      <CampoNumero rotulo="larg." mm={r.largura} unidade={unidade} aoMudar={(largura) => mudar({ largura })} />
                      <CampoNumero rotulo="comp." mm={r.comprimento} unidade={unidade} aoMudar={(comprimento) => mudar({ comprimento })} />
                    </div>
                  </div>
                );
              })}
              <button className={botao} disabled={editar.isPending} onClick={() => alterar(e.id, { furos: [...(e.furos ?? []), furoNoCentro(centroComodo())] })}>
                + Furo
              </button>
              <p className="mt-1 text-xs text-tinta-suave">
                O furo da escada vai ser criado sozinho quando a escada chegar; aqui dá para abrir outros.
              </p>
            </>
          )}
          {tela?.estimada && <p className="mt-2 text-xs text-chute">Tem medida chutada: os desenhos saem como PRELIMINAR.</p>}
          <button className={`${botao} mt-3 text-erro`} disabled={editar.isPending} onClick={() => remover(e.id)}>
            Remover
          </button>
        </section>
      )}
    </>
  );
}
