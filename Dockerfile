# ----------------------------------------------------------
# n8n 1.45.1   ·   Debian Slim   ·   Playwright Chromium
# ----------------------------------------------------------
FROM node:20-slim

# --- paquets système + n8n + Playwright ---
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends wget jq bc tzdata ca-certificates \
 && npm install -g n8n@1.45.1 playwright@1.54.1 \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*

# Fuseau horaire
RUN ln -sf /usr/share/zoneinfo/Europe/Paris /etc/localtime \
 && echo "Europe/Paris" > /etc/timezone

EXPOSE 5678
CMD ["n8n"]
