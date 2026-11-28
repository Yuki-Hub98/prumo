import type { ThreeEvent } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import { DoubleSide } from "three";
import { api, ou } from "../api/cliente";
import { useCena, useEditar, usePlanejado } from "../dados";
import { btn } from "../estilo";
import {
  alternarPorta,
  alturaEspaco,
  type Construcao,
  larguraVao,
  moverEspaco,
  puxarAlturaEspaco,
  puxarLarguraVao,
  removerEspaco,
  TIPOS_ESPACO,
  tipoEspaco,
  type TipoEspaco,
} from "../planejado";
import { formatar, type Unidade } from "../unidades";
import {
  type Alca,
  type AlcaParte,
  alcasDaParte,
  type Borda,
  caixaPuxada,
  cenaDoMovel,
  eixoAlca,
  eixoParte,
  type Medidas,
  medidaParte,
  medidaPuxada,
  naFrente,
  type Parte,
  pontoDaAlca,
  pontoParte,
  type Regiao,
  regiaoDoEspaco,
  regiaoPuxada,
  regioesClicaveis,
} from "../visor/detalhe";
import { descartar, giroThree, montarCena, paraThree } from "../visor/montarCena";
import { CampoAuto } from "./EditorPlanejado";
import { type AlcaTela, CaixaFantasma, corToken, JanelaDetalhe, LinhaMedida } from "./JanelaDetalhe";

const NOMES: Record<Alca, string> = { largura: "Largura", profundidade: "Profundidade", altura: "Altura" };
const ALCAS: Alca[] = ["largura", "profundidade", "altura"];
const NOME_PARTE: Record<AlcaParte, string> = { altura: "Altura do espaço", largura: "Largura do vão" };

type V3 = [number, number, number];

/** Retângulo plano (m) na frente do móvel: clicável (invisível) ou pintado (seleção). */
function Placa({ r, m, cor, opacidade, aoClicar, aoPassar }: {
  r: Pick<Regiao, "x" | "y" | "largura" | "altura">;
  m: Medidas;
  cor: string;
  opacidade: number;
  aoClicar?: (e: ThreeEvent<MouseEvent>) => void;
  aoPassar?: (dentro: boolean) => void;
}) {
  const { centro, tamanho } = naFrente(r, m);
  return (
    <mesh
      position={centro}
      onClick={aoClicar}
      onPointerOver={aoPassar && ((e) => (e.stopPropagation(), aoPassar(true)))}
      onPointerOut={aoPassar && (() => aoPassar(false))}
    >
      <planeGeometry args={tamanho} />
      <meshBasicMaterial color={cor} transparent opacity={opacidade} depthWrite={false} side={DoubleSide} />
    </mesh>
  );
}

/**
 * "Editar em detalhe" do móvel: **só ele** em 3D, com alças para puxar largura, profundidade e
 * altura (passo de 1 cm, lado oposto parado, grava como "Quero assim"). No planejado, clicar
 * numa gaveta, nicho, cabideiro ou prateleira escolhe aquele espaço: o painel edita o espaço e
 * o vão dele, e as alças passam a puxar a altura do espaço e a largura do vão.
 */
export function EditarDetalhe({
  codigo,
  comodo,
  id,
  nome,
  centro,
  rotacao,
  medidas,
  construcao,
  portas,
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
  construcao?: Construcao | null;
  portas?: "abrir" | "correr" | null;
  unidade: Unidade;
  aoFechar: () => void;
}) {
  const cena = useCena(codigo, { comodo });
  const editar = useEditar(codigo);
  const vista = usePlanejado(codigo, comodo, id, !!construcao).data;
  const caminho = { codigo, comodo, id_: id };
  const [atual, setAtual] = useState<Medidas>(medidas);
  const [sel, setSel] = useState<Parte | null>(null);
  const [sobre, setSobre] = useState<Parte | null>(null);
  const [semPortas, setSemPortas] = useState(false);
  /** Medida da parte enquanto puxa (ou até a vista nova chegar). */
  const [puxada, setPuxada] = useState<{ alca: AlcaParte; valor: number } | null>(null);
  const inicio = useRef<Medidas>(medidas);

  // medida nova gravada (ou desfeita): volta a acompanhar o projeto
  const chave = `${medidas.largura}|${medidas.profundidade}|${medidas.altura}|${medidas.base}`;
  useEffect(() => setAtual(medidas), [chave]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => setPuxada(null), [vista, editar.error]);
  // a parte escolhida sumiu (desfeita, tirada): volta ao móvel
  const c = construcao ?? null;
  const selValida = sel && c && sel.vao < c.vaos.length && sel.espaco < c.vaos[sel.vao].espacos.length ? sel : null;

  const grupo = useMemo(() => (cena.data ? montarCena(cenaDoMovel(cena.data, id)) : null), [cena.data, id]);
  useEffect(() => () => void (grupo && descartar(grupo)), [grupo]);
  // sem portas: esconde as folhas para ver (e clicar) o que tem atrás
  useEffect(() => {
    grupo?.traverse((o) => void ((o.userData.parte === "portas" || o.userData.da_porta) && (o.visible = !semPortas)));
  }, [grupo, semPortas]);

  const tam = Math.max(medidas.largura, medidas.profundidade, medidas.base + medidas.altura) / 1000;
  const alvo: V3 = [0, (medidas.base + medidas.altura) / 2 / 1000, 0];
  const amarelo = corToken("--trena", "#f2b200");
  const mudou = (a: Alca) => atual[a] !== medidas[a];

  const gravarConstrucao = (nova: Construcao) =>
    editar.mutate((versao) =>
      ou(
        api.PUT("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/construcao", {
          params: { path: caminho, query: { versao } },
          body: { construcao: nova },
        }),
      ),
    );
  const gravarMovel = (alca: Alca, valor: number) =>
    editar.mutate((versao) => {
      if (alca === "altura")
        return ou(
          api.PATCH("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}", {
            params: { path: caminho, query: { versao } },
            body: { altura: { valor, origem: "projeto", obs: "puxada no editar em detalhe" } },
          }),
        );
      return ou(
        api.POST("/projetos/{codigo}/comodos/{comodo}/moveis/{id_}/redimensionar", {
          params: { path: caminho, query: { versao } },
          body: { lado: alca === "largura" ? "direita" : "frente", tamanho: valor },
        }),
      );
    });

  // ---------------------------------------------------------------- alças
  const regiao = selValida && vista ? regiaoDoEspaco(vista.retangulos, selValida) : undefined;
  const valorParte = (alca: AlcaParte) =>
    selValida && vista
      ? alca === "altura"
        ? (vista.alturas[selValida.vao]?.[selValida.espaco] ?? 0)
        : (vista.larguras_vaos[selValida.vao] ?? 0)
      : 0;
  const bordas = selValida && c ? alcasDaParte(selValida, c.vaos.length, c.vaos[selValida.vao].espacos.length) : [];
  const regiaoAgora = (alca: AlcaParte, borda: Borda) =>
    regiao && (puxada?.alca === alca ? regiaoPuxada(regiao, alca, borda, puxada.valor) : regiao);

  let alcas: AlcaTela[];
  if (regiao) {
    alcas = bordas.map(({ alca, borda }) => ({
      id: alca,
      ponto: pontoParte(regiaoAgora(alca, borda)!, alca, borda, medidas),
      eixo: eixoParte(alca, borda),
      rotulo: `${NOME_PARTE[alca]} ${formatar(puxada?.alca === alca ? puxada.valor : valorParte(alca), unidade)}`,
    }));
  } else {
    const caixa = caixaPuxada(medidas, atual);
    alcas = ALCAS.map((a) => ({ id: a, ponto: pontoDaAlca(a, caixa), eixo: eixoAlca(a), rotulo: `${NOMES[a]} ${formatar(atual[a], unidade)}` }));
  }

  const aoComecar = () => {
    inicio.current = atual;
  };
  const aoPuxar = (alca: string, t: number) => {
    if (regiao) setPuxada({ alca: alca as AlcaParte, valor: medidaParte(valorParte(alca as AlcaParte), t) });
    else setAtual((m) => ({ ...m, [alca]: medidaPuxada(alca as Alca, inicio.current, t) }));
  };
  const aoSoltar = (alca: string) => {
    if (regiao && selValida && c) {
      const borda = bordas.find((b) => b.alca === puxada?.alca)?.borda;
      if (puxada && borda && Math.round(puxada.valor) !== Math.round(valorParte(puxada.alca))) {
        const passo = borda === "fim" ? 1 : -1;
        const { vao: i, espaco: j } = selValida;
        gravarConstrucao(
          puxada.alca === "altura"
            ? puxarAlturaEspaco(c, i, j, j + passo, puxada.valor, valorParte("altura"))
            : puxarLarguraVao(c, i, i + passo, puxada.valor, valorParte("largura")),
        );
      } else setPuxada(null);
      return;
    }
    const a = alca as Alca;
    if (atual[a] !== medidas[a]) gravarMovel(a, atual[a]);
  };

  // ---------------------------------------------------------------- painel
  const painel =
    selValida && c ? (
      <PainelParte
        c={c}
        p={selValida}
        portas={portas}
        vista={vista}
        unidade={unidade}
        ocupado={editar.isPending}
        gravar={gravarConstrucao}
        aoEscolher={setSel}
      />
    ) : (
      <>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-tinta-suave">Medidas</h3>
        {ALCAS.map((a) => (
          <LinhaMedida key={a} nome={NOMES[a]} valor={formatar(atual[a], unidade)} mudou={mudou(a)} />
        ))}
        <p className="mt-2 text-xs text-tinta-suave">
          Puxar muda a medida de 1 em 1 cm com o lado oposto parado, e ela entra como "Quero assim". Desfazer, na
          barra de cima, volta.
        </p>
        {c && (
          <p className="mt-2 rounded-md bg-papel p-2 text-xs">
            Clique numa gaveta, nicho ou prateleira para editar aquela parte.
          </p>
        )}
      </>
    );

  return (
    <JanelaDetalhe
      codigo={codigo}
      editar={editar}
      titulo={nome}
      dica={c ? "Clique numa parte para editá-la · puxe as alças amarelas · Esc fecha" : "Puxe as alças amarelas · arraste o fundo para girar · Esc fecha"}
      aviso={grupo ? null : cena.error ? cena.error.message : "Montando o 3D…"}
      tam={tam}
      alvo={alvo}
      alcas={alcas}
      aoComecar={aoComecar}
      aoPuxar={aoPuxar}
      aoSoltar={aoSoltar}
      aoClicarFundo={() => setSel(null)}
      aoFechar={aoFechar}
      painel={
        <>
          {c && portas && (
            <label className="mb-3 flex items-center gap-2 text-xs text-tinta-suave">
              <input type="checkbox" checked={semPortas} onChange={(e) => setSemPortas(e.target.checked)} />
              Esconder as portas
            </label>
          )}
          {painel}
        </>
      }
    >
      {/* o móvel no referencial dele: sem o giro da planta, centro na origem */}
      {grupo && (
        <group rotation-y={-giroThree(rotacao)}>
          <group position={paraThree(-centro[0], -centro[1], 0)}>
            <primitive object={grupo} />
          </group>
        </group>
      )}
      {!regiao && ALCAS.some(mudou) && <CaixaFantasma {...caixaPuxada(medidas, atual)} />}
      {/* partes do planejado: placas invisíveis na frente para clicar; a escolhida em amarelo */}
      {c &&
        vista &&
        regioesClicaveis(vista.retangulos).map((r, i) => {
          const p = { vao: r.vao, espaco: r.espaco };
          const igual = (q: Parte | null) => q?.vao === p.vao && q.espaco === p.espaco;
          return (
            <Placa
              key={i}
              r={r}
              m={medidas}
              cor={amarelo}
              opacidade={igual(sobre) && !igual(selValida) ? 0.15 : 0}
              aoClicar={(e) => {
                e.stopPropagation();
                if (e.delta < 4) setSel(p); // arrastar para girar não escolhe
              }}
              aoPassar={(dentro) => setSobre((s) => (dentro ? p : igual(s) ? null : s))}
            />
          );
        })}
      {regiao && (
        <Placa
          r={puxada ? regiaoPuxada(regiao, puxada.alca, bordas.find((b) => b.alca === puxada.alca)?.borda ?? "fim", puxada.valor) : regiao}
          m={medidas}
          cor={amarelo}
          opacidade={0.35}
        />
      )}
    </JanelaDetalhe>
  );
}

/** Painel da parte escolhida: o espaço (tipo, altura, posição) e o vão dele (largura, porta). */
function PainelParte({
  c,
  p,
  portas,
  vista,
  unidade,
  ocupado,
  gravar,
  aoEscolher,
}: {
  c: Construcao;
  p: Parte;
  portas?: "abrir" | "correr" | null;
  vista?: { larguras_vaos: number[]; alturas: number[][] };
  unidade: Unidade;
  ocupado: boolean;
  gravar: (nova: Construcao) => void;
  aoEscolher: (p: Parte | null) => void;
}) {
  const vao = c.vaos[p.vao];
  const esp = vao.espacos[p.espaco];
  const n = vao.espacos.length;
  const titulo = "mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-tinta-suave";
  const auto = (mm: number | undefined) => mm !== undefined && <span className="text-[11px] text-tinta-suave">= {formatar(mm, unidade)}</span>;
  return (
    <>
      <button className={`${btn("fantasma", "xs")} -ml-1 mb-1`} onClick={() => aoEscolher(null)}>
        ← Móvel inteiro
      </button>
      <h3 className={titulo}>
        Espaço {p.espaco + 1} de {n} (de baixo) · vão {p.vao + 1}
      </h3>
      <label className="flex items-center justify-between gap-2 py-1">
        <span className="text-tinta-suave">Tipo</span>
        <select
          className="rounded-md border text-sm"
          value={esp.tipo}
          disabled={ocupado}
          onChange={(e) => gravar(tipoEspaco(c, p.vao, p.espaco, e.target.value as TipoEspaco))}
        >
          {TIPOS_ESPACO.map((t) => (
            <option key={t.id} value={t.id}>
              {t.nome}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-center justify-between gap-2 py-1">
        <span className="text-tinta-suave">Altura</span>
        <span className="flex items-center gap-1">
          {!esp.altura && auto(vista?.alturas[p.vao]?.[p.espaco])}
          <CampoAuto mm={esp.altura?.valor} unidade={unidade} rotulo="altura do espaço" aoMudar={(mm) => gravar(alturaEspaco(c, p.vao, p.espaco, mm))} />
        </span>
      </div>
      <div className="mt-1 flex flex-wrap gap-1">
        <button
          className={btn("secundario", "xs")}
          disabled={ocupado || p.espaco === n - 1}
          onClick={() => (gravar(moverEspaco(c, p.vao, p.espaco, 1)), aoEscolher({ ...p, espaco: p.espaco + 1 }))}
        >
          ↑ Subir
        </button>
        <button
          className={btn("secundario", "xs")}
          disabled={ocupado || p.espaco === 0}
          onClick={() => (gravar(moverEspaco(c, p.vao, p.espaco, -1)), aoEscolher({ ...p, espaco: p.espaco - 1 }))}
        >
          ↓ Descer
        </button>
        <button
          className={`${btn("secundario", "xs")} text-erro`}
          disabled={ocupado || n <= 1}
          onClick={() => (gravar(removerEspaco(c, p.vao, p.espaco)), aoEscolher(null))}
        >
          Tirar
        </button>
      </div>

      <h3 className={titulo}>Vão {p.vao + 1} de {c.vaos.length}</h3>
      <div className="flex items-center justify-between gap-2 py-1">
        <span className="text-tinta-suave">Largura</span>
        <span className="flex items-center gap-1">
          {!vao.largura && auto(vista?.larguras_vaos[p.vao])}
          <CampoAuto mm={vao.largura?.valor} unidade={unidade} rotulo="largura do vão" aoMudar={(mm) => gravar(larguraVao(c, p.vao, mm))} />
        </span>
      </div>
      {portas === "abrir" && (
        <label className="flex items-center gap-2 py-1">
          <input type="checkbox" checked={vao.porta !== false} disabled={ocupado} onChange={() => gravar(alternarPorta(c, p.vao))} />
          Com porta
        </label>
      )}
      <p className="mt-3 text-xs text-tinta-suave">
        Puxe as alças para mudar a altura do espaço e a largura do vão de 1 em 1 cm, como mover a prateleira ou a
        divisória: o vizinho do outro lado cede o espaço. Vazio = automático (divide o que sobra). Desfazer volta.
      </p>
    </>
  );
}
