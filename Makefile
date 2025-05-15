# ----------------------------------------------------------------------------
# 🧼 Linting & Formatting
# ----------------------------------------------------------------------------

.PHONY: format lint clean

format:
	@echo "🔧 Running autoflake..."
	autoflake --remove-unused-variables --remove-all-unused-imports -ri .
	@echo "📦 Running isort..."
	isort .
	@echo "🎨 Running black..."
	black .

lint:
	@echo "🔎 Running flake8..."
	flake8 .

clean:
	@echo "🧹 Cleaning __pycache__ and .pyc files..."
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
<<<<<<< HEAD

# ----------------------------------------------------------------------------
# Development
# ----------------------------------------------------------------------------
.PHONY: dev

dev:
	@echo "🔄 Starting dev server..."

	poetry run uvicorn src.mastercard_solution_tech_stack_agent.main:app \
		--host 0.0.0.0 --port 8000 \
		# --reload \
		# --reload-dir src/mastercard_solution_tech_stack_agent \
		# --reload-exclude .venv

# -----
# Docker
# ---

# Build the docker image
docker-build:
	@echo "🐳 Builidng docker image..."
	@docker build -t herbehordeun/mastercard_solution_tech_stack_agent:latest .

# Run the app in Docker
run-docker:
	@echo "🐳 Starting full dev stack using Docker Compose..."
	@docker compose up -d

# Check if all required environment variables are set
check-env:
	@echo "🔍 Checking environment configuration..."
	@poetry run python -c "from config import settings; print('✅ .env validation passed.')"
=======
>>>>>>> 010a15f (auto-commit)
