.DEFAULT_GOAL := help
SPLIT ?= dev
LABEL ?= local
DATASET ?= evals/datasets/sql.jsonl
EVAL_SNAPSHOT ?= data/snapshots/evals-2026-09
.PHONY: help setup up down ingest cnpj transform snapshot dbt-parse api ui evals eval-snapshot eval-restore evals-offline test test-unit lint format

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

ingest: ## Baixa as fontes públicas, valida e grava o staging em Parquet
	uv run python -m telecom_analyst.ingest

cnpj: ## Baixa a base do CNPJ e grava o recorte de telecom (precisa de make ingest)
	uv run python -m telecom_analyst.etl cnpj

transform: ## Carrega o Postgres, roda o dbt e gera o dicionário de dados
	uv run python -m telecom_analyst.etl load
	set -a; . ./.env; set +a; uv run dbt build --project-dir dbt --profiles-dir dbt
	uv run python -m telecom_analyst.etl dictionary

dbt-parse: ## Confere se o projeto dbt compila, sem precisar de dados
	set -a; . ./.env; set +a; uv run dbt parse --project-dir dbt --profiles-dir dbt

snapshot: ## Congela marts e semantic em data/snapshots/AAAA-MM
	@set -a; . ./.env; set +a; \
	period=$$(docker compose exec -T postgres psql -U $$POSTGRES_USER -d $$POSTGRES_DB -Atc \
		"SELECT to_char(snapshot_date, 'YYYY-MM') FROM semantic.snapshot"); \
	mkdir -p data/snapshots/$$period; \
	docker compose exec -T postgres pg_dump -U $$POSTGRES_USER -d $$POSTGRES_DB -Fc -n marts -n semantic \
		> data/snapshots/$$period/warehouse.dump; \
	sha256sum data/snapshots/$$period/warehouse.dump > data/snapshots/$$period/warehouse.dump.sha256; \
	echo "snapshot $$period gravado"

api: ## Sobe a API do agente na porta 8010
	uv run uvicorn telecom_analyst.api.main:app --port 8010

ui: ## Sobe a tela de demonstração na porta 8501
	uv run streamlit run ui/app.py

evals: ## Roda as perguntas golden. Uso: make evals SPLIT=dev LABEL=v1
	uv run python -m evals.run_evals --split $(SPLIT) --label $(LABEL) --dataset $(DATASET)

eval-snapshot: ## Gera o snapshot reduzido das evals
	uv run python -m evals.snapshot export $(EVAL_SNAPSHOT)

eval-restore: ## Restaura o snapshot reduzido no banco telecom_eval
	uv run python -m evals.snapshot load $(EVAL_SNAPSHOT) telecom_eval

evals-offline: ## Confere referências e busca de provedores, sem LLM, no banco telecom_eval
	POSTGRES_DB=telecom_eval uv run python -m evals.check_offline

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
