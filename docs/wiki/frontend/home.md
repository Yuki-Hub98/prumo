<!--
title: Frontend
description: Planta 2D com edição de móveis, problemas e "falta medir"
published: true
date: 2026-11-18T00:00:00.000Z
tags: frontend
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Frontend

**React + Vite + TypeScript**, **Tailwind CSS v4**, **TanStack Query**; tipos gerados do
OpenAPI da API (`openapi-typescript` + `openapi-fetch`), então a tela nunca diverge da API.

## Rodar

```bash
make banco                # Postgres + migrações
make api                  # http://localhost:8010
cd frontend && npm install   # só na primeira vez
make frontend             # http://localhost:5173
```

Mudou alguma rota ou esquema da API? `make frontend-tipos` regera `openapi.json` e
`esquema.d.ts`.

## O que já faz

- **Projetos:** lista, cria (código, casa/apartamento, pé-direito) e abre (`#/p/<código>`).
- **Unidade:** mm, cm ou m (salva no banco, em `/preferencias`); a API é sempre mm.
- **Planta 2D (SVG):** paredes, vãos, giro das portas, janelas, cômodos com área,
  móveis (seta = frente; tracejado = elevado), instalações (T, S, L, AF, AQ, ES, R, G),
  marcas de problema e escala. A geometria vem pronta da API (`.../geometria`): a tela
  não recalcula nada.
- **Móveis:** clicar seleciona; **arrastar move** (de 1 em 1 cm); girar 90°; encostar numa
  parede; editar largura/profundidade/altura/elevação; remover; adicionar do catálogo no
  centro do cômodo.
- **Medidas:** ao editar, a tela **sempre pergunta a origem** ("Medi", "Quero assim",
  "Chute") e mostra um selo colorido em cada valor.
- **Problemas** (com "novo" nos que a última edição criou) e **falta medir** (enquanto
  houver chute, os desenhos saem PRELIMINAR).
- **Versão:** toda edição vai com a versão que a tela tem; se outra aba gravou antes, a
  tela recarrega e avisa.
- **Desfazer / refazer:** botões no topo, ou **Ctrl+Z** e **Ctrl+Shift+Z** (ou Ctrl+Y), fora
  de campos de texto. **Histórico** abre a lista de versões (o que mudou e quando) com
  "voltar para esta" (pede confirmação). Nada é apagado: voltar vira uma versão nova.

## Imagens 3D

Com um cômodo selecionado, o painel "Imagens 3D" pede **rascunho** ou **final** da variação
de cor ativa, mostra a estimativa antes, a barra de progresso enquanto roda ("imagem 1 de 2
· 42% · faltam ~1 min") e as miniaturas quando fica pronto. Precisa do worker (`make worker`).

## Visor 3D

No topo, **Planta | 3D** troca a área principal para o modelo 3D do cômodo (o `.glb` do
render pronto mais recente; troque o cômodo na lista). Arraste para girar, roda para zoom,
botão direito para mover. Vistas prontas: **De cima** (sem teto, como maquete),
**Perspectiva**, **Frente**, **Fundo**, **Esquerda** e **Direita** — nas de lado a parede do
lado da câmera é **cortada** para ver o cômodo por dentro. A caixa **teto** mostra o teto e a
luminária. O modelo só muda quando sai um render novo: se o projeto mudou depois, a tela
avisa para pedir um rascunho. As texturas (madeira, tecido) aparecem só nas imagens; no 3D
vão as cores lisas.

## Editar planta

No topo, **"Editar planta"** troca a tela para o editor (os móveis ficam apagados):

- **Desenhar paredes:** escolha a espessura (e a origem), clique canto a canto; o ponto gruda
  nos cantos existentes e alinha na horizontal/vertical. Botão direito termina a sequência.
- **Cantos:** arraste os círculos azuis; as paredes que se encontram no canto vão junto.
- **Clique para editar:** parede (espessura, dividir, + porta, + janela, + tomada/ponto,
  remover), porta/janela (medidas, para onde abre, dobradiça), tomada/ponto (altura, posição),
  cômodo (nome, tipo, pé-direito, remover).
- **Novo cômodo:** "escolher as paredes…", clique nas paredes em volta, dê nome e tipo.
- Toda medida nova pergunta a origem ("Medi", "Quero assim", "Chute"). As edições vão em fila,
  uma de cada vez, para desenhar rápido sem conflito de versão.
- Link direto: `#/p/<projeto>?modo=planta&sel=parede:p2`.

## Ainda não

- Comparador de variações, construção de planejados.
- Login e perfis (planejado).
