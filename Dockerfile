# n8n + Playwright + utilitaires légers
FROM n8nio/n8n:1.45.1

ENV TZ=Europe/Paris
ENV DEBIAN_FRONTEND=noninteractive

USER root

# Installe les dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata wget jq bc && \
    rm -rf /var/lib/apt/lists/*

# Installe Playwright et ses navigateurs
RUN npx playwright install --with-deps chromium

USER node
WORKDIR /home/node

EXPOSE 5678
