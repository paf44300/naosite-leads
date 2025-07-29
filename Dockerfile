# ----------------------------------------------------------
# n8n 1.102.4 · Debian Slim · Playwright Chromium + Python
# ----------------------------------------------------------
FROM node:20-slim
USER root

# -------------------------------
# Système + Python + Node tools
# -------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        wget jq bc tzdata ca-certificates \
        python3 python3-pip python3-venv python3-full; \
    ln -sf /usr/bin/python3 /usr/bin/python; \
    rm -rf /var/lib/apt/lists/*

# --------------------------------------------
# n8n + Playwright (Node.js version + browser)
# --------------------------------------------
RUN npm install -g n8n@1.102.4 playwright@1.54.1 && \
    npx playwright install --with-deps chromium

# ----------------------------------------------------
# Python libraries (Playwright, Requests, BeautifulSoup)
# ----------------------------------------------------
RUN pip install --break-system-packages playwright requests beautifulsoup4

# ---------------------------------------
# Copie les scrapers Python dans /work
# ---------------------------------------
RUN mkdir -p /work/scripts
COPY scripts/ /work/scripts/
RUN chmod +x /work/scripts/*.py

# -------------------------
# Fuseau horaire : Paris
# -------------------------
RUN ln -sf /usr/share/zoneinfo/Europe/Paris /etc/localtime && \
    echo "Europe/Paris" > /etc/timezone

EXPOSE 5678
CMD ["n8n"]
