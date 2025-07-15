# ------------------------------------------------------------
# Naosite-Leads · Image n8n Community Edition (Alpine) + Playwright
# ------------------------------------------------------------
# - Base : n8nio/n8n:1.45.1 (Alpine)
# - Ajouts : tzdata, wget, jq, bc  +  Playwright (Chromium)
# - Taille finale ~100 Mo
# ------------------------------------------------------------

FROM n8nio/n8n:1.45.1       # Alpine par défaut

# --- Paquets système + fuseau horaire ---
USER root
RUN apk add --no-cache tzdata wget jq bc \
 && cp /usr/share/zoneinfo/Europe/Paris /etc/localtime \
 && echo "Europe/Paris" > /etc/timezone

# --- Installation Playwright + navigateurs ---
USER node
WORKDIR /home/node            # déjà dans l’image, mais on explicite
RUN npx playwright install --with-deps chromium

# --- Port exposé par n8n ---
EXPOSE 5678

# CMD par défaut = point-d’entrée n8n fourni par l’image de base
