.DEFAULT_GOAL := help
.PHONY: help setup up down test test-unit lint format

help: ## Lista os alvos disponíveis
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Instala dependências, cria o .env e ativa o pre-commit
	uv sync --locked
	@test -f .env || cp .env.example .env
	uv run pre-commit install

up: ## Sobe a stack e espera todos os serviços ficarem saudáveis
	docker compose up -d --wait --wait-timeout 300

down: ## Derruba a stack e mantém os volumes
	docker compose down

test: ## Roda todos os testes (precisa de make up)
	uv run pytest

test-unit: ## Roda só os testes que não dependem da stack
	uv run pytest -m "not integration"

lint: ## Roda ruff e mypy
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

format: ## Formata o código e corrige o que o ruff consegue
	uv run ruff check --fix .
	uv run ruff format .
