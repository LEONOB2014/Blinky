# ==============================================================================
# Radar de Señal Temprana - Makefile
# Reto 30X "Radar de contenido"
# ==============================================================================

.PHONY: demo-check help setup sync test test-ws lint format check worktree clean ask api-dev web-dev \
	deploy-push-lake deploy-serve deploy-api deploy-static deploy-web \
	deploy-cloudrun-stage deploy-cloudrun-local deploy-cloudrun

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
# WS5: API and web UI
# ==============================================================================
api-dev: ## Run the FastAPI server on port 8000 (RADAR_PROFILE=dev by default)
	uv run --extra api uvicorn api.app:app --reload --host 127.0.0.1 --port 8000

web-dev: ## Run the Vite dev server in web/ (bun)
	cd web && bun run dev

# ==============================================================================
# Deploy (WS8): deploy/README.md has the full order. Paid or public steps need the maintainer.
# ==============================================================================
deploy-push-lake: ## Upload the API's lake tables to the Modal Volume radar-lake
	RADAR_PROFILE=full uv run --extra deploy python deploy/push_lake.py

deploy-serve: ## Temporary Modal URL for the API (no secret: /api/chat answers 503)
	RADAR_NEBIUS_SECRET=0 uv run --extra deploy modal serve deploy/modal_app.py

deploy-api: ## Deploy the API on Modal (needs the radar-nebius secret; maintainer's approval)
	uv run --extra deploy modal deploy deploy/modal_app.py

deploy-cloudrun-stage: ## Stage the Cloud Run build context in build/cloudrun/ (code + the API's lake tables)
	RADAR_PROFILE=full uv run python deploy/cloudrun_stage.py

deploy-cloudrun-local: deploy-cloudrun-stage ## Build and run the Cloud Run image locally on :18080
	docker build -t radar-api:local build/cloudrun
	docker run --rm -p 18080:8080 -e PORT=8080 radar-api:local

deploy-cloudrun: deploy-cloudrun-stage ## Deploy the API on Cloud Run (MIN_INSTANCES keeps a warm instance; default 0)
	gcloud run deploy radar-api --source build/cloudrun --region $(or $(REGION),us-central1) \
		--allow-unauthenticated --cpu 1 --memory 1Gi --min-instances $(or $(MIN_INSTANCES),0) \
		--max-instances 3 \
		--set-secrets NEBIUS_API_KEY=radar-nebius-key:latest,LANGSMITH_API_KEY=radar-langsmith-key:latest \
		--update-env-vars LANGSMITH_TRACING=true,LANGSMITH_PROJECT=radar-agents --quiet

deploy-static: ## Write the static fallback to web/public/data/ from the full lake
	RADAR_PROFILE=full uv run --extra api python deploy/export_static.py

deploy-web: ## Build web/dist with API_URL (empty = static only)
	cd web && bun install && VITE_API_BASE_URL="$(API_URL)" bun run build

redeploy-all: ## The final redeploy, in order (dry run by default; ARGS=--run deploys)
	bash scripts/redeploy_all.sh $(ARGS)

demo-check: ## Check the public site and API before the demo (ARGS=--chat adds one real chat turn)
	uv run python scripts/demo_check.py $(ARGS)

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
