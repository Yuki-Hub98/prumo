<!--
title: Comandos
description: Referência de todos os comandos (make e CLI)
published: true
date: 2026-11-18T00:00:00.000Z
tags: uso comandos
editor: markdown
dateCreated: 2026-11-18T00:00:00.000Z
-->

# Comandos

Guia rápido para usar o sistema pelo terminal, a partir da raiz do repositório.

Há duas formas de chamar cada coisa:

- `make <alvo> P=... C=...`: atalhos do Makefile (mais curtos);
- `uv run interiores <comando> ...`: a CLI completa, com todas as opções.

Use `uv run interiores --help` ou `uv run interiores <comando> --help` para ver as opções.

---

## 1. Preparar o ambiente (uma vez)

```bash
make setup             # instala dependências, pre-commit e exclui .relatorios/ e .mrs/ do git
make blender-imagem    # imagem Docker do Blender 4.5 LTS (~2 GB), necessária para o render 3D
```

**Subir tudo de uma vez (dia a dia):**

```bash
make dev    # Postgres + Redis (Docker), migrações, API, worker e frontend num terminal só
```

Os logs saem com prefixo (`[api]`, `[worker]`, `[front]`); Ctrl+C para os três (a infra
continua no Docker: `make down` para parar). Se a porta da API ou a 5173 já estiver em uso,
ele avisa e não sobe. Na primeira vez instala as dependências do frontend.

---

## 2. Conferir o projeto

```bash
make validate P=casa                          # valida o projeto e roda as checagens
uv run interiores validar casa --estimadas    # idem, listando cada medida estimada
```

Mostra a área útil de cada cômodo, os problemas por severidade (erro, aviso, info) e
quantas medidas ainda são estimadas (o que deixa os desenhos com "PRELIMINAR").

---

## 3. Desenhos técnicos (planta, cortes, elevações)

```bash
make cad P=casa                 # pavimento + todos os cômodos
make cad P=casa C=quarto        # planta, cortes AA/BB e elevação de cada parede do quarto
make cad P=casa A=terreo        # só a planta geral do pavimento
make cad P=casa C=quarto F=1    # força a regeração
```

Saídas:

- `out/casa/terreo/quarto/base/planta.pdf` / `.dxf`: planta do quarto;
- `out/casa/terreo/quarto/base/corte-aa.pdf`, `corte-bb.pdf`: cortes;
- `out/casa/terreo/quarto/base/elevacao-p1.pdf` … `elevacao-p8.pdf`: cada parede vista de dentro;
- `out/casa/terreo/_geral/planta.pdf`: planta geral do pavimento.

A planta do cômodo mostra o id de cada parede (`p1`, `p2`...) e as linhas dos cortes.
Os DXF abrem no AutoCAD/LibreCAD (1 unidade = 1 mm).

---

## 4. Móveis

### Ver o catálogo

```bash
uv run interiores catalogo          # todos os tipos (cama, guarda_roupa, sofa, tv, mesa...)
uv run interiores catalogo cama     # modelos de um tipo (solteiro, casal, queen, king...)
```

### Adicionar

Prendendo na parede (o sistema calcula a posição e a rotação, virado para o cômodo):

```bash
uv run interiores movel adicionar casa quarto criado_mudo --parede p2 --a 100
uv run interiores movel adicionar casa quarto tv --modelo 55pol --parede p7 --a 400 --elevacao 1000
```

- `--parede`: id da parede (aparece na planta);
- `--a`: mm do início da parede até a borda do móvel (a mesma referência das portas e janelas).

Pelo centro (x, y em mm) e rotação:

```bash
uv run interiores movel adicionar casa quarto cama --modelo queen --em 2485,1325 --rotacao 90
```

- `--rotacao`: 0, 90, 180 ou 270. Em 0, a frente do móvel aponta para cima na planta;
  90 = para a esquerda; 180 = para baixo; 270 = para a direita.

Medidas próprias (substituem as do catálogo):

```bash
uv run interiores movel adicionar casa quarto guarda_roupa --parede p6 --a 300 \
    --largura 2000 --profundidade 600 --altura 2400 --origem trena
```

- `--origem`: `estimada` (padrão), `trena` (medido) ou `projeto` (decidido).
- Medidas que você não informar vêm do catálogo como `estimada`.

### Mover, listar e remover

```bash
uv run interiores movel mover casa quarto tv --parede p2 --a 1200
uv run interiores movel mover casa quarto cama --em 2400,1325 --rotacao 90
uv run interiores movel listar casa quarto
uv run interiores movel remover casa quarto criado-mudo
```

Depois de adicionar ou mover, as checagens do cômodo rodam na hora (passagem, lateral da
cama, porta batendo, TV perto demais, móveis sobrepostos...).

---

## 5. Móveis planejados (por dentro + lista de corte)

```bash
uv run interiores planejado criar casa quarto guarda-roupa   # construção padrão do tipo
make planejado P=casa C=quarto                               # todos os planejados do cômodo
make planejado P=casa C=quarto M=guarda-roupa                # só um móvel
uv run interiores planejado criar casa quarto guarda-roupa --substituir   # recomeça
```

Tipos planejáveis: guarda_roupa, armario, comoda, criado_mudo, estante, rack, sapateira,
penteadeira.

Saídas em `out/casa/terreo/quarto/base/`:

- `planejado-guarda-roupa.pdf` / `.dxf`: vista frontal (sem portas) e lateral, cotadas;
- `planejado-guarda-roupa-corte.xlsx`: peças (medidas, quantidade, fita de borda),
  ferragens e estimativa de chapas.

A construção fica no campo `construcao` do móvel em `projetos/casa/comodos/quarto.json`
(vãos, gavetas, nichos, cabideiros; o que não tiver medida divide o espaço que sobra).

---

## 6. Render 3D

```bash
make render P=casa C=quarto                            # ~1min40
make render P=casa C=quarto V=escura                   # uma variação de cor
make render P=casa C=quarto V=todas                    # base + todas as variações
make render P=casa C=quarto F=1                        # força a regeração
uv run interiores render casa quarto --amostras 16     # prévia rápida (~30 s, menos qualidade)
```

Saídas em `out/casa/terreo/quarto/<variação>/`:

- `render-perspectiva.png`: o quarto visto de dentro;
- `render-superior.png`: vista de cima, sem o teto;
- `quarto.glb`: modelo 3D (abre no Blender, no `f3d` ou em visualizadores de glTF).

### Pavimento inteiro (a casa)

```bash
make render P=casa                                     # todos os pavimentos (~10 s rascunho)
make render P=casa A=terreo                            # só um pavimento
```

Todos os cômodos do pavimento juntos, cada parede uma vez só, com o **teto cortado**.
Saídas em `out/casa/terreo/_geral/`: `render-perspectiva.png` (vista aérea),
`render-superior.png` (de cima) e `terreo.glb`. Usa as cores padrão (as variações são por
cômodo). Sai PRELIMINAR se qualquer cômodo do pavimento tiver medida estimada.

### Variações de cor

Crie `projetos/casa/variacoes/quarto/<nome>.json`, por exemplo `escura.json`:

```json
{
  "schema_version": 1,
  "comodo": "quarto",
  "nome": "Escura",
  "cores": {
    "parede": "#7A8B94",
    "piso": "#5C3D24",
    "teto": "#FAFAFA",
    "rodape": "#FFFFFF",
    "moveis": {"guarda_roupa": "#2F3B45", "cama": "#3E2C20"},
    "pecas": {"guarda_roupa": {"portas": "#F2EFE8", "puxadores": "#C9A227"},
              "cama": {"travesseiros": "#C0392B", "roupa_de_cama": "#2E5E8C"}}
  }
}
```

`pecas` dá cor a uma parte do móvel (por id ou tipo); o resto do móvel fica com a cor de
`moveis`. Partes: portas, gavetas, puxadores, prateleiras, cabeceira, colchão
(`colchao`), roupa de cama (`roupa_de_cama`, o edredom), travesseiros, almofadas, encosto,
braços (`bracos`), assento, tampo, pés (`pes`) e moldura; quais cada móvel tem depende do
tipo (`interiores_core.partes`).

Em `moveis`, vale o id de um móvel (`"guarda-roupa"`) ou o tipo (`"guarda_roupa"`, todos
daquele tipo). Tudo é opcional: o que faltar usa a cor padrão.

---

### Comparar as variações lado a lado

```bash
make compare P=casa C=quarto                     # todas as variações com imagem (perspectiva)
make compare P=casa C=quarto V=base,escura VISTA=superior
```

Junta a imagem pronta de cada variação (final ou, sem ela, o rascunho) numa grade com o nome
de cada uma: `out/casa/terreo/quarto/_comparacao/comparacao-<vista>.png`. Precisa de pelo menos
duas variações renderizadas (`make render P=casa C=quarto V=todas`).

### Tinta

```bash
make tinta P=casa                                # cores padrão
make tinta P=casa VAR="quarto=escura"            # com a variação de cor do quarto
```

Planilha `out/casa/terreo/_geral/tinta.xlsx`: aba **Comprar** (por tinta e cor: área, litros e
latas sugeridas) e aba **Por cômodo** (paredes, parede de destaque, teto, rodapé e portas).
Paredes e teto em látex; portas (dos dois lados) e rodapé em esmalte. A área das paredes é a
face de cada parede voltada para o cômodo × pé-direito, menos portas, janelas e a faixa do
rodapé. Padrões (estimativa de rótulo): látex 10 m²/L por demão, esmalte 8 m²/L, 2 demãos,
10 % de perda, latas de 18 / 3,6 / 0,9 L (látex) e 3,6 / 0,9 / 0,225 L (esmalte). Troque no
`regras.toml`:

```toml
[tinta]
rendimento_latex = 12
demaos_latex = 3
perda = 0.15
latas_latex = [18, 3.6]
```

Sai com "PRELIMINAR" se houver medida estimada: confira as áreas antes de comprar.

---

## 7. Configurar os limites das checagens

Crie `projetos/casa/regras.toml` (opcional; os valores abaixo são os padrões):

```toml
[geral]
passagem_livre = 700          # mm
distancia_tela_pct = 150      # distância da TV = 1,5 × a diagonal
prateleira_vao_max = 900      # móveis planejados
cabideiro_altura_min = 1000
cabideiro_profundidade_min = 550
gaveta_largura_min = 300

[quarto]
lateral_cama = 600
frente_guarda_roupa = 900     # só porta de abrir
largura_cama_casal = 1200

[cozinha]
triangulo_min = 3600          # soma pia–fogão–geladeira
triangulo_max = 6600
pia_ponto_max = 300           # água fria e esgoto até a pia
altura_bancada = 900
altura_bancada_tolerancia = 50
fogao_janela = 300            # fogão mais perto que isto da janela = "embaixo"
```

---

## 8. Desenvolvimento

```bash
make check                                   # lint + tipos + testes (o que o CI roda)
make test                                    # só os testes
PRUMO_TESTAR_BLENDER=1 uv run pytest -m blender   # teste com o Blender de verdade (lento)
make schema                                  # regera schema/*.json (frontend)
make format                                  # formata o código
```

---

## Dicas

- Tudo é gerado de novo só quando algo mudou (medidas, móveis, regras, variações).
  Se nada mudou, o comando responde "inalterado" na hora. Use `F=1` / `--forcar` para refazer.
- Enquanto houver medida `estimada`, desenhos e renders saem com "PRELIMINAR — NÃO USAR
  PARA OBRA". Ao trocar por medidas de trena, o aviso some sozinho.
- Ids do projeto `casa`: cômodos `quarto` e `banheiro`; paredes `p1`–`p8`; móveis do quarto
  `cama`, `guarda-roupa`, `tv`, `armario`.
- Nada em `out/` deve ser editado à mão: é sempre regerado a partir de `projetos/`.
