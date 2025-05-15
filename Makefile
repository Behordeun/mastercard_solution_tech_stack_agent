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

# ----------------------------------------------------------------------------
# Development
# ----------------------------------------------------------------------------
.PHONY: dev

dev:
	@echo "🔄 Starting dev server..."

	poetry run uvicorn src.mastercard_solution_tech_stack_agent.main:app \
		--host 0.0.0.0 --port 8000 \
		--reload \
		--reload-dir $(pwd)/src/mastercard_solution_tech_stack_agent \
		--reload-exclude .venv
