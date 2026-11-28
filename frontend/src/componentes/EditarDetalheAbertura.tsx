import { useEffect, useMemo, useRef, useState } from "react";
import { DoubleSide, Mesh, Plane, Vector3, type Material } from "three";
import { api, ou, type Medida } from "../api/cliente";
import { useCena, useEditar } from "../dados";
import { formatar, type Unidade } from "../unidades";
import {
  aberturaPuxada,
  type AlcaAbertura,
  caixaAbertura,
  cenaDaParede,
  eixoAlcaAbertura,
  type MedidasAbertura,
  pontoAlcaAbertura,
} from "../visor/detalhe";
import { descartar, giroThree, montarCena, paraThree } from "../visor/montarCena";
import { type AlcaTela, CaixaFantasma, JanelaDetalhe, LinhaMedida } from "./JanelaDetalhe";

type V3 = [number, number, number];

const NOMES: Record<AlcaAbertura, string> = { inicio: "Do início", fim: "Largura", altura: "Altura", peitoril: "Peitoril" };

/** O que o detalhe precisa da abertura e da parede dela (formas do projeto.json). */
export type AberturaDetalhe = {
  id: string;
  tipo: "porta" | "janela";
  distancia_inicio: Medida;
  largura: Medida;
  altura: Medida;
  peitoril?: Medida | null;
  abre_para?: string | null;
  de?: string;
};
export type ParedeDetalhe = { id: string; inicio: number[]; fim: number[]; espessura: Medida; lado_a: string; lado_b: string };

/** Quanto de parede aparece de cada lado do vão (mm). */
export function margemParede(largura: number): number {
  return Math.max(500, Math.round(largura * 0.4));
}

/** De que lado a câmera começa: a porta pelo lado para onde abre; a janela por dentro. */
export function ladoDaCamera(a: AberturaDetalhe, p: ParedeDetalhe): 1 | -1 {
  if (a.tipo === "porta") return (a.abre_para ?? a.de) === p.lado_b ? 1 : -1;
  return p.lado_a === "externo" ? 1 : -1;
}

/**
 * "Editar em detalhe" da porta ou janela: o trecho da parede com o vão em 3D (girável) e
 * alças para puxar os dois lados (largura e distância do início), a altura e, na janela, o
 * peitoril — de 1 em 1 cm, com a borda oposta parada, gravando como "Quero assim".
 */
export function EditarDetalheAbertura({
  codigo,
  pavimento,
  abertura: a,
  parede: p,
  unidade,
  aoFechar,
}: {
  codigo: string;
  pavimento: string;
  abertura: AberturaDetalhe;
  parede: ParedeDetalhe;
  unidade: Unidade;
  aoFechar: () => void;
}) {
  const cena = useCena(codigo, { pavimento });
  const editar = useEditar(codigo);
  const janela = a.tipo === "janela";
  const medidas: MedidasAbertura = {
    inicio: a.distancia_inicio.valor,
    largura: a.largura.valor,
    altura: a.altura.valor,
    peitoril: janela ? (a.peitoril?.valor ?? 0) : 0,
  };
  const [atual, setAtual] = useState(medidas);
  const inicio = useRef(medidas);
  const chave = `${medidas.inicio}|${medidas.largura}|${medidas.altura}|${medidas.peitoril}`;
  useEffect(() => setAtual(medidas), [chave, editar.error]); // eslint-disable-line react-hooks/exhaustive-deps

  // referencial do vão: centro do vão no eixo da parede, parede ao longo de x
  const [x0, y0] = p.inicio;
  const [x1, y1] = p.fim;
  const comp = Math.hypot(x1 - x0, y1 - y0) || 1;
  const u = [(x1 - x0) / comp, (y1 - y0) / comp];
  const d = medidas.inicio + medidas.largura / 2;
  const centro = [x0 + u[0] * d, y0 + u[1] * d];
  const angulo = (Math.atan2(u[1], u[0]) * 180) / Math.PI;
  const margem = margemParede(medidas.largura);
  const lado = ladoDaCamera(a, p);
  const esp = p.espessura.valor;

  const grupo = useMemo(() => (cena.data ? montarCena(cenaDaParede(cena.data, p.id)) : null), [cena.data, p.id]);
  useEffect(() => () => void (grupo && descartar(grupo)), [grupo]);
  // só o trecho em volta do vão: corta a parede (já no referencial do detalhe) nos dois lados
  const meio = medidas.largura / 2 + margem;
  useEffect(() => {
    if (!grupo) return;
    const planos = [new Plane(new Vector3(1, 0, 0), meio / 1000), new Plane(new Vector3(-1, 0, 0), meio / 1000)];
    grupo.traverse((o) => {
      if (!(o instanceof Mesh)) return;
      for (const m of (Array.isArray(o.material) ? o.material : [o.material]) as Material[]) {
        m.clippingPlanes = planos;
        m.side = DoubleSide; // o corte mostra o miolo da parede, não um buraco
      }
    });
  }, [grupo, meio]);

  const caixa = caixaAbertura(medidas, atual, esp);
  const alcasIds: AlcaAbertura[] = janela ? ["inicio", "fim", "altura", "peitoril"] : ["inicio", "fim", "altura"];
  const valor = (id: AlcaAbertura) => (id === "fim" ? atual.largura : id === "inicio" ? atual.inicio : atual[id]);
  const alcas: AlcaTela[] = alcasIds.map((id) => ({
    id,
    ponto: pontoAlcaAbertura(id, caixa, lado),
    eixo: eixoAlcaAbertura(id),
    rotulo: `${NOMES[id]} ${formatar(valor(id), unidade)}`,
  }));
  const mudou = (k: keyof MedidasAbertura) => atual[k] !== medidas[k];

  const gravar = () => {
    const campos: Record<string, Medida> = {};
    const m = (valor: number): Medida => ({ valor, origem: "projeto", obs: "puxada no editar em detalhe" });
    if (mudou("inicio")) campos.distancia_inicio = m(atual.inicio);
    if (mudou("largura")) campos.largura = m(atual.largura);
    if (mudou("altura")) campos.altura = m(atual.altura);
    if (janela && mudou("peitoril")) campos.peitoril = m(atual.peitoril);
    if (!Object.keys(campos).length) return;
    editar.mutate((versao) =>
      ou(
        api.PATCH("/projetos/{codigo}/pavimentos/{pavimento}/aberturas/{id_}", {
          params: { path: { codigo, pavimento, id_: a.id }, query: { versao } },
          body: campos,
        }),
      ),
    );
  };

  const titulo = `${janela ? "Janela" : "Porta"} ${a.id}`;
  const alto = (medidas.peitoril + medidas.altura) / 1000;
  return (
    <JanelaDetalhe
      codigo={codigo}
      editar={editar}
      titulo={titulo}
      dica="Puxe as alças amarelas · arraste o fundo para girar · Esc fecha"
      aviso={grupo ? null : cena.error ? cena.error.message : "Montando o 3D…"}
      tam={Math.max((medidas.largura + 2 * margem) / 1000, alto)}
      alvo={[0, alto / 2, 0]}
      ladoCamera={lado}
      alcas={alcas}
      aoComecar={() => (inicio.current = atual)}
      aoPuxar={(id, t) => setAtual(aberturaPuxada(id as AlcaAbertura, inicio.current, t))}
      aoSoltar={gravar}
      aoFechar={aoFechar}
      painel={
        <>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-tinta-suave">Medidas</h3>
          <LinhaMedida nome="Do início da parede" valor={formatar(atual.inicio, unidade)} mudou={mudou("inicio")} />
          <LinhaMedida nome="Largura" valor={formatar(atual.largura, unidade)} mudou={mudou("largura")} />
          <LinhaMedida nome="Altura" valor={formatar(atual.altura, unidade)} mudou={mudou("altura")} />
          {janela && <LinhaMedida nome="Peitoril" valor={formatar(atual.peitoril, unidade)} mudou={mudou("peitoril")} />}
          <p className="mt-2 text-xs text-tinta-suave">
            Na parede {p.id}. Puxar um lado muda a largura com o outro lado parado (o do início muda também a distância)
            {janela ? "; o peitoril muda a altura com o topo parado" : ""}. De 1 em 1 cm, como "Quero assim". Desfazer, na
            barra de cima, volta.
          </p>
        </>
      }
    >
      {grupo && (
        <group rotation-y={-giroThree(angulo)}>
          <group position={paraThree(-centro[0], -centro[1], 0)}>
            <primitive object={grupo} />
          </group>
        </group>
      )}
      {(["inicio", "largura", "altura", "peitoril"] as const).some(mudou) && (
        // um pouco mais grossa que a parede, para aparecer por cima dela
        <CaixaFantasma min={[caixa.min[0], caixa.min[1], caixa.min[2] - 0.01] as V3} max={[caixa.max[0], caixa.max[1], caixa.max[2] + 0.01] as V3} />
      )}
    </JanelaDetalhe>
  );
}
