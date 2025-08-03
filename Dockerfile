# ----------------------------------------------------------
# n8n 1.102.4 · Debian Slim · Chrome + Python + Selenium - EMERGENCY FIX
# ----------------------------------------------------------
FROM node:20-slim
USER root

# -------------------------------
# Système + Python + Node tools + Chrome dependencies + DBUS FIX
# -------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        wget jq bc tzdata ca-certificates \
        python3 python3-pip python3-venv python3-full \
        gnupg unzip curl \
        xvfb \
        dbus dbus-x11 \
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

# Variables d'environnement optimisées
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROME_PATH=/usr/bin/google-chrome-stable
ENV DEBIAN_FRONTEND=noninteractive

# ============================================
# CORRECTION DBUS - CRITIQUE POUR LE DÉMARRAGE
# ============================================
RUN mkdir -p /etc/dbus-1 && \
    mkdir -p /usr/share/dbus-1 && \
    mkdir -p /var/run/dbus && \
    mkdir -p /run/dbus && \
    dbus-uuidgen > /etc/machine-id

# Créer le fichier de configuration dbus manquant
RUN echo '<!DOCTYPE busconfig PUBLIC \
    "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN" \
    "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd"> \
<busconfig> \
  <type>system</type> \
  <listen>unix:path=/var/run/dbus/system_bus_socket</listen> \
  <policy context="default"> \
    <allow user="*"/> \
    <allow own="*"/> \
    <allow send_type="method_call"/> \
    <allow send_type="signal"/> \
    <allow send_type="method_return"/> \
    <allow send_type="error"/> \
    <allow receive_type="method_call"/> \
    <allow receive_type="signal"/> \
    <allow receive_type="method_return"/> \
    <allow receive_type="error"/> \
  </policy> \
</busconfig>' > /usr/share/dbus-1/system.conf

# --------------------------------------------
# n8n (sans Playwright - on utilise Selenium)
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
# SCRIPT DE LANCEMENT CORRIGÉ - SANS DBUS DAEMON
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
# Nettoyer les processus existants\n\
echo "🧹 Cleaning existing processes..."\n\
pkill -f "Xvfb|chrome" 2>/dev/null || true\n\
sleep 1\n\
\n\
# Démarrer Xvfb (écran virtuel) SANS dbus\n\
echo "🖥️ Starting Xvfb virtual display..."\n\
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset -dpi 96 > /dev/null 2>&1 &\n\
sleep 3\n\
echo "✅ Xvfb started on display :99"\n\
\n\
# Test Chrome rapidement\n\
echo "🧪 Testing Chrome installation..."\n\
/usr/bin/google-chrome-stable --version || echo "⚠️ Chrome version check failed"\n\
\n\
# Test Chrome headless rapide\n\
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
if [ -f /work/scripts/website_finder.py ]; then\n\
    echo "✅ website_finder.py found"\n\
else\n\
    echo "❌ website_finder.py missing"\n\
fi\n\
\n\
# Démarrer n8n\n\
echo "🎯 Starting n8n..."\n\
exec n8n "$@"\n' > /usr/local/bin/start-n8n.sh && \
    chmod +x /usr/local/bin/start-n8n.sh

# Test final que tout fonctionne
RUN echo "Testing final setup..." && \
    /usr/bin/google-chrome-stable --version && \
    echo "Chrome test passed" && \
    python3 --version && \
    echo "Python test passed"

EXPOSE 5678
CMD ["/usr/local/bin/start-n8n.sh"]
