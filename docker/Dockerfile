FROM node:22-bookworm AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY babel.config.json ./
COPY ui ./ui
RUN npm run build

FROM python:3.10-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
COPY --from=assets /app/static/webpack_bundles ./static/webpack_bundles
ENV PATH="/app/.venv/bin:$PATH" \
    DJANGO_DEBUG=0
RUN DJANGO_SECRET_KEY=collectstatic-build-only DB_ENGINE=sqlite \
    python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "rupia.wsgi:application", "--bind", "0.0.0.0:8000"]
