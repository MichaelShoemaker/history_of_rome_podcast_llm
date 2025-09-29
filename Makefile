# History of Rome Podcast RAG System Makefile
# Simplifies Docker operations and system management

.PHONY: help build up down restart logs status clean install-deps pull-episodes transcribe health test

# Default target
.DEFAULT_GOAL := help

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)History of Rome RAG System$(NC)"
	@echo "$(YELLOW)Available commands:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ==============================================================================
# MAIN SYSTEM OPERATIONS
# ==============================================================================

build: ## Build all Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker compose build --no-cache

up: ## Start the complete RAG system
	@echo "$(BLUE)Starting History of Rome RAG system...$(NC)"
	@echo "$(YELLOW)This will start:$(NC)"
	@echo "  - Qdrant vector database (localhost:6333)"
	@echo "  - Ollama LLM service (localhost:11434)"
	@echo "  - Flask web interface (localhost:5000)"
	@echo "  - Transcript loader (one-time)"
	docker compose up -d
	@echo "$(GREEN)System starting...$(NC)"
	@echo "$(YELLOW)Web interface will be available at: http://localhost:5000$(NC)"
	@echo "$(YELLOW)Run 'make logs' to see startup progress$(NC)"

down: ## Stop and remove all containers
	@echo "$(BLUE)Stopping RAG system...$(NC)"
	docker compose down
	@echo "$(GREEN)System stopped$(NC)"

restart: ## Restart the entire system
	@echo "$(BLUE)Restarting RAG system...$(NC)"
	docker compose restart
	@echo "$(GREEN)System restarted$(NC)"

# ==============================================================================
# MONITORING AND DEBUGGING
# ==============================================================================

logs: ## Show logs from all services
	docker compose logs -f

logs-qdrant: ## Show Qdrant logs
	docker compose logs -f qdrant

logs-ollama: ## Show Ollama logs
	docker compose logs -f ollama

logs-flask: ## Show Flask app logs
	docker compose logs -f flask_app

logs-loader: ## Show transcript loader logs
	docker compose logs transcript_loader

status: ## Show status of all services
	@echo "$(BLUE)Service Status:$(NC)"
	@docker compose ps
	@echo ""
	@echo "$(BLUE)System Health:$(NC)"
	@curl -s http://localhost:5000/health | python3 -m json.tool 2>/dev/null || echo "$(RED)Flask app not responding$(NC)"

health: ## Check system health and connectivity
	@echo "$(BLUE)Checking system health...$(NC)"
	@echo ""
	@echo "$(YELLOW)Qdrant (Vector Database):$(NC)"
	@curl -s http://localhost:6333/health 2>/dev/null && echo "$(GREEN)✓ Qdrant is healthy$(NC)" || echo "$(RED)✗ Qdrant not responding$(NC)"
	@echo ""
	@echo "$(YELLOW)Ollama (LLM Service):$(NC)"
	@curl -s http://localhost:11434/api/tags 2>/dev/null >/dev/null && echo "$(GREEN)✓ Ollama is healthy$(NC)" || echo "$(RED)✗ Ollama not responding$(NC)"
	@echo ""
	@echo "$(YELLOW)Flask App (Web Interface):$(NC)"
	@curl -s http://localhost:5000/health 2>/dev/null >/dev/null && echo "$(GREEN)✓ Flask app is healthy$(NC)" || echo "$(RED)✗ Flask app not responding$(NC)"

# ==============================================================================
# DATA MANAGEMENT
# ==============================================================================

pull-episodes: ## Download podcast episodes (requires main venv)
	@echo "$(BLUE)Downloading podcast episodes...$(NC)"
	@echo "$(YELLOW)Note: This requires the main project dependencies$(NC)"
	@if [ ! -d "history_of_rome_episodes" ]; then \
		echo "$(YELLOW)Creating episodes directory...$(NC)"; \
		mkdir -p history_of_rome_episodes; \
	fi
	@python3 -c "import requests, beautifulsoup4" 2>/dev/null || (echo "$(RED)Missing dependencies. Run: pip install -r requirements-main.txt$(NC)" && exit 1)
	jupyter nbconvert --execute --to notebook pull_episodes.ipynb --ExecutePreprocessor.timeout=3600

transcribe: ## Transcribe episodes using CPU (requires main venv)
	@echo "$(BLUE)Transcribing episodes...$(NC)"
	@echo "$(YELLOW)Note: This may take several hours$(NC)"
	@python3 -c "import faster_whisper" 2>/dev/null || (echo "$(RED)Missing dependencies. Run: pip install -r requirements-main.txt$(NC)" && exit 1)
	jupyter nbconvert --execute --to notebook parse_episodes.ipynb --ExecutePreprocessor.timeout=36000

transcribe-gpu: ## Transcribe episodes using GPU (requires main venv)
	@echo "$(BLUE)Transcribing episodes with GPU...$(NC)"
	@echo "$(YELLOW)Note: Requires NVIDIA GPU and CUDA$(NC)"
	@python3 -c "import torch; assert torch.cuda.is_available()" || (echo "$(RED)CUDA not available$(NC)" && exit 1)
	python3 gpu_parser.py

reload-transcripts: ## Reload transcripts into Qdrant
	@echo "$(BLUE)Reloading transcripts...$(NC)"
	docker compose restart transcript_loader
	@echo "$(YELLOW)Check logs with: make logs-loader$(NC)"

# ==============================================================================
# DEVELOPMENT AND TESTING
# ==============================================================================

install-deps: ## Install Python dependencies for local development
	@echo "$(BLUE)Installing dependencies...$(NC)"
	@if [ ! -f "requirements-main.txt" ]; then \
		echo "$(RED)requirements-main.txt not found$(NC)"; \
		exit 1; \
	fi
	pip install -r requirements-main.txt
	@echo "$(GREEN)Dependencies installed$(NC)"

test: ## Test the RAG system with sample questions
	@echo "$(BLUE)Testing RAG system...$(NC)"
	@echo "$(YELLOW)Sending test questions to the API...$(NC)"
	@echo ""
	@echo "$(YELLOW)Test 1: Simple question$(NC)"
	@curl -s -X POST http://localhost:5000/api/ask \
		-H "Content-Type: application/json" \
		-d '{"question": "Who was Julius Caesar?", "context_limit": 3}' | \
		python3 -c "import sys, json; data=json.load(sys.stdin); print('Answer:', data.get('answer', 'No answer')[:200] + '...' if len(data.get('answer', '')) > 200 else data.get('answer', 'No answer'))" 2>/dev/null || echo "$(RED)API test failed$(NC)"

shell-qdrant: ## Open shell in Qdrant container
	docker compose exec qdrant sh

shell-ollama: ## Open shell in Ollama container
	docker compose exec ollama bash

shell-flask: ## Open shell in Flask container
	docker compose exec flask_app bash

# ==============================================================================
# CLEANUP AND MAINTENANCE
# ==============================================================================

clean: ## Stop containers and remove volumes (DESTRUCTIVE)
	@echo "$(RED)WARNING: This will delete all data including downloaded models$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to cancel, or wait 5 seconds to continue...$(NC)"
	@sleep 5
	docker compose down -v
	docker system prune -f
	@echo "$(GREEN)Cleanup complete$(NC)"

clean-containers: ## Remove containers but keep volumes
	@echo "$(BLUE)Removing containers (keeping data)...$(NC)"
	docker compose down
	docker compose rm -f
	@echo "$(GREEN)Containers removed$(NC)"

clean-images: ## Remove built images
	@echo "$(BLUE)Removing built images...$(NC)"
	docker rmi history_of_rome_podcast_llm_transcript_loader history_of_rome_podcast_llm_flask_app 2>/dev/null || true
	@echo "$(GREEN)Images removed$(NC)"

# ==============================================================================
# SHORTCUTS AND ALIASES
# ==============================================================================

start: up ## Alias for 'up'

stop: down ## Alias for 'down'

web: ## Open web interface in browser
	@echo "$(BLUE)Opening web interface...$(NC)"
	@python3 -c "import webbrowser; webbrowser.open('http://localhost:5000')" 2>/dev/null || echo "$(YELLOW)Open http://localhost:5000 in your browser$(NC)"

# ==============================================================================
# INFORMATION
# ==============================================================================

info: ## Show system information
	@echo "$(BLUE)History of Rome RAG System Information$(NC)"
	@echo ""
	@echo "$(YELLOW)Services:$(NC)"
	@echo "  Web Interface: http://localhost:5000"
	@echo "  Qdrant API:    http://localhost:6333"
	@echo "  Ollama API:    http://localhost:11434"
	@echo ""
	@echo "$(YELLOW)Data Directories:$(NC)"
	@echo "  Episodes:      ./history_of_rome_episodes/"
	@echo "  Transcripts:   ./all_transcripts/"
	@echo ""
	@echo "$(YELLOW)Docker Volumes:$(NC)"
	@docker volume ls | grep history || echo "  No volumes found"
	@echo ""
	@echo "$(YELLOW)Useful Commands:$(NC)"
	@echo "  make up        - Start the system"
	@echo "  make down      - Stop the system"
	@echo "  make logs      - View all logs"
	@echo "  make health    - Check system health"
	@echo "  make test      - Test the RAG system"

ports: ## Show which ports are in use
	@echo "$(BLUE)Port Usage:$(NC)"
	@echo "  5000: Flask Web Interface"
	@echo "  6333: Qdrant HTTP API"
	@echo "  6334: Qdrant gRPC API"
	@echo "  11434: Ollama API"
	@echo ""
	@echo "$(YELLOW)Checking if ports are available:$(NC)"
	@for port in 5000 6333 6334 11434; do \
		if netstat -tuln 2>/dev/null | grep -q ":$$port "; then \
			echo "  $$port: $(RED)In use$(NC)"; \
		else \
			echo "  $$port: $(GREEN)Available$(NC)"; \
		fi; \
	done 2>/dev/null || echo "  $(YELLOW)Install netstat to check port usage$(NC)"
