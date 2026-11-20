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
| GET | `/projetos/{p}/versoes` | lista de versões + para onde o desfazer/refazer levariam |
| GET | `/projetos/{p}/versoes/{v}` | projeto numa versão antiga |
| POST | `/projetos/{p}/desfazer` | volta ao estado de antes da última edição (no rascunho: um passo) |
| POST | `/projetos/{p}/refazer` | refaz o último desfazer (só logo depois de desfazer) |
| POST | `/projetos/{p}/rascunho/salvar` | salva o rascunho: cada passo vira versão; reexporta `projetos/<p>` |
| POST | `/projetos/{p}/rascunho/descartar` | volta para a versão salva e apaga os passos |
| POST | `/projetos/{p}/versoes/{v}/restaurar` | volta para o conteúdo da versão `v` |
| PATCH | `/projetos/{p}/imovel` | tipo (casa/apartamento) e apelido |
| POST | `/projetos/{p}/renomear` | troca o código (a pasta em `projetos/` vai junto) |
| DELETE | `/projetos/{p}?confirmar={p}` | apaga do banco; a pasta vai para `projetos/_apagados/` |
| POST | `/projetos/{p}/pavimentos` | novo pavimento (ex.: superior) |
| DELETE | `/projetos/{p}/pavimentos/{a}` | remove; com conteúdo, só com `?cascata=true` |
| PATCH | `/projetos/{p}/pavimentos/{a}` | nome, pé-direito, rodapé |
| POST/PATCH/DELETE | `.../paredes`, `.../paredes/{id}` | paredes (`/dividir`, `?cascata=`) |
| POST | `.../vertices/mover` | arrastar um canto |
| POST/PATCH/DELETE | `.../aberturas`, `.../aberturas/{id}` | portas e janelas |
| POST/PATCH/DELETE | `.../comodos`, `.../comodos/{id}` | cômodos |
| POST/PATCH/DELETE | `.../instalacoes`, `.../instalacoes/{id}` | tomadas, água, esgoto... |
| GET | `/catalogo` | tipos e modelos de móvel (medidas padrão, lados de uso) |
| POST | `/projetos/{p}/comodos/{c}/moveis` | pôr móvel do catálogo: `centro` (+`rotacao`) ou `parede` (+`distancia`) |
| POST | `.../moveis/{id}/mover` | arrastar, girar ou prender numa parede |
| PATCH/DELETE | `.../moveis/{id}` | medidas (com origem), nome, modelo, portas; remover |
| PUT | `.../moveis/{id}/construcao` | montar por dentro (`{construcao}`: chapa, fundo, rodapé, vãos com espaços) ou `null` para desmontar; recusa o que não cabe |
| POST | `.../moveis/{id}/construcao/sugerir` | interior padrão do tipo (guarda-roupa, cômoda, sob medida...) |
| GET | `.../moveis/{id}/planejado` | vista de frente calculada (retângulos em mm), larguras/alturas, peças, chapas, ferragens |

Toda resposta de edição traz `novos` e `problemas`: nos móveis, as checagens de uso do
cômodo (passagem, lateral da cama, frente do guarda-roupa, giro de porta, tomada atrás de
móvel, distância sofá-TV), para a tela mostrar na hora.

**Desfazer, refazer e restaurar nunca apagam nada:** o conteúdo da versão alvo (do
`snapshot`) é gravado como **versão nova**, com a operação `desfazer:N`, `refazer:N` ou
`reverter:N` no histórico. Assim dá para desfazer um desfazer, e o histórico conta tudo.
Qualquer edição nova depois de desfazer zera o refazer. Voltar para antes de um
`renomear` mantém o código atual do projeto.

**Rascunho:** toda edição pela API entra como **passo de rascunho**: uma versão normal
(snapshot e histórico), acima de `projeto.rascunho_desde`. Enquanto há rascunho, o JSON em
`projetos/` não é reexportado (fica igual ao salvo), `interiores importar`/`exportar` recusam
e "restaurar" pede para salvar ou descartar antes. **Desfazer no rascunho** restaura o passo
anterior e **desce a versão**; o passo desfeito fica guardado para o refazer até a próxima
edição. **Salvar** fecha o rascunho (cada passo que ficou vira versão) e exporta; **Descartar**
volta para `rascunho_desde`. `GET .../versoes` traz `rascunho: {desde, passos, refazer}`.

O esquema completo (para gerar os tipos do frontend) está em `/openapi.json`.

## Render pela fila

`make worker` sobe o Redis e o worker (arq), que chama o Blender (Docker) um render por vez.

| Método | Caminho | Para quê |
|---|---|---|
| GET | `/renders/estimativas` | segundos estimados por qualidade (histórico desta máquina) |
| POST | `/projetos/{p}/comodos/{c}/renders` | pedir (`variacao`, `qualidade`: rascunho \| final) → 202 |
| POST | `/projetos/{p}/pavimentos/{a}/renders` | modelo 3D do pavimento inteiro (`qualidade`) → 202; `escopo: pavimento` |
| GET | `/projetos/{p}/renders?comodo=` / `?pavimento=` | pedidos recentes (de um cômodo / do pavimento inteiro) |
| GET | `/renders/{id}` | status, progresso, imagem atual, tempo restante, duração |
| GET | `/renders/{id}/imagens/{nome}` | PNG pronto (`render-<vista>.png`) |
| GET | `/renders/{id}/modelo` | modelo 3D do cômodo ou do pavimento (`.glb`), para o visor; `modelo_url` no render |

- **Qualidades:** rascunho 800×500, 16 amostras (segundos); final 1600×1000, 96 amostras
  (~2 min). O rascunho grava em `<variação>/rascunho/` e nunca sobrescreve o final.
- **Versão:** renderiza a versão do projeto do momento do pedido (snapshot do banco).
- **Estimativa:** mediana dos renders do mesmo tamanho; sem eles, custo por pixel·amostra
  dos outros; sem histórico, o medido (119 s o final).
- **Progresso:** lido da saída do Blender ("Sample x/y", "Remaining"); o tempo restante usa
  o ritmo real depois de 5%.
- Pedido igual (mesmo cômodo, variação, qualidade e versão) já na fila não entra de novo.
