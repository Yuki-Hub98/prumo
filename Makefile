# Atalhos do projeto — ver CLAUDE.md §12.
.DEFAULT_GOAL := help
.PHONY: help setup sync lint format typecheck test check schema validate cad planejado render blender-imagem wiki banco importar exportar api frontend frontend-tipos worker dev up down logs

help: ## Lista os comandos
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

setup: ## uv sync + pre-commit + .relatorios/ e .mrs/ em .git/info/exclude
	uv sync --all-packages
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
	@for d in .relatorios/ .mrs/; do grep -qxF "$$d" .git/info/exclude || echo "$$d" >> .git/info/exclude; done
	@test -f .env || cp .env.example .env

sync: ## Instala/atualiza dependências do workspace
	uv sync --all-packages

lint: ## ruff check + format --check
	uv run ruff check .
	uv run ruff format --check .

format: ## Formata e corrige o que der
	uv run ruff format .
	uv run ruff check --fix .

typecheck: ## mypy --strict no core
	uv run mypy

test: ## pytest com cobertura do core
	uv run pytest --cov

check: lint typecheck test ## Tudo que o CI roda

schema: ## Gera o JSON Schema oficial em schema/
	uv run interiores schema --saida schema

validate: ## Valida um projeto: make validate P=casa
	@test -n "$(P)" || { echo "informe o projeto: make validate P=<projeto>"; exit 2; }
	uv run interiores validar $(P)

cad: ## Plantas DXF/PDF: make cad P=casa [A=terreo] [C=quarto] [F=1 força]
	@test -n "$(P)" || { echo "informe o projeto: make cad P=<projeto> [A=<pavimento>] [C=<cômodo>]"; exit 2; }
	uv run interiores cad $(P) $(if $(A),--pavimento $(A)) $(if $(C),--comodo $(C)) $(if $(F),--forcar)

planejado: ## Desenho e lista de corte: make planejado P=casa C=quarto [M=móvel] [F=1]
	@test -n "$(P)" -a -n "$(C)" || { echo "informe: make planejado P=<projeto> C=<cômodo> [M=<móvel>]"; exit 2; }
	uv run interiores planejado gerar $(P) $(C) $(M) $(if $(F),--forcar)

BLENDER_VERSION ?= 4.5.16

blender-imagem: ## Constrói a imagem Docker do Blender headless (uma vez)
	docker build -f docker/blender.Dockerfile --build-arg BLENDER_VERSION=$(BLENDER_VERSION) -t interiores-blender:$(BLENDER_VERSION) .

render: ## Renders 3D: make render P=casa [C=quarto [V=variação|todas]] [A=terreo] [F=1]; sem C = pavimento inteiro
	@test -n "$(P)" || { echo "informe: make render P=<projeto> [C=<cômodo> [V=<variação>|todas]] [A=<pavimento>]"; exit 2; }
	uv run interiores render $(P) $(C) $(if $(V),--variacao $(V)) $(if $(A),--pavimento $(A)) $(if $(F),--forcar)

wiki: ## Sobe só a wiki de documentação (http://localhost:3000)
	docker compose up -d wiki

banco: ## Sobe o Postgres e aplica as migrações
	docker compose up -d --wait db
	uv run interiores banco atualizar

importar: ## Arquivos → banco: make importar P=casa [F=1 fica com os arquivos]
	@test -n "$(P)" || { echo "informe o projeto: make importar P=<projeto>"; exit 2; }
	uv run interiores importar $(P) $(if $(F),--forcar)

exportar: ## Banco → arquivos: make exportar P=casa [F=1 sobrescreve]
	@test -n "$(P)" || { echo "informe o projeto: make exportar P=<projeto>"; exit 2; }
	uv run interiores exportar $(P) $(if $(F),--forcar)

api: ## Sobe a API (http://localhost:8010/docs); precisa do banco (make banco)
	uv run interiores-api

worker: ## Worker da fila de render (Redis + Blender); precisa de make banco e do redis
	docker compose up -d --wait redis
	uv run interiores-worker

frontend-tipos: ## Regera o OpenAPI e os tipos TypeScript do frontend
	uv run python -c "from interiores_api.app import openapi; openapi()"
	cd frontend && npm run tipos

frontend: ## Frontend em http://localhost:5173 (precisa da API: make api)
	cd frontend && npm run dev

dev: ## Tudo de uma vez: infra + migrações + API + worker + frontend (Ctrl+C para)
	./scripts/dev.sh

up: ## Sobe a infra (docker compose)
	docker compose up -d

down: ## Derruba a infra
	docker compose down

logs: ## Logs da infra
	docker compose logs -f
