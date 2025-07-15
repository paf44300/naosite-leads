#!/usr/bin/env bash
set -eo pipefail

# Ce script vérifie l'utilisation du proxy Webshare et bascule sur le plan rotatif
# si le quota gratuit est dépassé. Nécessite flyctl.

if [[ -z "$1" ]]; then
    echo "Usage: $0 <MOT_DE_PASSE_PROXY_ROTATIF>"
    exit 1
fi

NEW_PWD=$1
ROTATING_USER="USR-FR-rotate" # Selon la documentation

echo "Vérification de la bande passante utilisée pour l'utilisateur $PROXY_USER..."
USED_GB=$(curl -s -u "$PROXY_USER:$PROXY_PASS" \
  "https://proxy.webshare.io/api/v2/proxy/usage/" | jq -r '.bandwidth_used_gb')

if [[ -z "$USED_GB" ]]; then
  echo "Erreur : Impossible de récupérer l'usage de la bande passante."
  exit 1
fi

echo "Usage actuel : ${USED_GB} GB"

# Utilise 'bc' pour la comparaison de nombres à virgule flottante
if (( $(echo "$USED_GB >= 1" | bc -l) )); then
  echo "Quota du plan gratuit dépassé. Bascule vers le proxy rotatif..."
  flyctl secrets set \
    PROXY_SERVER="http://p.webshare.io:80" \
    PROXY_USER="${ROTATING_USER}" \
    PROXY_PASS="${NEW_PWD}"

  echo "Secrets mis à jour sur Fly.io. Un nouveau déploiement est nécessaire."
else
  echo "Bande passante dans les limites du plan gratuit. Aucune action."
fi
