<!--
title: Frontend
description: Planejado: editor de planta, móveis e visor 3D
published: true
date: 2026-11-18T00:00:00.000Z
tags: frontend
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Frontend (planejado)

Esta seção vai receber o passo a passo do frontend quando ele existir.

Stack prevista: **React + Vite + TypeScript**, **react-three-fiber** (visor 3D do `.glb`),
**TanStack Query**, **Tailwind**, tipos gerados do OpenAPI da API (FastAPI).

## O que está previsto

- **Criar casa do zero (editor de planta):** desenhar paredes com as medidas, portas,
  janelas, cômodos e instalações, com as checagens na hora.
- **Editor de móveis:** escolher do catálogo (`schema/catalogo.json`), arrastar, girar,
  "grudar na parede", redimensionar, montar planejados.
- **Visor 3D:** o `.glb` gerado pelo render.
- **Comparador e variações:** cores lado a lado.
- **Painel de problemas:** as checagens por severidade.

## O que já está pronto para ele

- JSON Schema do modelo e da variação em `schema/`, e o catálogo de móveis em
  `schema/catalogo.json`.
- Edição de móveis no core (`core/editar.py`): adicionar, mover, prender na parede,
  remover e definir a construção do planejado, que a API vai expor.
- Saídas com cache por hash, prontas para virar jobs do worker.
