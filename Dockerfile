# Image n8n + playwright + tzdata
# Utiliser une image n8n officielle comme base. Une version spécifique est recommandée.
FROM n8nio/n8n:latest

# Définir les variables d'environnement pour les installations non interactives et le fuseau horaire
ENV TZ=Europe/Paris
ENV DEBIAN_FRONTEND=noninteractive

# Passer root pour installer les paquets système
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata wget && \
    rm -rf /var/lib/apt/lists/*

# Revenir à l'utilisateur 'node' pour les opérations n8n et npm
USER node
WORKDIR /home/node

# Installer Playwright et les dépendances du navigateur (Chromium dans ce cas)
# --with-deps installe également les bibliothèques système nécessaires
RUN npx playwright install --with-deps chromium

# Exposer le port par défaut de n8n
EXPOSE 5678

# Le point d'entrée par défaut de l'image de base (CMD ["n8n"]) sera utilisé
