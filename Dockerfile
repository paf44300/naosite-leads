# Node 20 + Debian slim
FROM node:20-slim                # ≈170 Mo

# Paquets système utiles
RUN apt-get update \
 && apt-get install -y --no-install-recommends wget jq bc tzdata ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# n8n + Playwright (package + navigateurs)
RUN npm install -g n8n@1.45.1 playwright@1.54.1 \
 && playwright install --with-deps chromium

# Fuseau horaire
RUN ln -sf /usr/share/zoneinfo/Europe/Paris /etc/localtime \
 && echo "Europe/Paris" > /etc/timezone

EXPOSE 5678
CMD ["n8n"]
