# n8n Community (Alpine) + Playwright – installation faite en root
FROM n8nio/n8n:1.45.1

# --- Paquets système + Playwright ---
USER root
RUN apk add --no-cache tzdata wget jq bc shadow \
 && npm install -g --omit=dev playwright@1.54.1 \
 && playwright install --with-deps chromium \
 && cp /usr/share/zoneinfo/Europe/Paris /etc/localtime \
 && echo "Europe/Paris" > /etc/timezone

# --- Revenir à l’utilisateur non-privilégié ---
USER node
EXPOSE 5678
