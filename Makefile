# ==============================================================================
# Radar de Señal Temprana - Makefile
# Reto 30X "Radar de contenido"
# ==============================================================================

.PHONY: help setup sync test test-ws lint format check worktree clean ask

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ==============================================================================
# Setup
# ==============================================================================
setup: ## Install the env, the pre-commit and commit-msg hooks, and .env from the template
	uv sync
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
	@if [ ! -f .env ]; then cp .env.example .env && chmod 600 .env && echo "Created .env from template"; fi

sync: ## Install every workstream extra (bq, labels, graph, models, api, crosssource)
	uv sync --all-extras

# ==============================================================================
# Quality and tests
# ==============================================================================
test: ## Tests that need no network, BigQuery or lake (what CI runs)
	uv run pytest -m "not bq and not data"

test-ws: ## Contracts are valid JSON Schema and every mock matches its contract
	uv run pytest tests/test_contracts.py

lint: ## Lint
	uv run ruff check .

format: ## Format
	uv run ruff format .

check: ## Every pre-commit hook on every file (identical to CI)
	uv run pre-commit run --all-files

# ==============================================================================
# Agents: make ask Q="¿Qué tema de IA sube esta semana y por qué?"
# ==============================================================================
ask: ## Ask the Media Master (Qwen3-30B via Nebius; NEBIUS_API_KEY in .env)
	uv run python -m agents "$(Q)"

# ==============================================================================
# Worktrees: make worktree BRANCH=feat/ws1-run-bq
# ==============================================================================
worktree: ## New worktree for BRANCH from the latest origin/develop, with the lake linked
	@test -n "$(BRANCH)" || (echo "usage: make worktree BRANCH=<type>/ws<N>-<desc>" && exit 1)
	git fetch origin
	git worktree add -b $(BRANCH) ../radar-worktrees/$(subst /,-,$(BRANCH)) origin/develop
	ln -s ../../radar/lake ../radar-worktrees/$(subst /,-,$(BRANCH))/lake
	@echo "cd ../radar-worktrees/$(subst /,-,$(BRANCH))"

clean: ## Remove caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage coverage.xml
