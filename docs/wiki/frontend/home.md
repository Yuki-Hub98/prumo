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
- **Rascunho:** toda edição da tela (cores, móveis, planta) entra num rascunho: dá para
  testar à vontade. No topo aparece "N mudanças não salvas" com **Salvar** (ou **Ctrl+S**:
  cada mudança vira uma versão e o JSON em `projetos/` é atualizado) e **Descartar** (volta
  para o que estava salvo; pede confirmação). O rascunho fica no banco: recarregar a página
  não perde nada.
- **Desfazer / refazer:** botões no topo, ou **Ctrl+Z** e **Ctrl+Shift+Z** (ou Ctrl+Y), fora
  de campos de texto. No rascunho voltam **um passo de cada vez** (a cor anterior, a posição
  anterior; arrastar e soltar conta como um passo). Depois de salvo, voltam as versões.
  **Histórico** abre a lista de versões (as não salvas aparecem marcadas) com "voltar para
  esta" (pede confirmação; só sem rascunho). Nada salvo é apagado: voltar vira uma versão nova.
- **Clique sem arrastar:** o móvel só começa a andar depois de 4 px; clicar para selecionar
  não move nada.

## Coluna lateral

Em "Móveis e cores" a coluna da direita tem **abas**: **Móvel** (o móvel selecionado e
adicionar do catálogo; clicar num móvel na planta abre esta aba), **Cores**, **Imagens** e
**Problemas** (com a contagem, e o que falta medir). A **largura é ajustável**: arraste a faixa
cinza da borda esquerda (ou use ← → com ela em foco; clique duplo volta ao padrão); fica
lembrada neste navegador. Em "Editar planta" a coluna mostra o editor, sem abas.

O quadradinho de cor abre um **seletor dentro da página** (degradê, matiz, R/G/B e as cores
já usadas no cômodo), à esquerda do botão para não sair da tela.

Cada cor mudada entra no **rascunho** (~0,6 s depois de parar de mexer): **Desfazer** / Ctrl+Z
volta a cor anterior, passo a passo; **Salvar** no topo grava. **Marque várias linhas**
(caixinhas) e uma cor só pinta todas (barra "N marcados"; mudar uma linha marcada também
pinta as outras). Em cada móvel, **▸ detalhes** abre as partes com cor própria (portas,
gavetas, puxadores, travesseiros, roupa de cama, colchão, pés...); sem cor, a parte fica com a
do móvel. No 3D as partes pintam ao vivo em modelos gerados a partir desta versão (peça um
rascunho em "Imagens" se o modelo for antigo). Clicar no **nome de um móvel** no painel, ou **no móvel no 3D**, seleciona o
móvel: em Cores a linha dele fica marcada; nas outras abas abre Móvel.

## Imagens 3D

Com um cômodo selecionado, o painel "Imagens 3D" mostra as **vistas** que fazem sentido no
cômodo (perspectiva, da porta, de frente para a cama, cada canto livre, de cima): clique para
ligar ou desligar; cada vista é uma imagem, e a escolha fica lembrada por cômodo neste
navegador. Depois pede **rascunho** ou **final** da variação de cor ativa, mostra a estimativa
(pelo número de vistas) antes, a barra de progresso enquanto roda ("imagem 1 de 2
· 42% · faltam ~1 min") e as miniaturas, com o nome de cada vista, quando fica pronto. Precisa do worker (`make worker`).

## Visor 3D

No topo, **Planta | 3D** troca a área principal para o modelo 3D do cômodo (o `.glb` do
render pronto mais recente; troque o cômodo na lista). Arraste para girar, roda para zoom,
botão direito para mover. Vistas prontas: **De cima** (sem teto, como maquete),
**Perspectiva**, **Frente**, **Fundo**, **Esquerda** e **Direita** — nas de lado a parede do
lado da câmera é **cortada** para ver o cômodo por dentro. A caixa **teto** mostra o teto e a
luminária. O modelo só muda quando sai um render novo: se o projeto mudou depois, a tela
avisa para pedir um rascunho. As texturas (madeira, tecido) aparecem só nas imagens; no 3D
vão as cores lisas.

Na lista, **Pavimento inteiro** mostra a casa toda (todos os cômodos, sem teto). O botão
**gerar modelo da casa** (ou **atualizar**) põe um rascunho na fila e o visor abre quando fica
pronto; as vistas de lado cortam a parede externa do lado da câmera.

### Pintar no 3D

O cômodo da lista fica selecionado, e o painel **Cores** abre ao lado. Na "base", o botão
**pintar este cômodo** cria a variação "Minhas cores" (o projeto base não muda). Cada cor
mudada (paredes em geral ou uma por uma, piso, teto, rodapé, cada móvel) aparece **na hora**
no modelo, sem render, e entra no rascunho; as imagens do Blender com as cores novas saem no
próximo render (rascunho ou final). O móvel selecionado ganha um contorno quase transparente
em volta (a cor dele continua a escolhida). No **Pavimento inteiro** pintam piso, teto, rodapé e móveis
do cômodo da lista; as paredes não, porque cada parede é uma peça só entre dois cômodos.

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
