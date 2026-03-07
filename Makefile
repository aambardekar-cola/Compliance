.PHONY: help install-backend install-frontend install dev-backend dev-frontend dev test deploy lint

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install-backend: ## Install backend dependencies
	cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

install-frontend: ## Install frontend dependencies
	cd frontend && npm install

install: install-backend install-frontend ## Install all dependencies

dev-backend: ## Run backend dev server
	cd backend && source .venv/bin/activate && uvicorn api.main:app --reload --port 8000

dev-frontend: ## Run frontend dev server
	cd frontend && npm run dev

test-backend: ## Run backend tests
	cd backend && source .venv/bin/activate && pytest ../tests/backend/ -v

test-frontend: ## Run frontend tests
	cd frontend && npm test

test: test-backend test-frontend ## Run all tests

lint-backend: ## Lint backend code
	cd backend && source .venv/bin/activate && ruff check . && ruff format --check .

lint-frontend: ## Lint frontend code
	cd frontend && npm run lint

lint: lint-backend lint-frontend ## Lint all code

deploy: ## Deploy all CDK stacks
	cd infrastructure && cdk deploy --all --require-approval broadening

synth: ## Synthesize CDK stacks (dry run)
	cd infrastructure && cdk synth
