# syntax=docker/dockerfile:1

# ---- Stage 1: compile Tailwind CSS with the standalone CLI (no Node.js needed) ----
FROM debian:bookworm-slim AS css
ARG TAILWIND_VERSION=v4.3.3
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo arm64 || echo x64) \
    && curl -sSLo /usr/local/bin/tailwindcss \
       "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${ARCH}" \
    && chmod +x /usr/local/bin/tailwindcss
WORKDIR /app
COPY . .
RUN tailwindcss -i assets/tailwind.css -o static/css/app.css --minify

# ---- Stage 2: the Django application ----
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so Docker can cache this layer between code changes.
ARG REQUIREMENTS=requirements/base.txt
COPY requirements/ requirements/
RUN pip install -r ${REQUIREMENTS}

COPY . .
COPY --from=css /app/static/css/app.css static/css/app.css
# The Tailwind binary is kept so docker compose can rebuild CSS while you develop.
COPY --from=css /usr/local/bin/tailwindcss /usr/local/bin/tailwindcss

# collectstatic needs settings to import, but not a real secret or database.
RUN DJANGO_SETTINGS_MODULE=config.settings.prod SECRET_KEY=build-only \
    DATABASE_URL=sqlite:///tmp/build.db python manage.py collectstatic --noinput

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
