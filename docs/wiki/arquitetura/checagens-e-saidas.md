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
| Móveis sobrepostos (planta e altura; o vão sob o tampo de mesa/escrivaninha é livre para o que couber nele, ex.: gabinete) | — | aviso |
| TV perto de quem assiste | 1,5 × diagonal | aviso |
| Quarto: lateral da cama (2 lados no casal, 1 no solteiro) | 600 mm | aviso |
| Quarto: frente de guarda-roupa de porta de abrir | 900 mm ou folha + 100 | aviso |
| Cozinha: triângulo pia–fogão–geladeira (soma entre os meios das frentes) | 3600–6600 mm | aviso (falta um dos três: info) |
| Cozinha: pia sem ponto de água fria ou de esgoto por perto | 300 mm | erro |
| Cozinha: fogão a gás sem ponto de gás no cômodo ou sem ventilação (janela/porta para fora) | — | erro |
| Cozinha: fogão embaixo de janela | 300 mm | aviso |
| Cozinha: altura da bancada da pia | 900 ± 50 mm | aviso |
| Banheiro: área livre à frente do vaso e do lavatório | 600 mm | aviso |
| Banheiro: tomada perto do box | 600 mm | erro |
| Banheiro: box sem ralo dentro dele | — | erro |
| Banheiro: vaso sem esgoto; lavatório sem água fria ou esgoto | 300 mm | erro |
| Área de serviço: máquina de lavar e tanque sem água fria ou esgoto | 300 mm | erro |
| Área de serviço sem máquina ou sem tanque | — | info |
| Planejado: construção que não cabe | — | erro |
| Planejado: prateleira sem apoio · cabideiro baixo · móvel raso · gaveta estreita | 900 · 1000 · 550 · 300 mm | aviso |
| Estrutura: laje que se cruza · viga sem comprimento | — | erro |
| Estrutura: furo fora da laje · lajes sobrepostas | — | aviso |
| Escada atravessando parede | — | erro |
| Escada: espelho (`escada_espelho_min/max`) · piso (`escada_piso_min`) · 2 × espelho + piso (`escada_blondel_min/max`) · largura (`escada_largura_min`) | 160–190 · 250 · 600–650 · 800 mm | aviso |
| Escada: fora do pavimento · desnível diferente da altura até o andar de cima · lance que não cabe · caracol com menos de `escada_altura_livre` entre uma volta e a de cima | 2100 mm | aviso |

Os limites de escada ficam na seção `[geral]` do `regras.toml`.

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
