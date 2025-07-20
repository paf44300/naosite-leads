# ----------------------------------------------------------
# n8n 1.102.4 · Debian Slim · Playwright Chromium + Python
# ----------------------------------------------------------
FROM node:20-slim

USER root

# 1) Paquets système + Python + n8n + Playwright
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        wget jq bc tzdata ca-certificates \
        python3 python3-pip python3-venv; \
    ln -sf /usr/bin/python3 /usr/bin/python; \
    npm install -g n8n@1.102.4 playwright@1.54.1; \
    playwright install --with-deps chromium; \
    rm -rf /var/lib/apt/lists/*

# 2) Dossier scripts (assure qu’il existe toujours)
RUN mkdir -p /work/scripts
COPY scrapers/ /work/scripts/
RUN chmod +x /work/scripts/*.py

# 3) Fuseau horaire
RUN ln -sf /usr/share/zoneinfo/Europe/Paris /etc/localtime \
 && echo "Europe/Paris" > /etc/timezone

EXPOSE 5678
CMD ["n8n"]
