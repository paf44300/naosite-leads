# ----------------------------------------------------------
# n8n 1.102.4 · Debian Slim · Chrome + Python + Selenium
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
        dbus-x11 \
        fonts-liberation \
        fonts-noto-color-emoji \
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
        libgbm1 \
        libxss1 \
        libgconf-2-4 \
        xdg-utils; \
    ln -sf /usr/bin/python3 /usr/bin/python; \
    rm -rf /var/lib/apt/lists/*

# ----------------------------------------
# Installation de Google Chrome STABLE
# ----------------------------------------
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Variables d'environnement pour Chrome headless optimisées
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROME_PATH=/usr/bin/google-chrome-stable
ENV CHROME_DEVEL_SANDBOX=/usr/lib/chromium-browser/chrome-sandbox
ENV DEBIAN_FRONTEND=noninteractive

# --------------------------------------------
# n8n (sans Playwright car on utilise Selenium)
# --------------------------------------------
RUN npm install -g n8n@1.102.4

# ----------------------------------------------------
# Python libraries (SELENIUM + requests + beautifulsoup)
# ----------------------------------------------------
RUN pip install --break-system-packages \
    requests \
    beautifulsoup4 \
    selenium \
    undetected-chromedriver \
    lxml \
    urllib3 \
    webdriver-manager

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
# Configuration Chrome pour conteneur + Dbus
# -------------------------
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix && \
    mkdir -p /run/dbus && \
    mkdir -p /var/run/dbus

# Créer un utilisateur non-root pour Chrome (sécurité)
RUN groupadd -r chrome && useradd -r -g chrome -G audio,video chrome && \
    mkdir -p /home/chrome && chown -R chrome:chrome /home/chrome

# Configuration Dbus pour éviter les erreurs Chrome
RUN dbus-uuidgen > /etc/machine-id

# Script de lancement avec Xvfb + Dbus optimisé
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Nettoyer les processus existants\n\
pkill -f "Xvfb\|dbus\|chrome" 2>/dev/null || true\n\
sleep 1\n\
\n\
# Démarrer dbus\n\
if [ ! -f /var/run/dbus/pid ]; then\n\
    dbus-daemon --system --fork\n\
    sleep 1\n\
fi\n\
\n\
# Démarrer Xvfb (écran virtuel)\n\
if ! pgrep -x "Xvfb" > /dev/null; then\n\
    Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset -dpi 96 > /dev/null 2>&1 &\n\
    sleep 3\n\
    echo "Xvfb started on :99"\n\
fi\n\
\n\
# Test Chrome rapidement\n\
echo "Testing Chrome installation..."\n\
google-chrome-stable --version || echo "Chrome version check failed"\n\
\n\
# Vérifier que Chrome peut démarrer en mode headless\n\
timeout 10 google-chrome-stable --headless --no-sandbox --disable-gpu --dump-dom about:blank > /dev/null 2>&1 && \\\n\
    echo "✅ Chrome headless test passed" || \\\n\
    echo "⚠️ Chrome headless test failed"\n\
\n\
# Exécuter n8n\n\
echo "Starting n8n..."\n\
exec n8n "$@"\n' > /usr/local/bin/start-n8n.sh && \
    chmod +x /usr/local/bin/start-n8n.sh

# Test que Chrome fonctionne au build
RUN google-chrome-stable --version && \
    google-chrome-stable --headless --no-sandbox --disable-gpu --dump-dom about:blank > /dev/null 2>&1

EXPOSE 5678
CMD ["/usr/local/bin/start-n8n.sh"]
