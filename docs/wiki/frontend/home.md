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

No topo da coluna da direita fica o título (**Painel de edição**, ou **Editar planta** no
editor) e o botão **☰**, que fecha a coluna (sobra uma faixa com o ☰ para reabrir; fica
lembrado no navegador). Em "Móveis e cores" a coluna tem **abas**: **Móvel** (o móvel selecionado e
adicionar do catálogo; clicar num móvel na planta abre esta aba), **Cores**, **Imagens** e
**Problemas** (com a contagem, e o que falta medir). A **largura é ajustável**: arraste a faixa
cinza da borda esquerda (ou use ← → com ela em foco; clique duplo volta ao padrão); fica
lembrada neste navegador. Em "Editar planta" a coluna mostra o editor, sem abas.

O quadradinho de cor abre um **seletor dentro da página** (degradê, matiz, R/G/B e as cores
já usadas no cômodo), à esquerda do botão para não sair da tela.

Cada cor mudada entra no **rascunho** (~0,6 s depois de parar de mexer): **Desfazer** / Ctrl+Z
volta a cor anterior, passo a passo; **Salvar** no topo grava. **Marque várias linhas**
(caixinhas) e uma cor só pinta todas (barra "N marcados"; mudar uma linha marcada também
pinta as outras). Em cada móvel, **▸ detalhes** abre as partes com cor própria (abre sozinho ao selecionar o
móvel e fecha quando outro é selecionado; dá para abrir os de outros na mão): portas,
gavetas, puxadores, travesseiros, roupa de cama, colchão, pés...); sem cor, a parte fica com a
do móvel. No 3D as partes pintam ao vivo em modelos gerados a partir desta versão (peça um
rascunho em "Imagens" se o modelo for antigo). Clicar no **nome de um móvel** no painel, ou **no móvel no 3D**, seleciona o
móvel: em Cores a linha dele fica marcada; nas outras abas abre Móvel.

## Móvel do zero e planejado

Na aba **Móvel**, em "Adicionar móvel", **Criar do zero** pede nome, largura, profundidade e
altura (e de onde vêm as medidas: "Medi", "Quero assim" ou "Chute") e põe uma caixa com essas
medidas no centro do cômodo (tipo `sob_medida`), já selecionada.

Guarda-roupa, armário, cômoda, criado-mudo, estante, rack, sapateira, penteadeira e o móvel
sob medida podem ser **montados por dentro**: o botão começa com uma sugestão para o tipo e
abre o editor:

- **vista de frente** em escala (gavetas em amarelo, nichos, cabideiros; **ver portas** mostra
  as folhas tracejadas por cima);
- **portas**: sem portas, de abrir (uma ou duas folhas por vão; **com porta** liga/desliga em
  cada vão) ou de correr (no móvel todo);
- **vãos** da esquerda para a direita (de quem olha de frente): largura (vazio = divide o que
  sobra), tirar, **+ vão**;
- **espaços** de cada vão, de baixo para cima: gaveta, nicho/prateleira ou cabideiro, altura
  (vazio = automático), ↑↓ para trocar de lugar, ✕ para tirar, **+ gaveta / + nicho /
  + cabideiro** põe em cima;
- resumo: peças de chapa, chapas necessárias e ferragens; **Desmontar** volta a ser uma caixa.

O que não cabe (vãos mais largos que o móvel, gavetas que não entram) é recusado com a
mensagem do cálculo. Tudo entra no rascunho (Desfazer volta cada passo). No 3D aparecem as
portas, as frentes de gaveta com puxador e, nos vãos sem porta, os nichos e as prateleiras.
Pia, cuba, torneira, fogão e geladeira chegam com a cozinha e o banheiro.

### Formas

Mesa, escrivaninha, banco/puff, berço e móvel sob medida têm **forma** no painel do móvel:
**retangular**, **cantos arredondados** (raio; sem raio, 10 cm), **redondo / oval** (círculo
quando largura = profundidade, oval quando diferentes) e **em L** (largura do braço — sem
medida, 40 % do lado menor — e o lado do braço que vem para a frente, olhando de frente). Largura
e profundidade continuam sendo a caixa em volta. A forma vale na planta (e no DXF), nas
checagens (passagem, colisão) e no 3D: a mesa ganha tampo na forma e pés por dentro dela.
O **sofá** pode ser retangular ou **em L** (sofá de canto; no catálogo há o modelo "De canto em
L", 260 × 160): o braço do L é o fundo do assento (sem medida, 90 cm), com encosto nas costas e
na lateral de fora do braço, braços nas duas pontas e almofadas nos dois trechos. O painel só
mostra as formas que o móvel aceita. Cama, poltrona, guarda-roupa e móveis planejados ficam
retangulares.

## Tinta e comparador

No fim da aba **Cores**, **Tinta do pavimento** mostra o que comprar com a variação escolhida em
cada cômodo: látex de paredes e teto e esmalte de portas e rodapé, por cor (amostra, m², litros
e latas). Parede de destaque conta à parte. **Baixar planilha (.xlsx)** traz a mesma planilha do
`make tinta`. Na aba **Imagens**, **comparar variações lado a lado** abre em tela cheia a imagem
pronta mais recente de cada variação, na vista escolhida (marque quais comparar; Esc fecha).

## Imagens 3D

Com um cômodo selecionado, o painel "Imagens 3D" mostra as **vistas** que fazem sentido no
cômodo (perspectiva, da porta, de frente para a cama, cada canto livre, de cima): clique para
ligar ou desligar; cada vista é uma imagem, e a escolha fica lembrada por cômodo neste
navegador. Depois pede **rascunho** ou **final** da variação de cor ativa, mostra a estimativa
(pelo número de vistas) antes, a barra de progresso enquanto roda ("imagem 1 de 2
· 42% · faltam ~1 min") e as miniaturas, com o nome de cada vista, quando fica pronto. Precisa do worker (`make worker`).

## Visor 3D

No topo, **Planta | 3D** troca a área principal para o 3D do cômodo (troque na lista). O 3D é
**ao vivo**: é montado na hora a partir da mesma cena que o core calcula para o Blender
(`GET .../cena`), a cada versão do projeto, rascunho incluído. Móvel novo, movido, girado,
medida, parede, porta ou planejado aparecem no 3D e na planta juntos, sem pedir render. Arraste
para girar, roda para zoom, botão direito para mover; editar não tira a câmera do lugar.
Vistas prontas: **De cima** (sem teto, como maquete), **Perspectiva**, **Frente**, **Fundo**,
**Esquerda** e **Direita** — nas de lado a parede do lado da câmera é **cortada** para ver o
cômodo por dentro. A caixa **teto** mostra o teto e a luminária. No 3D vão as cores lisas; as
fotos realistas (texturas, luz) são do Blender, na aba **Imagens**.

Na lista, **Pavimento inteiro** mostra a casa toda (todos os cômodos, sem teto), também ao vivo;
as vistas de lado cortam a parede externa do lado da câmera.

### Pintar no 3D

O cômodo da lista fica selecionado, e o painel **Cores** abre ao lado. Na "base", o botão
**Pintar este cômodo** cria a variação "Minhas cores" (o projeto base não muda). Cada cor
mudada (paredes em geral ou uma por uma, piso, teto, rodapé, cada móvel) aparece **na hora**
no modelo, sem render, e entra no rascunho; as imagens do Blender com as cores novas saem no
próximo render (rascunho ou final). O móvel selecionado ganha um contorno quase transparente
em volta (a cor dele continua a escolhida). No **Pavimento inteiro** pintam piso, teto, rodapé e móveis
do cômodo da lista; as paredes não, porque cada parede é uma peça só entre dois cômodos.

## Tema claro e escuro

O botão de sol/lua no topo (e na lista de projetos) troca entre claro e escuro. A escolha fica
neste navegador; sem escolha, segue o sistema. As cores vêm dos tokens da identidade visual
(`index.css`): cor sempre quer dizer alguma coisa — verde/azul/laranja é a origem da medida
(Medi / Quero assim / Chute, este também tracejado), vermelho/âmbar é problema e amarelo é ação
principal ou o que está selecionado.

## Redimensionar pelas bordas

Com um móvel selecionado na planta (modo **Móveis e cores**), aparecem quatro alças amarelas no
meio dos lados. Puxe uma: o contorno fantasma mostra o tamanho novo e a medida ao vivo; ao
soltar, a largura (lados) ou a profundidade (frente/costas) muda com o **lado oposto parado**.
De 1 em 1 cm, mínimo 10 cm. A medida arrastada entra como **"Quero assim"** (decisão do
usuário: arrastar é decidir) — troque no painel se foi medida. Desfazer volta.

## Mover e girar no 3D

No **3D** ao vivo, com um móvel selecionado (clique nele): **arraste o próprio móvel** e ele
desliza pelo piso, de 1 em 1 cm, com o contorno amarelo junto; ao soltar, a posição é gravada
(como arrastar na planta). **Girar 90°** (no topo do 3D) gira o selecionado. Arrastar o fundo
continua girando a câmera; a câmera fica parada enquanto o móvel é arrastado. Desfazer volta.

## Acabamento, puxador e pés

No painel do móvel (aba **Móvel**): **Acabamento** (madeira clara, madeira escura, MDF
amadeirado, branco fosco, laca com brilho, preto fosco), **Puxador** (barra, botão, perfil de
alumínio, cava) e **Pés** (quadrado, palito, metálico fino, sem pé com rodapé recuado). Só
aparecem as escolhas que o tipo tem (cama não tem puxador; guarda-roupa não tem pés). É só
visual: medidas e checagens não mudam. A cor da variação continua valendo por cima do
acabamento; o veio da madeira aparece nas fotos (render), no 3D ao vivo só a cor.

## Meus modelos

Com um móvel selecionado (aba **Móvel**), **Salvar como modelo** guarda ele como está agora —
medidas, forma (arredondado, redondo, em L), portas e a montagem por dentro do planejado — com
um nome. Ele aparece em **Adicionar móvel → Meus modelos**, em qualquer cômodo e em qualquer
projeto, e sai igual ao original: cada medida vem com a origem que tinha (um chute continua
chute e entra em "Falta medir"). **Apagar modelo** tira da lista sem mexer nos móveis já
colocados. Os modelos ficam no banco (por enquanto valem para todos; com login, cada pessoa
terá os seus).

## Andares

No topo, a lista mostra o andar aberto; **+ Andar** cria um andar novo (sobrado, mezanino):
nome, pé-direito e cota do piso, com a origem das medidas. A cota vem sugerida em cima do
andar mais alto (piso + pé-direito + laje de 15 cm, como chute se não mudar) e o pé-direito
copiado do andar aberto. O andar novo abre no **Editar planta**: as paredes do andar de baixo
aparecem **apagadas ao fundo** e os cantos delas atraem o ponto ao desenhar, para o de cima
sair alinhado. **Remover este andar** (no editor, com confirmação) leva junto paredes, cômodos e
móveis; o único andar não sai. Tudo entra no rascunho. Os andares ainda não aparecem
empilhados no 3D (escadas e lajes ficam para depois).

## Editar planta

No topo, **"Editar planta"** troca a tela para o editor (os móveis ficam apagados):

- **Desenhar paredes:** escolha a espessura (e a origem), clique canto a canto; o ponto gruda
  nos cantos existentes e alinha na horizontal/vertical. Botão direito termina a sequência.
- **Cantos:** arraste os quadradinhos dos cantos; as paredes que se encontram no canto vão junto.
- **Clique para editar:** parede (espessura, dividir, + Porta, + Janela, + Tomada/ponto,
  remover), porta/janela (medidas, para onde abre, dobradiça, tipo), tomada/ponto (altura,
  posição), cômodo (nome, tipo, pé-direito, remover).
- **Portas e janelas prontas:** em **+ Porta** / **+ Janela**, "Modelo pronto" traz os tamanhos
  comerciais (porta de 60 a 90 cm, de correr, camarão; janela de correr 100 × 100 a 200 × 120,
  basculante e maxim-ar de banheiro, de abrir, fixa) e preenche as medidas — a origem continua
  sendo perguntada. Porta: folha (giro, correr, camarão) e estilo (lisa, almofadada, com vidro,
  veneziana). Janela: abertura (correr, basculante, maxim-ar, de abrir, fixa) e número de
  folhas. Tudo muda depois no painel da porta/janela e aparece na planta, nas elevações e no 3D.
  Janela sem tipo informado (projetos antigos) continua desenhada como antes.
- **Novo cômodo:** "Escolher as paredes…", clique nas paredes em volta, dê nome e tipo.
- Toda medida nova pergunta a origem ("Medi", "Quero assim", "Chute"). As edições vão em fila,
  uma de cada vez, para desenhar rápido sem conflito de versão.
- Link direto: `#/p/<projeto>?modo=planta&sel=parede:p2`.

## Ainda não

- Comparador de variações, construção de planejados.
- Login e perfis (planejado).
