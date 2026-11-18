<!--
title: Passo a passo de um projeto
description: Do croqui ao render
published: true
date: 2026-11-18T00:00:00.000Z
tags: uso
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Passo a passo de um projeto

1. **Medir.** Croqui da planta vista de cima, paredes numeradas, medidas rente ao piso e ao
   teto, duas diagonais (esquadro), pé-direito, portas (largura, altura, lado da
   dobradiça), janelas (peitoril, largura, altura), tomadas e pontos de água com a altura.
2. **Registrar no JSON** (`projetos/<projeto>/projeto.json`): pavimento, paredes por eixo
   (coordenadas em mm), aberturas presas às paredes, instalações, cômodos pelas paredes.
   Medida que faltar entra como `estimada` com uma `obs` dizendo de onde veio.
3. **Validar:** `make validate P=<projeto>`. Corrija erros (cômodo não fecha, parede
   sobreposta, porta incoerente...).
4. **Planta:** `make cad P=<projeto> C=<cômodo>`. Imprima e confira com a trena; troque as
   estimadas por `trena`.
5. **Móveis:** `uv run interiores movel adicionar ...` (catálogo) e, se for planejado,
   `uv run interiores planejado criar ...` + `make planejado ...`.
6. **Checagens:** aparecem no terminal e desenhadas na planta (camada RESTRICAO).
7. **Cortes e elevações:** saem junto com `make cad ... C=<cômodo>`.
8. **Render:** `make render P=<projeto> C=<cômodo>`; cores em `variacoes/<cômodo>/*.json`.

Exemplo real: o projeto `casa` (quarto com banheiro, medidas aproximadas).
