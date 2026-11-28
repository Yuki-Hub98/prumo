<!--
title: Modelo de dados
description: O que vai em projeto.json, comodos/ e variacoes/
published: true
date: 2026-11-18T00:00:00.000Z
tags: arquitetura dados
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Modelo de dados

Unidade interna: **milímetros inteiros**. Toda medida é um objeto:

```json
{"valor": 3150, "origem": "trena", "obs": "rodapé a rodapé", "data": "2026-11-17"}
```

## `projeto.json`

```
Projeto (schema_version, projeto, imovel)
└── pavimentos[]: id, cota_piso, pe_direito, rodape
    ├── paredes[]: id, inicio [x,y], fim [x,y], espessura, lado_a, lado_b, altura?
    ├── aberturas[]: porta (de, para, folha giro|correr, abre_para, dobradica)
    │                ou janela (peitoril); parede, distancia_inicio, largura, altura
    ├── estrutura[]: pilar (centro, largura, profundidade) | viga (inicio, fim, largura,
    │                altura) | laje (espessura, sistema, contorno?, furos[])
    ├── instalacoes[]: ponto (tomada, interruptor, ponto_luz, agua_fria, agua_quente,
    │                  esgoto, ralo, gas; posicao, altura, parede?, comodo?) ou trecho
    └── comodos[]: id, nome, tipo, paredes[], pe_direito?
```

- Coordenadas globais por pavimento, y para cima.
- **Parede é uma só entre dois cômodos.** `lado_a` é o cômodo à esquerda de quem anda de
  `inicio` para `fim`.
- O polígono do cômodo é derivado das paredes (não é digitado).
- `comodo` no ponto de instalação diz de que lado de uma parede interna ele fica.
- **Laje** é a de cobertura do pavimento (teto dele, piso do de cima), do pé-direito para
  cima. Sem `contorno`, cobre o pavimento inteiro por fora das paredes; `furos` são contornos
  em mm.

## `comodos/<cômodo>.json` (móveis)

`moveis[]`: `id`, `tipo` (do catálogo), `modelo?`, `nome?`, `centro [x,y]`,
`rotacao` (0/90/180/270), `largura`, `profundidade`, `altura`, `elevacao?` (suspenso),
`portas?` (abrir|correr), `largura_porta?`, `polegadas?` (TV), `construcao?` (planejado).

**Orientação:** em rotação 0, as costas do móvel ficam para baixo na planta (−y) e a frente
para cima (+y); a rotação é anti-horária.

**Planejado (`construcao`):** `chapa` e `fundo` (material + espessura), `rodape?`,
`vaos[]` da esquerda para a direita, cada um com `largura?`, `porta` e `espacos[]` de
baixo para cima (`gaveta` | `nicho` | `cabideiro`, `altura?`). O que não tiver medida
divide o espaço que sobra; prateleiras entram sozinhas entre os espaços.

## `variacoes/<cômodo>/<nome>.json`

Cores (`#RRGGBB`) de parede, piso, teto, rodapé e de móveis por id ou tipo. Nunca alteram
o projeto base.

## `regras.toml`

Limites das checagens em `[geral]` e `[<tipo de cômodo>]`. Ver
[Checagens e saídas](/arquitetura/checagens-e-saidas).

Os schemas oficiais ficam em `schema/` (`make schema`).
