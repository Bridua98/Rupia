.PHONY: install dev test lint migrate build

install:
	uv sync
	npm install

dev:
	npm run dev

build:
	npm run build

migrate:
	uv run python manage.py migrate

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
