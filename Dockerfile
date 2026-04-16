FROM python:3.13-slim

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

# Install Python dependencies
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/local.txt

COPY . .

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
