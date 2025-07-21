# ----------------------------------------------------------
# n8n 1.102.4 · Debian Slim · Playwright Chromium + Python
# ----------------------------------------------------------
FROM node:20-slim
USER root

# Paquets + n8n + Playwright + Python
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        wget jq bc tzdata ca-certificates \
        python3 python3-pip python3-venv; \
    ln -sf /usr/bin/python3 /usr/bin/python; \
    npm install -g n8n@1.102.4 playwright@1.54.1; \
    playwright install --with-deps chromium; \
    pip install playwright; \
    playwright install --with-deps; \
    rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------------------------------
# Copie les scrapers (==> assure-toi que le dossier existe dans le dépôt git)
# ----------------------------------------------------------------------------
RUN mkdir -p /work/scripts
COPY scripts/ /work/scripts/         
RUN chmod +x /work/scripts/*.py

RUN ln -sf /usr/share/zoneinfo/Europe/Paris /etc/localtime \
 && echo "Europe/Paris" > /etc/timezone

EXPOSE 5678
CMD ["n8n"]
