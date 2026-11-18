<!--
title: Prumo — documentação
description: Projeto de interiores a partir de medidas reais
published: true
date: 2026-11-18T00:00:00.000Z
tags: inicio
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Prumo

Sistema para projetar e reformar imóveis inteiros (casa ou apartamento) a partir de
**medidas reais**. Tudo é gerado por código a partir de arquivos JSON: plantas, cortes e
elevações em escala (DXF/PDF), checagens de uso, móveis (do catálogo e planejados, com
lista de corte) e renders 3D.

## Por onde começar

- [Instalação](/uso/instalacao): preparar o ambiente.
- [Passo a passo de um projeto](/uso/passo-a-passo): do croqui ao render.
- [Comandos](/uso/comandos): referência de tudo que dá para rodar.
- [Arquitetura](/arquitetura/visao-geral): como o sistema é organizado.
- [Modelo de dados](/arquitetura/modelo-de-dados): o que vai no JSON.
- [Checagens e saídas](/arquitetura/checagens-e-saidas): regras, avisos e arquivos gerados.
- [Desenvolvimento](/desenvolvimento/contribuindo): branches, commits, testes.
- [Frontend](/frontend/home): o que vem por aí.

## Regras que valem sempre

- **O JSON é a fonte da verdade** das medidas (`projetos/<projeto>/`).
- Toda medida tem **origem**: `trena` (medido), `estimada` (chute) ou `projeto` (decidido).
- Havendo medida `estimada`, desenhos e renders saem com **PRELIMINAR — NÃO USAR PARA OBRA**.
- O sistema **aponta** restrições; não substitui arquiteto, engenheiro ou eletricista.

## Como esta wiki funciona

As páginas são arquivos Markdown versionados no repositório, em `docs/wiki/`. A Wiki.js
(serviço `wiki` do docker-compose) lê essa pasta.

Primeira vez:

1. `make wiki` (ou `docker compose up -d wiki`) e abra <http://localhost:3000>.
2. Crie a conta de administrador no assistente de instalação.
3. **Administração → Armazenamento → Sistema de arquivos local**: ative, caminho
   `/wiki/docs`, salve.
4. Na mesma tela, em **Ações**, clique em **Importar tudo**.

Para atualizar depois de mudar os arquivos no repositório: **Importar tudo** de novo.
Páginas editadas pela própria wiki são gravadas de volta em `docs/wiki/` (e podem ser
commitadas).
