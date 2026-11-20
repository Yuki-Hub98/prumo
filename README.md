# PRUMO

## interiores

> Projeto de interiores a partir de medidas reais: plantas DXF/PDF, renders 3D no Blender e checagens de obra, tudo gerado por código.

![status](https://img.shields.io/badge/status-em%20desenvolvimento-orange)
![python](https://img.shields.io/badge/python-3.12-blue)
![commits](https://img.shields.io/badge/commits-conventional-brightgreen)

Você mede o cômodo com a trena, anota num croqui e o sistema faz o resto: modelo 3D com várias opções de cor e móvel para comparar, plantas e cortes cotados para levar ao marceneiro e uma lista de problemas antes de furar qualquer parede.

Nada é desenhado à mão. Tudo é gerado a partir de arquivos JSON de medidas: mudou uma medida, os desenhos e as imagens são refeitos.

---

## ⚠️ Dependência obrigatória: `uv`

> [!IMPORTANT]
> **Sem o [uv](https://docs.astral.sh/uv/) instalado, o projeto não funciona.**
> Ele instala o Python 3.12 e todas as bibliotecas, roda a CLI (`uv run interiores ...`),
> os testes, o `make` e os hooks de commit (pre-commit e commitizen chamam `uv run`).
> Dependências novas entram com `uv add`; nunca com `pip`.

**Instalar** (Linux/macOS, sem `sudo`; vai para `~/.local/bin`):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

**Conferir** (abra um terminal novo antes, para o `PATH` atualizar):

```bash
uv --version
uv sync --all-packages   # cria o .venv com tudo
```

Se aparecer `uv: comando não encontrado`, adicione `~/.local/bin` ao `PATH`
(`export PATH="$HOME/.local/bin:$PATH"` no `~/.bashrc`) e abra outro terminal.

---

## Por que existe

Reformar sem projeto costuma terminar em guarda-roupa que não abre por causa da cama, tomada atrás do móvel ou furo no lugar do cano. Este projeto existe para:

- **separar o que foi medido do que foi chutado.** Cada medida diz a origem: `trena`, `estimada` ou `projeto`;
- **impedir que um desenho com chute vá para a obra.** Enquanto houver medida estimada, tudo sai marcado como **"PRELIMINAR — NÃO USAR PARA OBRA"**;
- **comparar opções antes de comprar**, com cores, móveis e layouts lado a lado;
- **achar problemas cedo**: passagem estreita, porta batendo em móvel, tomada obstruída, pilar onde não se fura.

## O que ele gera

| Saída | Como | Formato |
|---|---|---|
| Modelo 3D e imagens realistas, com variações | Blender headless | `.png`, `.glb`, `.blend` |
| Planta, cortes e elevações em escala, com cotas | ezdxf | `.dxf`, `.pdf` |
| Comparações lado a lado | Pillow | `.png` |
| Cálculo de tinta e materiais | openpyxl | `.xlsx` |
| Relatório de problemas | regras do `core` | terminal / API |

## Como funciona

```
fotos + croqui com trena          frontend (editor)
        │                                │
        ▼                                ▼
projetos/<projeto>/*.json  ◄──────►  API (FastAPI) ──► PostgreSQL ← fonte da verdade
  (exportação versionada;      importar/                (medidas em mm + origem,
   CLI e Claude editam aqui)   exportar                  histórico e versões)
        │
        ▼
core: valida, edita, monta a geometria e roda as checagens
        │
        ├──► cad        → plantas e cortes DXF/PDF
        ├──► render     → cenas e imagens no Blender
        └──► relatorios → comparações e tinta
```

O modelo é hierárquico: **Projeto → Imóvel → Pavimento → Cômodo**. O desenvolvimento começa pelo quarto, mas o schema já é o de uma casa inteira, com paredes compartilhadas entre cômodos, portas ligando ambientes e instalações (elétrica, água, esgoto, gás) por pavimento.

### Exemplo de medida

```json
{ "valor": 3150, "origem": "trena", "obs": "parede da janela, rodapé a rodapé" }
```

Unidade interna: **milímetros**. Origens possíveis: `trena`, `estimada`, `projeto`.

## Stack

- **Python 3.12** com [uv](https://docs.astral.sh/uv/) em workspace (monorepo)
- **pydantic v2**, **shapely**: modelo, validação e geometria
- **ezdxf** + **matplotlib**: desenho técnico
- **Blender LTS** (headless, via `bpy`): 3D e renders
- **FastAPI**, **SQLAlchemy**, **Alembic**, **arq**: API e fila de jobs
- **PostgreSQL**, **Redis**, **MinIO**: dados, fila e arquivos gerados
- **React + Vite + TypeScript**, **react-three-fiber**: frontend com visor 3D
- **Docker / Docker Compose**

## Estrutura

```
.
├── projetos/        # exportação do banco (medidas e variações), versionada
├── packages/
│   ├── core/        # modelo, validação, regras, edição da planta, tipos de cômodo
│   ├── banco/       # PostgreSQL: tabelas, migrações, importar/exportar
│   ├── cad/         # plantas e cortes
│   ├── render/      # scripts do Blender
│   ├── relatorios/  # comparações, tinta
│   └── cli/         # comando `interiores`
├── services/
│   ├── api/         # FastAPI
│   └── worker/      # jobs em fila
├── frontend/        # React
├── docker/          # Dockerfiles
└── out/             # saídas geradas (não versionado)
```

## Começando

> ⚠️ O projeto está no início. Os comandos abaixo descrevem o fluxo planejado.

Pré-requisitos: **[uv](https://docs.astral.sh/uv/) (obrigatório — veja a seção "Dependência obrigatória: `uv`" no topo)**, Docker e Docker Compose. O Blender só é necessário fora do Docker.

```bash
git clone https://github.com/Yuki-Hub98/interiores.git
cd interiores
cp .env.example .env
make setup        # uv sync + pre-commit install
make dev          # TUDO de uma vez: infra + migrações + API + worker + tela (Ctrl+C para)
make wiki         # documentação completa em http://localhost:3000 (Wiki.js)
```

A documentação (uso, arquitetura, modelo de dados, desenvolvimento) fica em `docs/wiki/`
e é servida pela Wiki.js; na primeira vez, siga "Como esta wiki funciona" em
`docs/wiki/home.md`.

Banco e API (o banco é a fonte da verdade; `projetos/` é a exportação dele):

```bash
make banco                        # sobe o Postgres e aplica as migrações
make importar P=casa              # arquivos → banco (nova versão)
make api                          # API em http://localhost:8010/docs
make exportar P=casa              # banco → arquivos (a API já faz isso a cada edição)
```

Imagens 3D pela tela (fila Redis + worker que chama o Blender):

```bash
make worker                  # sobe o Redis e consome a fila (um render por vez)
```

No frontend, clique num cômodo e use "Imagens 3D": **rascunho** (segundos) ou **final**
(~2 min), com estimativa pelo histórico da máquina e barra de progresso lida do Blender.

Frontend (planta 2D com edição de móveis; precisa da API):

```bash
cd frontend && npm install   # só na primeira vez
make frontend                # http://localhost:5173
```

Editou o JSON à mão (ou pela CLI)? Rode `make importar`. Se o banco e os arquivos mudaram
desde a última sincronização, importar e exportar recusam e avisam (`F=1` escolhe um lado).
Toda edição pela API exige `?versao=` (a versão que a tela estava vendo): se alguém gravou
antes, a resposta é 409 e a tela recarrega em vez de atropelar.

Sem Docker (core, CAD e CLI):

```bash
make validate P=casa              # valida medidas + checagens
make cad P=casa C=quarto          # planta, cortes AA/BB e elevação de cada parede
```

A planta do cômodo mostra o id de cada parede (`p1`, `p2`...) e as linhas dos cortes AA e
BB; cada parede vira `elevacao-<id>.pdf` (vista de dentro do cômodo, com portas, janelas,
tomadas, pontos de água e móveis na altura certa).

Móveis (catálogo com medidas padrão, que entram como estimadas e podem ser ajustadas):

```bash
uv run interiores catalogo                      # tipos de móvel
uv run interiores catalogo tv                   # modelos de um tipo
uv run interiores movel adicionar casa quarto tv --modelo 50pol --parede p7 --a 400 --elevacao 1000
uv run interiores movel adicionar casa quarto cama --em 2485,1325 --rotacao 90
uv run interiores movel mover casa quarto tv --parede p2 --a 1200
uv run interiores movel listar casa quarto
uv run interiores movel remover casa quarto tv
```

Duas formas de posicionar:

- `--parede <id> --a <mm>`: prende as costas do móvel na parede, virado para o cômodo
  (`--a` é a distância do início da parede até a borda do móvel, como nas portas e janelas);
- `--em x,y --rotacao r`: centro em mm no sistema do pavimento; rotação 0/90/180/270 (em 0
  a frente do móvel aponta para cima na planta).

`--elevacao` deixa o móvel suspenso (TV na parede, armário aéreo). Depois de cada mudança
as checagens do cômodo rodam.

Móveis planejados (por dentro: vãos, gavetas, prateleiras, cabideiros, portas e chapas):

```bash
uv run interiores planejado criar casa quarto guarda-roupa   # construção padrão do tipo
uv run interiores planejado gerar casa quarto                # todos os planejados do cômodo
make planejado P=casa C=quarto M=guarda-roupa
```

Gera em `out/<projeto>/<pavimento>/<cômodo>/base/` o desenho técnico do móvel
(`planejado-<móvel>.dxf/.pdf`: vista frontal sem portas e vista lateral, cotadas) e a
lista de corte `planejado-<móvel>-corte.xlsx` (peças com medidas e fita de borda,
ferragens e estimativa de chapas). A construção fica no campo `construcao` do móvel em
`comodos/<cômodo>.json`; vãos sem largura e espaços sem altura dividem igualmente o que
sobra.

Render 3D (Blender LTS headless; sem Blender instalado, usa a imagem Docker):

```bash
make blender-imagem                        # uma vez: interiores-blender:4.5.16 (~2 GB)
make render P=casa C=quarto                # perspectiva + vista de cima + quarto.glb
make render P=casa C=quarto V=todas        # todas as variações de cor
```

Saídas em `out/<projeto>/<pavimento>/<cômodo>/<variação>/`. Variações de cor ficam em
`projetos/<projeto>/variacoes/<cômodo>/<nome>.json` (schema em `schema/variacao.schema.json`):

```json
{"schema_version": 1, "comodo": "quarto", "nome": "Escura",
 "cores": {"parede": "#7A8B94", "piso": "#5C3D24", "moveis": {"guarda_roupa": "#2F3B45"}}}
```

`INTERIORES_BLENDER` aponta para um Blender local; `INTERIORES_BLENDER_IMAGEM` troca a imagem.

Stack completa:

```bash
make up                           # sobe api, worker, blender, db, redis, minio, frontend
make render P=casa C=quarto V=todas
make down
```

## Medindo um cômodo

1. Faça um croqui da planta vista de cima e numere as paredes no sentido horário.
2. Meça cada parede **rente ao piso e rente ao teto**.
3. Meça as **duas diagonais**. Se forem diferentes, o cômodo não está no esquadro.
4. Anote o **pé-direito**.
5. Portas e janelas: largura, altura, distância até o canto e, nas janelas, o **peitoril**.
6. Tomadas e interruptores: altura do piso e distância até o canto.
7. Marque **pilares, vigas e paredes com cano ou fiação** embutidos.
8. Tire uma foto de frente de cada parede.

O que não for medido entra como `estimada`, e os desenhos saem como preliminares até completar.

## Roadmap

### Feito

- [x] Esqueleto do monorepo (uv, Docker, pre-commit, commitizen) — PRs #1 e #2
- [x] `core`: schema Projeto → Imóvel → Pavimento → Cômodo — #3
- [x] Checagens do quarto (passagem, cama, guarda-roupa, portas, tomadas) — #5
- [x] Planta do quarto e do pavimento em DXF/PDF com carimbo, aviso de obra e instalações — #4, #11
- [x] Cortes e elevações do quarto — #8
- [x] Móveis — catálogo: cama, guarda-roupa, armário, sofá, TV/rack, mesa, cadeira, cômoda,
      criado-mudo, escrivaninha, estante..., com medidas padrão editáveis, frente/lados de uso,
      símbolo na planta, 3D e checagens próprias (ex.: distância sofá–TV) — #6
- [x] Móveis — planejados: projetar por dentro (vãos, prateleiras, gavetas, portas, chapas), com
      desenho técnico cotado, lista de corte e de ferragens (`.xlsx`) — #7; 3D com portas,
      gavetas e nichos — #27
- [x] Render do quarto no Blender com variações de cor, fila de render e vistas escolhidas
      (porta, cama, cantos, de cima) — #9, #17, #20, #24
- [x] API + banco: PostgreSQL como fonte da verdade, histórico de cada mudança, desfazer/refazer
      e voltar para uma versão, exportação para `projetos/` — #12, #13, #14, #21
- [x] **Rascunho**: testar mudanças à vontade, desfazer passo a passo e só então salvar (cada
      mudança vira uma versão) ou descartar — #26
- [x] Frontend — planta 2D, formulário de medidas com a origem (medi / quero assim / chute),
      painel de problemas e "falta medir", coluna lateral com abas e largura ajustável — #15, #26
- [x] Frontend — criar casa do zero (editor de planta): paredes, cantos, portas, janelas,
      instalações e cômodos, com as checagens na hora — #18
- [x] Frontend — editor de móveis: catálogo, arrastar, girar, encostar na parede, medidas,
      **criar do zero** (sob medida) e **montar planejado por dentro** — #15, #27, #28
- [x] Frontend — **visor 3D ao vivo**, igual à planta (sem esperar render), com vistas prontas,
      corte das paredes e teto liga/desliga — #23, #29
- [x] Cores: variações por cômodo, cada parede, piso, teto, rodapé, cada móvel e **cada parte do
      móvel** (portas, gavetas, puxadores, travesseiros...), pintadas ao vivo no 3D; seletor de
      cor e várias coisas de uma vez — #16, #26
- [x] **Formas dos móveis**: cantos arredondados, redondo/oval e em L (mesas e móveis de corpo
      simples), na planta, no DXF, nas checagens e no 3D — #30
- [x] Planta geral do pavimento e 3D da casa (pavimento inteiro com o teto cortado) — #11, #25, #29
- [x] **Andares**: criar e remover andares pela tela, com o andar de baixo de referência ao
      desenhar o de cima
- [x] **Comparador e tinta**: variações lado a lado (`make compare` e na tela) e planilha de
      tinta (`make tinta` e na tela): látex de paredes e teto e esmalte de portas e rodapé, por
      cor, com litros e latas

### Próximos

- [ ] Cozinha (hidráulica, gás, triângulo de trabalho), com pia/cuba, torneira, fogão e
      geladeira; depois banheiro (vaso, box/chuveiro, ralo)
- [ ] Modelos prontos (pedido do usuário, 2026-11-18): biblioteca de modelos pré-feitos para
      escolher e posicionar, com símbolo na planta e 3D detalhado. **Tudo editável pela
      pessoa**: partir de um modelo pronto e mudar medidas, acabamento/cor, número de
      portas/folhas/gavetas, puxador, sentido de abertura etc., podendo **salvar a versão
      editada como modelo próprio**:
      - **móveis mais comuns** do mercado, com acabamento, puxadores, pés e portas visíveis;
      - **portas**: de giro (lisa, almofadada, com vidro), de correr (aparente e embutida),
        camarão, pivotante, de banheiro com veneziana; com batente, guarnição e maçaneta;
      - **janelas**: de correr (2 e 4 folhas), basculante, maxim-ar, de abrir, veneziana,
        com caixilho, vidro e peitoril padrão; tamanhos comerciais (ex.: 120 × 100, 150 × 120)
- [ ] Editor de móveis — o que falta: redimensionar puxando as bordas na planta, mover e girar
      direto no 3D, sofá e bancada planejada em L, lista de corte e desenho do planejado pela tela
- [ ] Render: fotos realistas do pavimento inteiro pela tela; variação de layout de móveis
- [ ] Referência por foto (pedido do usuário, 2026-11-19): subir uma foto (Pinterest, um
      quarto parecido) pela tela; o sistema tira a paleta dela e cria uma variação de cor
      parecida, para comparar com o render
- [ ] Perfis e login (pedido do usuário, 2026-11-18): cada pessoa com conta, seus projetos
      (vários por pessoa) e suas preferências (ex.: unidade cm/m/mm); projetos podem ser
      compartilhados. O banco já guarda vários projetos; falta o dono de cada um
- [ ] Deploy

## Contribuindo / commits

Os commits seguem [Conventional Commits](https://www.conventionalcommits.org/pt-br/), validados pelo [Commitizen](https://commitizen-tools.github.io/commitizen/):

```bash
cz commit     # commit guiado
cz bump       # nova versão + CHANGELOG
```

Exemplos:

```
feat(cad): gerar corte AA com cotas de pé-direito
fix(regras): considerar raio da porta na checagem de passagem
feat(medidas): registrar medidas de trena da parede da janela
```

As regras completas do projeto (modelo de medidas, checagens, camadas DXF, escopos de commit) estão no [`CLAUDE.md`](./CLAUDE.md).

## Aviso

Este projeto **aponta** restrições e problemas, mas não substitui arquiteto, engenheiro ou eletricista. Os limites das checagens são referências de ergonomia configuráveis, e não norma técnica.

## Licença

A definir.
