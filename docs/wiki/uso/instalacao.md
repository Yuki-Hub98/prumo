<!--
title: Instalação
description: Preparar o ambiente
published: true
date: 2026-11-18T00:00:00.000Z
tags: uso
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Instalação

Pré-requisitos: [uv](https://docs.astral.sh/uv/), Docker e Docker Compose. Python 3.12 é
instalado pelo uv.

```bash
git clone https://github.com/Yuki-Hub98/interiores.git
cd interiores
cp .env.example .env
make setup             # dependências, pre-commit, exclui .relatorios/ e .mrs/ do git
make blender-imagem    # Blender 4.5 LTS no Docker (~2 GB), só para o render 3D
make wiki              # esta documentação em http://localhost:3000
```

Sem Docker funcionam: validação, desenhos (CAD), móveis, planejados e planilhas. O Docker
é necessário para o render (a menos que o Blender esteja instalado: defina
`INTERIORES_BLENDER=/caminho/do/blender`) e para a infraestrutura (`make up`: Postgres,
Redis, MinIO e a wiki).

## Variáveis de ambiente (`.env`)

| Variável | Para quê |
|---|---|
| `POSTGRES_*`, `REDIS_PORT`, `MINIO_*` | infraestrutura da futura API |
| `WIKI_PORT` | porta da wiki (padrão 3000) |
| `INTERIORES_BLENDER` | executável do Blender local (opcional) |
| `INTERIORES_BLENDER_IMAGEM` | imagem Docker do Blender (padrão `interiores-blender:4.5.16`) |
