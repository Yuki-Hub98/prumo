<!--
title: Desenvolvimento
description: Branches, commits, testes e relatórios
published: true
date: 2026-11-18T00:00:00.000Z
tags: desenvolvimento
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Desenvolvimento

## Fluxo

- `main` estável; trabalho em `feat/<assunto>`, `fix/<assunto>`, `chore/<assunto>`.
- Commits em **Conventional Commits**, validados pelo Commitizen (`cz commit`):
  `feat(cad): gerar corte AA com cotas de pé-direito`.
- Escopos: `core`, `regras`, `tipos`, `cad`, `render`, `relatorios`, `cli`, `api`, `worker`,
  `frontend`, `db`, `docker`, `medidas`, `deps`, `ci`.
- Mudança de medida (`medidas`) vai em commit separado de código.
- Cada commit deve passar nos testes sozinho.
- Versão e CHANGELOG com `cz bump`.

## Qualidade

```bash
make check     # ruff + mypy (core, cad) + pytest com cobertura (meta ≥ 85% no core)
```

- Testes usam **cópias congeladas** do projeto de exemplo (`packages/*/tests/dados/`):
  editar `projetos/` não quebra testes.
- Desenhos: snapshot por entidades do DXF (`PRUMO_ATUALIZAR_SNAPSHOTS=1` regrava; suba o
  `planta vN` quando o desenho mudar de propósito).
- Render: testes com um Blender falso; o real roda com `PRUMO_TESTAR_BLENDER=1`.

## Contexto local (fora do git)

- `.relatorios/<data>-<feature>/RELATORIO.md`: objetivo, decisões, o que foi feito,
  medidas alteradas, problemas, commits, pendências.
- `.mrs/<data>-<tipo>-<slug>.md`: descrição pronta para o PR.

Ambos ficam excluídos em `.git/info/exclude` (`make setup`).
