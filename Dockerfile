# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=1.7.1

# Install system dependencies
# Install system dependencies with safer mirror replacement
RUN sed -i 's|http://deb.debian.org|http://deb.debian.org|g' /etc/apt/sources.list.d/* \
    && apt-get update \
    && apt-get install -y --no-install-recommends --fix-missing \
       curl build-essential gcc libffi-dev libssl-dev git ca-certificates gnupg2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Set working directory
WORKDIR /app

# Copy only pyproject files first to leverage Docker layer caching
COPY pyproject.toml poetry.lock ./

# Configure Poetry to not use virtual environments
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY src /app/src
COPY .env /app/.env

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI using Uvicorn via Poetry
CMD ["poetry", "run", "uvicorn", "mastercard_solution_tech_stack_agent.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "src", "--app-dir", "src/mastercard_solution_tech_stack_agent"]