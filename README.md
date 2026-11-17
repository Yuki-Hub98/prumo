# PRUMO

## interiores

> Projeto de interiores a partir de medidas reais: plantas DXF/PDF, renders 3D no Blender e checagens de obra, tudo gerado por código.

![status](https://img.shields.io/badge/status-em%20desenvolvimento-orange)
![python](https://img.shields.io/badge/python-3.12-blue)
![commits](https://img.shields.io/badge/commits-conventional-brightgreen)

Você mede o cômodo com a trena, anota num croqui e o sistema faz o resto: modelo 3D com várias opções de cor e móvel para comparar, plantas e cortes cotados para levar ao marceneiro e uma lista de problemas antes de furar qualquer parede.

Nada é desenhado à mão. Tudo é gerado a partir de arquivos JSON de medidas: mudou uma medida, os desenhos e as imagens são refeitos.

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
| Comparações lado a lado | ImageMagick | `.png` |
| Cálculo de tinta e materiais | openpyxl | `.xlsx` |
| Relatório de problemas | regras do `core` | terminal / API |

## Como funciona

```
fotos + croqui com trena
        │
        ▼
projetos/<projeto>/projeto.json   ← fonte da verdade (medidas em mm + origem)
        │
        ▼
core: valida, monta a geometria e roda as checagens
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
├── projetos/        # medidas e variações (fonte da verdade)
├── packages/
│   ├── core/        # modelo, validação, regras, tipos de cômodo
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

Pré-requisitos: [uv](https://docs.astral.sh/uv/), Docker e Docker Compose. O Blender só é necessário fora do Docker.

```bash
git clone https://github.com/Yuki-Hub98/interiores.git
cd interiores
cp .env.example .env
make setup        # uv sync + pre-commit install
```

Sem Docker (core, CAD e CLI):

```bash
make validate P=casa              # valida medidas + checagens
make cad P=casa C=quarto          # planta e cortes do quarto
```

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

- [ ] Esqueleto do monorepo (uv, Docker, pre-commit, commitizen)
- [ ] `core`: schema Projeto → Imóvel → Pavimento → Cômodo
- [ ] Checagens do quarto (passagem, cama, guarda-roupa, portas, tomadas)
- [ ] Planta e cortes do quarto em DXF/PDF com carimbo e aviso de obra
- [ ] Render do quarto no Blender com variações de cor e móvel
- [ ] Comparador lado a lado e cálculo de tinta
- [ ] API + banco (histórico de medidas, variações, escolhas)
- [ ] Frontend: visor 3D, comparador, formulário de medidas, painel de problemas
- [ ] Cozinha (hidráulica, gás, triângulo de trabalho)
- [ ] Planta geral do pavimento e 3D da casa
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
