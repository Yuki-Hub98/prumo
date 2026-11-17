# Atalhos do projeto — ver CLAUDE.md §12.
.DEFAULT_GOAL := help
.PHONY: help setup sync lint format typecheck test check up down logs

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

up: ## Sobe a infra (docker compose)
	docker compose up -d

down: ## Derruba a infra
	docker compose down

logs: ## Logs da infra
	docker compose logs -f
