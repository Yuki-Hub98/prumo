<!--
title: Banco e API
description: PostgreSQL como fonte da verdade e a API HTTP de edição
published: true
date: 2026-11-18T00:00:00.000Z
tags: uso api banco
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Banco e API

O **PostgreSQL é a fonte da verdade**. A pasta `projetos/` é a exportação dele, versionada
no git; a API reexporta a cada edição.

```bash
make banco              # sobe o Postgres (docker compose) e aplica as migrações
make importar P=casa    # traz projetos/casa para o banco
make api                # http://localhost:8010/docs (documentação interativa)
```

## Sincronização com `projetos/`

| Situação | O que fazer |
|---|---|
| Editou o JSON à mão, pela CLI ou pelo Claude | `make importar P=<projeto>` |
| Editou pela API | nada: a API já exporta |
| Mudou nos dois lados | importar/exportar recusam; `F=1` escolhe um lado |

## Regras da API

- **Medidas em mm inteiros, sempre com origem** (`trena`, `projeto`, `estimada`); a tela
  pergunta "medi / quero assim / chute" e converte a unidade escolhida.
- **Toda edição leva `?versao=`**: a versão que a tela estava vendo. Se alguém gravou
  antes, volta **409** com `versao_atual` — recarregue e refaça.
- **Edição que quebraria referência** (parede inexistente, id repetido, lado ocupado...)
  volta **422** e nada é gravado. Problemas de desenho (cômodo ainda aberto) não bloqueiam:
  voltam em `novos` / `problemas` na resposta.

## Rotas

| Método | Caminho | Para quê |
|---|---|---|
| GET | `/projetos` | listar projetos |
| POST | `/projetos` | criar projeto vazio (para desenhar do zero) |
| GET | `/projetos/{p}` | projeto inteiro + versão |
| GET | `/projetos/{p}/problemas` | erros, avisos, infos |
| GET | `/projetos/{p}/estimadas` | lista "falta medir" |
| GET | `/projetos/{p}/historico?desde=` | mudanças (antes → depois) |
| GET | `/projetos/{p}/versoes/{v}` | projeto numa versão antiga |
| PATCH | `/projetos/{p}/pavimentos/{a}` | nome, pé-direito, rodapé |
| POST/PATCH/DELETE | `.../paredes`, `.../paredes/{id}` | paredes (`/dividir`, `?cascata=`) |
| POST | `.../vertices/mover` | arrastar um canto |
| POST/PATCH/DELETE | `.../aberturas`, `.../aberturas/{id}` | portas e janelas |
| POST/PATCH/DELETE | `.../comodos`, `.../comodos/{id}` | cômodos |
| POST/PATCH/DELETE | `.../instalacoes`, `.../instalacoes/{id}` | tomadas, água, esgoto... |

O esquema completo (para gerar os tipos do frontend) está em `/openapi.json`.
