# ----------------------------------------------------------
# n8n 1.102.4   ·   Debian Slim   ·   Playwright Chromium
# + Python 3.12 (pip & venv)
# ----------------------------------------------------------
FROM node:20-slim

# --- paquets système + n8n + Playwright + Python ---
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        wget jq bc tzdata ca-certificates \
        python3 python3-pip python3-venv \
 && ln -s /usr/bin/python3 /usr/bin/python \        
 && npm install -g n8n@1.102.4 playwright@1.54.1 \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*

# Fuseau horaire
RUN ln -sf /usr/share/zoneinfo/Europe/Paris /etc/localtime \
 && echo "Europe/Paris" > /etc/timezone

EXPOSE 5678
CMD ["n8n"]
