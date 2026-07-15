FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Tailwind CSS standalone CLI (detect architecture)
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "arm64" ]; then TAILWIND_ARCH="linux-arm64"; else TAILWIND_ARCH="linux-x64"; fi && \
    curl -sLO "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-${TAILWIND_ARCH}" && \
    chmod +x "tailwindcss-${TAILWIND_ARCH}" && \
    mv "tailwindcss-${TAILWIND_ARCH}" /usr/local/bin/tailwindcss

COPY requirements/ requirements/

FROM base AS dev

RUN pip install --no-cache-dir -r requirements/local.txt

COPY . .

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]

FROM base AS prod

RUN pip install --no-cache-dir -r requirements/production.txt

COPY . .

# Dummy env satisfies python-decouple; collectstatic never touches the DB
RUN tailwindcss -i static/css/input.css -o static/css/output.css --minify && \
    SECRET_KEY=build-only \
    DATABASE_URL=postgres://build:build@localhost:5432/build \
    ALLOWED_HOSTS=build \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    python manage.py collectstatic --no-input --ignore="input.css"

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120"]
