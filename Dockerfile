# n8n Community (Alpine) + Playwright
FROM n8nio/n8n:1.45.1

# --- Paquets système + Playwright ---
USER root
RUN apk add --no-cache tzdata wget jq bc shadow  \
 && npx --yes playwright install --with-deps chromium \
 && cp /usr/share/zoneinfo/Europe/Paris /etc/localtime \
 && echo "Europe/Paris" > /etc/timezone

# --- Repasser à l’utilisateur node (n8n) ---
USER node
EXPOSE 5678
