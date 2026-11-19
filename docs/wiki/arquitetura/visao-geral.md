<!--
title: Arquitetura
description: Como o sistema é organizado
published: true
date: 2026-11-18T00:00:00.000Z
tags: arquitetura
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Arquitetura

```
CLI / Claude Code ──► projetos/*.json ──┐
                                         ├──► core (modelo + validação + regras)
Frontend (React) ──► API (FastAPI) ─────┘          │
                                                    ├──► cad (ezdxf, matplotlib)
                                                    ├──► render (Blender headless)
                                                    └──► relatorios (openpyxl)
Infra: PostgreSQL (histórico) · Redis (fila) · MinIO (arquivos) · Wiki.js (docs)
```

Hoje existem `core`, `cad`, `render`, `relatorios` e `cli`. API, worker e frontend estão
planejados.

## Pacotes (`packages/`)

| Pacote | O que faz | Pode importar |
|---|---|---|
| `core` | modelo pydantic, validação, checagens, geometria (shapely), catálogo de móveis, cálculo de planejados, edição do JSON | pydantic, shapely |
| `cad` | planta, cortes, elevações, desenho do móvel planejado (DXF + PDF) | core, ezdxf, matplotlib |
| `render` | monta a `cena.json` e chama o Blender | **só core + stdlib** |
| `relatorios` | lista de corte (.xlsx) | core, openpyxl |
| `banco` | tabelas SQLAlchemy, migrações Alembic, importar/exportar `projetos/` | core, sqlalchemy, alembic, psycopg |
| `cli` | comando `interiores` (Typer) | todos |
| `services/api` | API FastAPI: rotas → *service* (pré-filtro e orquestração) → core | core, banco, fastapi |

## Princípios

1. **O banco é a fonte da verdade** (PostgreSQL): todo o modelo em tabelas pesquisáveis,
   todas as medidas com origem numa tabela só, histórico de cada mudança e snapshot de cada
   versão. `projetos/` é a exportação versionada; `interiores importar|exportar`
   sincronizam sem atropelar mudança dos dois lados. `core`, `cad` e `cli` continuam
   funcionando só com o JSON.
2. **`core` é Python puro**, testável sem Docker.
3. **Geração determinística e com cache.** Cada saída grava um `.json` com a chave (hash da
   entrada + versão do gerador); se nada mudou, não refaz.
4. **Scripts do Blender são finos.** O orquestrador entrega a geometria pronta em
   `cena.json`; o script (`bpy_cena.py`) só constrói e renderiza (o Python do Blender não
   tem pydantic).
5. **Hierarquia fixa:** Projeto → Imóvel → Pavimento → Cômodo. Geração por escopo
   (cômodo ou pavimento).
6. **Extensão por tipo de cômodo:** regras de um tipo ficam em `core/tipos/<tipo>.py`
   (achado pelo nome). Tipo novo = arquivo novo.

## Pastas

- `projetos/<projeto>/`: `projeto.json`, `comodos/<cômodo>.json` (móveis),
  `variacoes/<cômodo>/*.json` (cores), `regras.toml` (limites), versionados.
- `out/`: saídas geradas, nunca versionadas nem editadas à mão.
- `schema/`: JSON Schema do modelo e o catálogo (para o frontend).
- `docs/wiki/`: esta documentação.
- `docker/`: Dockerfiles (hoje: Blender).
