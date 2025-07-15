# Dockerfile final et corrigé

# Utilise l'image basée sur Debian, compatible avec Playwright
FROM n8nio/n8n:1.45.1

ENV TZ=Europe/Paris
ENV DEBIAN_FRONTEND=noninteractive

# Passe en root pour les installations
USER root

# Installe les dépendances avec apt-get (pour Debian)
RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata wget jq bc && \
    rm -rf /var/lib/apt/lists/*

# Installe Playwright et ses dépendances (fonctionnera car l'OS est supporté)
RUN npx playwright install --with-deps chromium

# Revient à l'utilisateur non-privilégié pour la sécurité
USER node
WORKDIR /home/node

EXPOSE 5678
