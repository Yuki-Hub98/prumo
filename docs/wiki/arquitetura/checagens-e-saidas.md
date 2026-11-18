<!--
title: Checagens e saídas
description: Regras de uso, avisos e arquivos gerados
published: true
date: 2026-11-18T00:00:00.000Z
tags: arquitetura checagens
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Checagens e saídas

## Checagens

Severidades: **erro** (bloqueia "pronto para marceneiro"), **aviso**, **info**. Os limites
são padrões configuráveis em `regras.toml`, não norma técnica.

| Checagem | Padrão | Severidade |
|---|---|---|
| Estrutura: ids, cômodo fechado, paredes sobrepostas, lados, aberturas | — | erro |
| Passagem livre das portas até cada porta e lado de uso dos móveis | 700 mm | aviso |
| Porta batendo em móvel ao abrir | — | erro |
| Tomada/interruptor atrás de móvel (na faixa de altura dele) | — | aviso |
| Móvel entrando na parede | — | erro |
| Móveis sobrepostos (planta e altura) | — | aviso |
| TV perto de quem assiste | 1,5 × diagonal | aviso |
| Quarto: lateral da cama (2 lados no casal, 1 no solteiro) | 600 mm | aviso |
| Quarto: frente de guarda-roupa de porta de abrir | 900 mm ou folha + 100 | aviso |
| Planejado: construção que não cabe | — | erro |
| Planejado: prateleira sem apoio · cabideiro baixo · móvel raso · gaveta estreita | 900 · 1000 · 550 · 300 mm | aviso |

## Saídas

Sempre em `out/<projeto>/<pavimento>/<cômodo>/<variação>/` (cômodo) ou
`out/<projeto>/<pavimento>/_geral/` (pavimento).

| Arquivo | O quê |
|---|---|
| `planta.dxf/.pdf` | planta em escala (1:20/1:25/1:50), cotas, móveis, instalações, checagens |
| `corte-aa`, `corte-bb`, `elevacao-<parede>` | cortes e elevações (DXF/PDF) |
| `planejado-<móvel>.dxf/.pdf` | desenho técnico do móvel planejado |
| `planejado-<móvel>-corte.xlsx` | peças, ferragens, chapas |
| `render-perspectiva.png`, `render-superior.png`, `<cômodo>.glb` | render 3D e modelo |

**Carimbo** em todo desenho: projeto, cômodo, escala, data, hash do JSON e a lista de
medidas estimadas usadas.

**Aviso de obra:** com medida estimada, o DXF tem a camada `AVISO`, o PDF uma marca d'água
diagonal e o PNG uma faixa no rodapé.

**Camadas DXF:** `PAREDE`, `ABERTURA`, `MOVEL`, `ELETRICA`, `HIDRAULICA`, `COTA`, `TEXTO`,
`RESTRICAO`, `AVISO`. 1 unidade = 1 mm.
