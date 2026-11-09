# =============================================================================
# PayFlow AI - Master Makefile
# =============================================================================
# Comprehensive command interface for development, testing, deployment,
# and maintenance of the PayFlow AI platform.
#
# Usage:
#   make help          # Show all available commands
#   make <target>      # Run a specific command
#
# Version: 2.0.0
# =============================================================================

.PHONY: help build dev prod stop clean logs shell test monitor

# Default target
.DEFAULT_GOAL := help

# =============================================================================
# VARIABLES
# =============================================================================
COMPOSE := docker compose
COMPOSE_PROD := $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

# =============================================================================
# HELP
# =============================================================================
help: ## Show this help message
	@echo "$(BLUE)PayFlow AI - Available Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Usage:$(NC) make [target]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make dev              # Start development environment"
	@echo "  make test             # Run all tests"
	@echo "  make diagrams         # Render architecture diagrams"
	@echo ""

# =============================================================================
# DOCKER - BUILD
# =============================================================================
build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	$(COMPOSE) build
	@echo "$(GREEN)✓ Build complete$(NC)"

build-no-cache: ## Build Docker images without cache
	@echo "$(BLUE)Building Docker images (no cache)...$(NC)"
	$(COMPOSE) build --no-cache
	@echo "$(GREEN)✓ Build complete$(NC)"

# =============================================================================
# DOCKER - DEVELOPMENT
# =============================================================================
dev: ## Start development environment with hot reload
	@echo "$(BLUE)Starting development environment...$(NC)"
	$(COMPOSE) --profile dev up -d
	@echo ""
	@echo "$(GREEN)✓ Development environment started!$(NC)"
	@echo ""
	@echo "$(YELLOW)Services:$(NC)"
	@echo "  - API:           http://localhost:8000"
	@echo "  - API Docs:      http://localhost:8000/docs"
	@echo "  - Dashboard:     http://localhost:8501"
	@echo "  - Webhook:       http://localhost:8001"
	@echo "  - Elasticsearch: http://localhost:9200"
	@echo "  - Kibana:        http://localhost:5601"
	@echo ""

dev-down: ## Stop development environment
	@echo "$(BLUE)Stopping development environment...$(NC)"
	$(COMPOSE) --profile dev down
	@echo "$(GREEN)✓ Stopped$(NC)"

dev-logs: ## Show logs for development environment
	$(COMPOSE) --profile dev logs -f

dev-logs-api: ## Show API logs only
	$(COMPOSE) --profile dev logs -f api

dev-logs-app: ## Show dashboard logs only
	$(COMPOSE) --profile dev logs -f app

dev-logs-webhook: ## Show webhook listener logs only
	$(COMPOSE) --profile dev logs -f webhook

# =============================================================================
# DOCKER - PRODUCTION
# =============================================================================
prod: ## Start production environment
	@echo "$(BLUE)Starting production environment...$(NC)"
	$(COMPOSE_PROD) --profile prod up -d
	@echo ""
	@echo "$(GREEN)✓ Production environment started!$(NC)"
	@echo ""
	@echo "$(YELLOW)Services:$(NC)"
	@echo "  - API:           http://localhost:8000"
	@echo "  - Dashboard:     http://localhost:8501"
	@echo "  - Webhook:       http://localhost:8001"
	@echo "  - Elasticsearch: http://localhost:9200"
	@echo ""

prod-down: ## Stop production environment
	@echo "$(BLUE)Stopping production environment...$(NC)"
	$(COMPOSE_PROD) --profile prod down
	@echo "$(GREEN)✓ Stopped$(NC)"

prod-logs: ## Show logs for production environment
	$(COMPOSE_PROD) --profile prod logs -f

# =============================================================================
# DOCKER - MONITORING
# =============================================================================
monitor: ## Start monitoring stack (Prometheus, Grafana, Jaeger)
	@echo "$(BLUE)Starting monitoring stack...$(NC)"
	$(COMPOSE) --profile monitoring up -d
	@echo ""
	@echo "$(GREEN)✓ Monitoring stack started!$(NC)"
	@echo ""
	@echo "$(YELLOW)Services:$(NC)"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana:    http://localhost:3000 (admin/admin123)"
	@echo "  - Jaeger:     http://localhost:16686"
	@echo ""

monitor-down: ## Stop monitoring stack
	@echo "$(BLUE)Stopping monitoring stack...$(NC)"
	$(COMPOSE) --profile monitoring down
	@echo "$(GREEN)✓ Stopped$(NC)"

monitor-logs: ## Show logs for monitoring stack
	$(COMPOSE) --profile monitoring logs -f

# =============================================================================
# DOCKER - DATA SERVICES
# =============================================================================
data: ## Start data services (Elasticsearch, Kibana)
	@echo "$(BLUE)Starting data services...$(NC)"
	$(COMPOSE) --profile data up -d
	@echo ""
	@echo "$(GREEN)✓ Data services started!$(NC)"
	@echo ""
	@echo "$(YELLOW)Services:$(NC)"
	@echo "  - Elasticsearch: http://localhost:9200"
	@echo "  - Kibana:        http://localhost:5601"
	@echo ""

data-down: ## Stop data services
	@echo "$(BLUE)Stopping data services...$(NC)"
	$(COMPOSE) --profile data down
	@echo "$(GREEN)✓ Stopped$(NC)"

# =============================================================================
# DOCKER - STOP & CLEAN
# =============================================================================
stop: ## Stop all running containers
	@echo "$(BLUE)Stopping all containers...$(NC)"
	$(COMPOSE) --profile dev --profile prod --profile monitoring --profile data stop
	@echo "$(GREEN)✓ All containers stopped$(NC)"

down: ## Stop and remove containers
	@echo "$(BLUE)Stopping and removing containers...$(NC)"
	$(COMPOSE) --profile dev --profile prod --profile monitoring --profile data down
	@echo "$(GREEN)✓ Containers removed$(NC)"

clean: ## Stop and remove containers, networks, and volumes
	@echo "$(YELLOW)Cleaning up containers, networks, and volumes...$(NC)"
	$(COMPOSE) --profile dev --profile prod --profile monitoring --profile data down -v
	@echo "$(GREEN)✓ Cleaned up$(NC)"

clean-all: ## Remove everything including images
	@echo "$(RED)WARNING: This will remove all containers, networks, volumes, and images!$(NC)"
	@read -p "Are you sure? [y/N] " confirm && [ $$confirm = "y" ] || exit 1
	$(COMPOSE) --profile dev --profile prod --profile monitoring --profile data down -v --rmi all
	docker system prune -f
	@echo "$(GREEN)✓ Everything cleaned$(NC)"

# =============================================================================
# LOGS & DEBUGGING
# =============================================================================
logs: ## Show logs for all services
	$(COMPOSE) logs -f

logs-api: ## Show logs for API service
	$(COMPOSE) logs -f api

logs-app: ## Show logs for Streamlit app
	$(COMPOSE) logs -f app

logs-webhook: ## Show logs for webhook listener
	$(COMPOSE) logs -f webhook

logs-es: ## Show logs for Elasticsearch
	$(COMPOSE) logs -f elasticsearch

# =============================================================================
# SHELL & DEBUGGING
# =============================================================================
shell-api: ## Open shell in API container
	@echo "$(BLUE)Opening shell in API container...$(NC)"
	$(COMPOSE) exec api /bin/bash

shell-app: ## Open shell in Streamlit container
	@echo "$(BLUE)Opening shell in Streamlit container...$(NC)"
	$(COMPOSE) exec app /bin/bash

shell-webhook: ## Open shell in webhook container
	@echo "$(BLUE)Opening shell in webhook container...$(NC)"
	$(COMPOSE) exec webhook /bin/bash

shell-es: ## Open shell in Elasticsearch container
	@echo "$(BLUE)Opening shell in Elasticsearch container...$(NC)"
	$(COMPOSE) exec elasticsearch /bin/bash

# =============================================================================
# TESTING
# =============================================================================
test: ## Run all tests (unit + integration)
	@echo "$(BLUE)Running all tests...$(NC)"
	pytest tests/ -v
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(NC)"
	pytest tests/ -m "not integration and not performance" -v
	@echo "$(GREEN)✓ Unit tests complete$(NC)"

test-integration: ## Run integration tests only
	@echo "$(BLUE)Running integration tests...$(NC)"
	pytest tests/integration/ -v
	@echo "$(GREEN)✓ Integration tests complete$(NC)"

test-performance: ## Run performance benchmarks
	@echo "$(BLUE)Running performance benchmarks...$(NC)"
	pytest tests/performance/ -v
	@echo "$(GREEN)✓ Benchmarks complete$(NC)"

test-coverage: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	pytest tests/ --cov=. --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "$(GREEN)✓ Coverage report generated$(NC)"
	@echo "$(YELLOW)Open htmlcov/index.html to view$(NC)"

test-fast: ## Run fast tests only (skip slow and performance)
	@echo "$(BLUE)Running fast tests...$(NC)"
	pytest tests/ -m "not slow and not performance" -v
	@echo "$(GREEN)✓ Fast tests complete$(NC)"

test-watch: ## Run tests in watch mode (auto-rerun on changes)
	@echo "$(BLUE)Running tests in watch mode...$(NC)"
	ptw --runner "pytest tests/ -v"

# =============================================================================
# CODE QUALITY
# =============================================================================
lint: ## Run all linters (flake8, mypy, black check)
	@echo "$(BLUE)Running linters...$(NC)"
	@echo ""
	@echo "$(YELLOW)1. Checking code formatting (black)...$(NC)"
	black --check . || echo "$(RED)✗ Black found formatting issues$(NC)"
	@echo ""
	@echo "$(YELLOW)2. Checking import sorting (isort)...$(NC)"
	isort --check-only . || echo "$(RED)✗ Isort found import issues$(NC)"
	@echo ""
	@echo "$(YELLOW)3. Running flake8...$(NC)"
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=15 --max-line-length=120 --statistics
	@echo ""
	@echo "$(YELLOW)4. Running mypy (type checking)...$(NC)"
	mypy . --ignore-missing-imports || echo "$(RED)✗ Mypy found type issues$(NC)"
	@echo ""
	@echo "$(GREEN)✓ Linting complete$(NC)"

format: ## Auto-format code (black, isort)
	@echo "$(BLUE)Formatting code...$(NC)"
	black .
	isort .
	@echo "$(GREEN)✓ Code formatted$(NC)"

security-scan: ## Run security scans (bandit, safety)
	@echo "$(BLUE)Running security scans...$(NC)"
	@echo ""
	@echo "$(YELLOW)1. Scanning code with bandit...$(NC)"
	bandit -r . -ll -ii --skip B101,B104,B105,B108,B311 || echo "$(RED)✗ Bandit found security issues$(NC)"
	@echo ""
	@echo "$(YELLOW)2. Checking dependencies with safety...$(NC)"
	safety check --full-report || echo "$(RED)✗ Safety found vulnerable dependencies$(NC)"
	@echo ""
	@echo "$(GREEN)✓ Security scan complete$(NC)"

# =============================================================================
# ARCHITECTURE DIAGRAMS
# =============================================================================
diagrams: ## Render all architecture diagrams to PNG (uses Kroki API)
	@echo "$(BLUE)Rendering architecture diagrams...$(NC)"
	python docs/architecture/render_diagrams.py
	@echo "$(GREEN)✓ Diagrams rendered$(NC)"

diagrams-offline: ## Render diagrams using local plantuml.jar
	@echo "$(BLUE)Rendering diagrams (offline mode)...$(NC)"
	python docs/architecture/render_diagrams.py --local
	@echo "$(GREEN)✓ Diagrams rendered$(NC)"

diagrams-docker: ## Render diagrams using Docker
	@echo "$(BLUE)Rendering diagrams (Docker mode)...$(NC)"
	python docs/architecture/render_diagrams.py --docker
	@echo "$(GREEN)✓ Diagrams rendered$(NC)"

diagrams-svg: ## Render all diagrams to SVG (better for README scaling)
	@echo "$(BLUE)Rendering diagrams to SVG...$(NC)"
	python docs/architecture/render_diagrams.py --format svg
	@echo "$(GREEN)✓ Diagrams rendered$(NC)"

diagrams-list: ## List all available diagram source files
	@echo "$(BLUE)📊 Available diagrams:$(NC)"
	@ls -1 docs/architecture/*.puml 2>/dev/null | sed 's|docs/architecture/|  - |' | sed 's|.puml||' || echo "  (no diagrams found)"

# =============================================================================
# DEMO
# =============================================================================
demo-terminal: ## Run terminal demo
	@echo "$(BLUE)Running terminal demo...$(NC)"
	python demo_terminal.py

demo-dashboard: ## Run Streamlit demo dashboard
	@echo "$(BLUE)Starting demo dashboard...$(NC)"
	streamlit run demo_dashboard.py

# =============================================================================
# STATUS & HEALTH
# =============================================================================
status: ## Show status of all containers
	@echo "$(BLUE)Container Status:$(NC)"
	$(COMPOSE) ps

health: ## Check health of all services
	@echo "$(BLUE)Checking service health...$(NC)"
	@echo ""
	@echo "$(YELLOW)API:$(NC)"
	@curl -s http://localhost:8000/health | jq -r '.status' 2>/dev/null || echo "$(RED)✗ Unhealthy or not running$(NC)"
	@echo ""
	@echo "$(YELLOW)Elasticsearch:$(NC)"
	@curl -s http://localhost:9200/_cluster/health | jq -r '.status' 2>/dev/null || echo "$(RED)✗ Unhealthy or not running$(NC)"
	@echo ""
	@echo "$(YELLOW)Dashboard:$(NC)"
	@curl -s http://localhost:8501/healthz >/dev/null 2>&1 && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Unhealthy or not running$(NC)"
	@echo ""

# =============================================================================
# DEVELOPMENT UTILITIES
# =============================================================================
install: ## Install all dependencies (production + development)
	@echo "$(BLUE)Installing dependencies...$(NC)"
	pip install -r requirements-dev.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

install-prod: ## Install production dependencies only
	@echo "$(BLUE)Installing production dependencies...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

venv: ## Create virtual environment
	@echo "$(BLUE)Creating virtual environment...$(NC)"
	python3 -m venv .venv
	@echo "$(GREEN)✓ Virtual environment created$(NC)"
	@echo "$(YELLOW)Activate with:$(NC) source .venv/bin/activate"

setup: ## Complete initial setup (venv + install + build)
	@echo "$(BLUE)Running complete setup...$(NC)"
	@echo ""
	@echo "$(YELLOW)Step 1: Creating virtual environment...$(NC)"
	python3 -m venv .venv
	@echo "$(YELLOW)Step 2: Activating virtual environment...$(NC)"
	. .venv/bin/activate && \
	echo "$(YELLOW)Step 3: Installing dependencies...$(NC)" && \
	pip install -r requirements-dev.txt && \
	echo "$(YELLOW)Step 4: Building Docker images...$(NC)" && \
	$(COMPOSE) build && \
	echo "" && \
	echo "$(GREEN)✓ Setup complete!$(NC)" && \
	echo "$(YELLOW)Next steps:$(NC)" && \
	echo "  1. Copy .env.example to .env and fill in your credentials" && \
	echo "  2. Run: make dev" && \
	echo "  3. Open: http://localhost:8501"

# =============================================================================
# DOCUMENTATION
# =============================================================================
docs: ## Build documentation (if mkdocs is configured)
	@echo "$(BLUE)Building documentation...$(NC)"
	@if [ -f "mkdocs.yml" ]; then \
		mkdocs build; \
		echo "$(GREEN)✓ Documentation built$(NC)"; \
		echo "$(YELLOW)Open site/index.html to view$(NC)"; \
	else \
		echo "$(YELLOW)No mkdocs.yml found. Skipping.$(NC)"; \
	fi

docs-serve: ## Serve documentation locally
	@echo "$(BLUE)Serving documentation...$(NC)"
	@if [ -f "mkdocs.yml" ]; then \
		mkdocs serve; \
	else \
		echo "$(YELLOW)No mkdocs.yml found. Skipping.$(NC)"; \
	fi

# =============================================================================
# CI/CD HELPERS
# =============================================================================
ci-test: ## Run tests as CI would (with coverage)
	@echo "$(BLUE)Running CI-style tests...$(NC)"
	pytest tests/ \
		--cov=. \
		--cov-report=xml \
		--cov-report=html \
		--cov-report=term-missing \
		--junitxml=junit/test-results.xml \
		-v
	@echo "$(GREEN)✓ CI tests complete$(NC)"

ci-lint: ## Run linting as CI would
	@echo "$(BLUE)Running CI-style linting...$(NC)"
	black --check .
	isort --check-only .
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	@echo "$(GREEN)✓ CI linting complete$(NC)"

# =============================================================================
# RELEASE
# =============================================================================
release-check: ## Pre-release checks (tests, lint, security)
	@echo "$(BLUE)Running pre-release checks...$(NC)"
	@echo ""
	@echo "$(YELLOW)1. Running tests...$(NC)"
	$(MAKE) test
	@echo ""
	@echo "$(YELLOW)2. Running linters...$(NC)"
	$(MAKE) lint
	@echo ""
	@echo "$(YELLOW)3. Running security scan...$(NC)"
	$(MAKE) security-scan
	@echo ""
	@echo "$(GREEN)✓ All pre-release checks passed!$(NC)"

# =============================================================================
# UTILITY
# =============================================================================
clean-pyc: ## Remove Python cache files
	@echo "$(BLUE)Cleaning Python cache files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete
	find . -type f -name "*$$py.class" -delete
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-logs: ## Remove log files
	@echo "$(BLUE)Cleaning log files...$(NC)"
	rm -rf logs/*
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-coverage: ## Remove coverage reports
	@echo "$(BLUE)Cleaning coverage reports...$(NC)"
	rm -rf htmlcov/ .coverage coverage.xml
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-all-local: ## Clean all local artifacts (pyc, logs, coverage)
	@echo "$(YELLOW)Cleaning all local artifacts...$(NC)"
	$(MAKE) clean-pyc
	$(MAKE) clean-logs
	$(MAKE) clean-coverage
	@echo "$(GREEN)✓ All cleaned$(NC)"

# =============================================================================
# SHORTCUTS
# =============================================================================
up: dev ## Alias for 'make dev'
down: dev-down ## Alias for 'make dev-down'
t: test ## Alias for 'make test'
tu: test-unit ## Alias for 'make test-unit'
ti: test-integration ## Alias for 'make test-integration'
tp: test-performance ## Alias for 'make test-performance'
tc: test-coverage ## Alias for 'make test-coverage'
l: lint ## Alias for 'make lint'
f: format ## Alias for 'make format'
d: diagrams ## Alias for 'make diagrams'
s: status ## Alias for 'make status'
h: health ## Alias for 'make health'

# =============================================================================
# END
# =============================================================================