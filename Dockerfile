# ----------------------------------------------------------
# n8n 1.102.4 · Debian Slim · Playwright Chromium + Python + Selenium
# ----------------------------------------------------------
FROM node:20-slim
USER root

# -------------------------------
# Système + Python + Node tools + Chrome dependencies
# -------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        wget jq bc tzdata ca-certificates \
        python3 python3-pip python3-venv python3-full \
        gnupg unzip curl \
        xvfb \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libdrm2 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        xdg-utils; \
    ln -sf /usr/bin/python3 /usr/bin/python; \
    rm -rf /var/lib/apt/lists/*

# ----------------------------------------
# Installation de Google Chrome (pour Selenium)
# ----------------------------------------
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Variables d'environnement pour Chrome headless
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/bin/google-chrome

# --------------------------------------------
# n8n + Playwright (Node.js version + browser)
# --------------------------------------------
RUN npm install -g n8n@1.102.4 playwright@1.54.1 && \
    npx playwright install --with-deps chromium

# ----------------------------------------------------
# Python libraries (Playwright, Requests, BeautifulSoup + SELENIUM)
# ----------------------------------------------------
RUN pip install --break-system-packages \
    playwright \
    requests \
    beautifulsoup4 \
    selenium \
    undetected-chromedriver \
    lxml \
    urllib3

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

# -------------------------
# Configuration Chrome pour conteneur
# -------------------------
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix

# Script de lancement avec Xvfb
RUN echo '#!/bin/bash\n\
# Démarrer Xvfb (écran virtuel) en arrière-plan si pas déjà démarré\n\
if ! pgrep -x "Xvfb" > /dev/null; then\n\
    Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset > /dev/null 2>&1 &\n\
    sleep 2\n\
fi\n\
\n\
# Exécuter n8n\n\
exec n8n "$@"\n' > /usr/local/bin/start-n8n.sh && \
    chmod +x /usr/local/bin/start-n8n.sh

EXPOSE 5678
CMD ["/usr/local/bin/start-n8n.sh"]
