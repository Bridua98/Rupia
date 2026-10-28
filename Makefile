.PHONY: install dev test lint migrate messages build

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

messages:
	uv run python manage.py makemessages -l es -l en -l de --ignore .venv --ignore node_modules
	uv run python manage.py compilemessages
