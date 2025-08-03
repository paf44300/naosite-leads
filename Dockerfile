# ----------------------------------------------------------
# n8n 1.102.4 · Debian Slim · Chrome + Python + Selenium - VERSION CORRIGÉE
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

# Variables d'environnement critiques
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROME_PATH=/usr/bin/google-chrome-stable
ENV DEBIAN_FRONTEND=noninteractive

# ============================================
# VARIABLES N8N CRITIQUES POUR FLY.IO
# ============================================
ENV N8N_HOST=0.0.0.0
ENV N8N_PORT=5678
ENV N8N_PROTOCOL=http
ENV WEBHOOK_URL=http://0.0.0.0:5678/
ENV N8N_EDITOR_BASE_URL=https://naosite-leads-mdvmcg.fly.dev

# Variables de performance
ENV NODE_OPTIONS="--max-old-space-size=1024"
ENV N8N_LOG_LEVEL=info
ENV DB_TYPE=sqlite
ENV EXECUTIONS_MODE=regular

# --------------------------------------------
# n8n installation avec configuration réseau
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
# Configuration Chrome + X11
# -------------------------
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix

# ===============================================
# SCRIPT DE LANCEMENT CORRIGÉ POUR FLY.IO
# ===============================================
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "🚀 Starting Naosite n8n container..."\n\
\n\
# Variables d'\''environnement pour Chrome\n\
export DISPLAY=:99\n\
export CHROME_BIN=/usr/bin/google-chrome-stable\n\
export CHROME_PATH=/usr/bin/google-chrome-stable\n\
\n\
# Variables n8n pour Fly.io\n\
export N8N_HOST=0.0.0.0\n\
export N8N_PORT=5678\n\
export N8N_PROTOCOL=http\n\
export WEBHOOK_URL=http://0.0.0.0:5678/\n\
\n\
# Nettoyer les processus existants\n\
echo "🧹 Cleaning existing processes..."\n\
pkill -f "Xvfb|chrome|n8n" 2>/dev/null || true\n\
sleep 2\n\
\n\
# Créer répertoire n8n avec permissions\n\
mkdir -p /root/.n8n\n\
chmod 755 /root/.n8n\n\
\n\
# Démarrer Xvfb (écran virtuel)\n\
echo "🖥️ Starting Xvfb virtual display..."\n\
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset -dpi 96 > /dev/null 2>&1 &\n\
XVFB_PID=$!\n\
sleep 3\n\
\n\
# Vérifier Xvfb\n\
if ps -p $XVFB_PID > /dev/null; then\n\
    echo "✅ Xvfb started successfully on display :99"\n\
else\n\
    echo "⚠️ Xvfb may have failed to start"\n\
fi\n\
\n\
# Test Chrome rapidement\n\
echo "🧪 Testing Chrome installation..."\n\
timeout 10 /usr/bin/google-chrome-stable --version 2>/dev/null || echo "⚠️ Chrome version check failed"\n\
\n\
# Test Chrome headless rapide (non bloquant)\n\
echo "🧪 Testing Chrome headless mode..."\n\
timeout 15 /usr/bin/google-chrome-stable \\\n\
    --headless=new \\\n\
    --no-sandbox \\\n\
    --disable-gpu \\\n\
    --disable-dev-shm-usage \\\n\
    --disable-web-security \\\n\
    --dump-dom about:blank > /dev/null 2>&1 && \\\n\
    echo "✅ Chrome headless test PASSED" || \\\n\
    echo "⚠️ Chrome headless test failed (continuing anyway)"\n\
\n\
# Vérifier que les scripts Python sont présents\n\
echo "🐍 Checking Python scripts..."\n\
for script in website_finder.py maps_scraper.py pj_scraper.py; do\n\
    if [ -f "/work/scripts/$script" ]; then\n\
        echo "✅ $script found"\n\
    else\n\
        echo "❌ $script missing"\n\
    fi\n\
done\n\
\n\
# Configuration réseau n8n pour Fly.io\n\
echo "🌐 Configuring n8n network settings..."\n\
echo "Host: ${N8N_HOST}:${N8N_PORT}"\n\
echo "Webhook URL: ${WEBHOOK_URL}"\n\
\n\
# Démarrer n8n avec configuration réseau explicite\n\
echo "🎯 Starting n8n..."\n\
echo "Listening on: ${N8N_HOST}:${N8N_PORT}"\n\
\n\
# Exec n8n avec toutes les variables d'\''environnement\n\
exec n8n start \\\n\
    --host="$N8N_HOST" \\\n\
    --port="$N8N_PORT" \\\n\
    --protocol="$N8N_PROTOCOL"\n' > /usr/local/bin/start-n8n.sh && \
    chmod +x /usr/local/bin/start-n8n.sh

# Configuration finale des permissions
RUN chmod -R 755 /work && \
    mkdir -p /root/.n8n && \
    chmod 755 /root/.n8n

# Test final que tout fonctionne
RUN echo "Testing final setup..." && \
    /usr/bin/google-chrome-stable --version && \
    echo "Chrome test passed" && \
    python3 --version && \
    echo "Python test passed" && \
    n8n --version && \
    echo "n8n test passed"

# Expose le port avec configuration explicite
EXPOSE 5678

# Configuration finale n8n
ENV N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=false

# Commande de démarrage
CMD ["/usr/local/bin/start-n8n.sh"]
