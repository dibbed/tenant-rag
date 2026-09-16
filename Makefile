# Makefile for RAG Telegram Assistant Development
.PHONY: help setup test lint format clean build deploy all

## 📋 Help
help:  ## Show this help message
	@echo "🤖 RAG Telegram Assistant Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

## 🚀 Setup & Development
setup:  ## Install all dependencies and setup development environment
	@echo "📦 Installing Python dependencies..."
	@pip install --upgrade pip
	@pip install -r requirements.txt
	@pip install pytest pytest-asyncio pytest-cov mypy ruff coverage hypothesis
	@echo "\n✅ Development environment ready!"

setup-dev: ## Install with additional development tools
	@echo "🛠️ Installing development dependencies..."
	@pip install -r requirements.txt
	@pip install pytest pytest-asyncio pytest-cov mypy ruff coverage hypothesis black isort
	@echo "\n✅ Development environment with all tools ready!"

## 🧪 Testing
test:  ## Run all tests with coverage
	@echo "🧪 Running test suite..."
	@pytest tests/ --cov=ragbot --cov-report=term-missing --cov-report=html -v

test-unit:  ## Run unit tests only
	@echo "🔬 Running unit tests..."
	@pytest tests/unit/ -v

test-integration:  ## Run integration tests only
	@echo "🔗 Running integration tests..."
	@pytest tests/integration/ -v

test-e2e:  ## Run end-to-end tests only
	@echo "🎯 Running E2E tests..."
	@pytest tests/e2e/ -v

test-coverage:  ## Generate detailed coverage report
	@echo "📊 Generating coverage report..."
	@pytest --cov=ragbot --cov-report=html --cov-report=xml
	@echo "\n📄 HTML report available at: htmlcov/index.html"

## 🔍 Code Quality
lint:  ## Run linting checks
	@echo "🔍 Running linters..."
	@ruff check .
	@mypy ragbot --ignore-missing-imports || true
	@echo "\n✅ Linting completed!"

format:  ## Format code using Ruff
	@echo "💅 Formatting code..."
	@ruff check --fix .
	@ruff format .
	@echo "\n✅ Code formatted!"

type-check:  ## Run MyPy type checking
	@echo "🔧 Running type checking..."
	@mypy ragbot --ignore-missing-imports

security:  ## Run security checks
	@echo "🔒 Running security checks..."
	@pip audit || echo "pip-audit not installed, run: pip install pip-audit"
	@bandit -r ragbot/ || echo "bandit not installed, run: pip install bandit"

## 🐳 Docker
build:  ## Build Docker image
	@echo "🏗️ Building Docker image..."
	@docker build -t rag-telegram-assistant .
	@echo "\n✅ Docker image built successfully!"

build-dev:  ## Build development Docker image with tools
	@echo "🏗️ Building development Docker image..."
	@docker build --target development -t rag-telegram-assistant:dev .

run-docker:  ## Run the bot in Docker container
	@echo "🚀 Running bot in Docker..."
	@docker run --env-file .env rag-telegram-assistant

docker-compose-up:  ## Start with Docker Compose
	@echo "🚀 Starting with Docker Compose..."
	@docker-compose up --build -d

docker-compose-logs:  ## View Docker Compose logs
	@echo "📋 Viewing logs..."
	@docker-compose logs -f

## 🚀 Deployment
deploy-dev:  ## Deploy to development environment
	@echo "🚀 Deploying to development..."
	# Add your development deployment commands here
	@echo "✅ Development deployment complete!"

deploy-prod:  ## Deploy to production environment
	@echo "🎯 Deploying to production..."
	# Add your production deployment commands here
	@echo "✅ Production deployment complete!"

## 📁 File Management
backup-data:  ## Backup vector databases and logs
	@echo "💾 Creating backup..."
	@mkdir -p backups
	@tar -czf backups/$(date +%Y%m%d_%H%M%S)_rag_backup.tar.gz data/ logs/ || echo "No data to backup"
	@echo "\n✅ Backup created!"

clean:  ## Clean up temporary files and caches
	@echo "🧹 Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type f -name ".coverage" -delete
	@find . -type f -name "coverage.xml" -delete
	@rm -rf htmlcov/ .pytest_cache/ .mypy_cache/ || true
	@docker image prune -f 2>/dev/null || true
	@echo "\n✅ Cleanup complete!"

clean-all: clean  ## Clean up everything including dependencies
	@echo "🧽 Deep cleaning..."
	@pip uninstall -r requirements.txt -y || true
	@pip freeze | xargs pip uninstall -y || true
	@docker system prune -f 2>/dev/null || true
	@echo "\n✅ Deep cleanup complete!"

## 📊 Information
info:  ## Show project information
	@echo "🤖 RAG Telegram Assistant Information"
	@echo "======================================"
	@echo ""
	@echo "📁 Project Structure:"
	@find ragbot/ -type d | sort | sed 's/^/  /'
	@echo ""
	@echo "📦 Dependencies:"
	@cat requirements.txt | wc -l
	@echo "  packages configured"
	@echo ""
	@echo "🧪 Test Coverage:"
	@if [ -f coverage.xml ]; then echo "  Coverage report available: htmlcov/index.html"; else echo "  Run 'make test-coverage' to generate"; fi
	@echo ""
	@echo "🐳 Docker:"
	@docker images | grep rag || echo "  Run 'make build' to create image"
	@echo ""

stats:  ## Show project statistics
	@echo "📊 RAG Telegram Assistant Statistics"
	@echo "===================================="
	@echo ""
	@echo "📄 Source code:"
	@find ragbot/ -name "*.py" -not -name "__init__.py" | wc -l
	@echo "  Python files"
	@example=""
	@for file in ragbot/*.py ; do if [[ $file == *main.py* ]] || [[ $file == *__init__.py* ]]; then continue; fi; example="$file"; break; done
	@if [ -n "$example" ]; then echo "  Example size: $$(cat $example | wc -l) LoC in main.py"; fi
	@echo ""
	@echo "🧪 Tests:"
	@find tests/ -name "*.py" | wc -l
	@echo "  Test files"
	@find tests/ -name "*.py" -exec wc -l {} \; | tail -1 | awk '{print $$1 " total lines of test code"}'

## 🔧 Utilities
create-env:  ## Create .env file from example
	@if [ ! -f .env ]; then cp .env.example .env && echo "✅ .env file created from .env.example"; else echo "⚠️  .env file already exists!"; fi

reset-db:  ## Reset vector databases and clear cache
	@echo "🔄 Resetting databases..."
	@rm -rf data/
	@rm -rf .pytest_cache/
	mkdir -p data/faiss_index
	@echo "\n✅ Database reset complete!"

update-deps:  ## Update all dependencies to latest versions
	@echo "🔄 Updating dependencies..."
	@pip install --upgrade pip
	@pip install -r requirements.txt --upgrade
	@echo "\n✅ Dependencies updated!"

## 🎯 Default Target
all: setup test lint  ## Run setup, tests and linting
