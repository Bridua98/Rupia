.PHONY: install dev test lint migrate build bootstrap

install:
	uv sync
	npm install

dev:
	npm run dev

build:
	npm run build

migrate:
	uv run python manage.py migrate

bootstrap:
	uv run python manage.py migrate
	uv run python manage.py ensure_superuser

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
