#!/usr/bin/env bash
set -eo pipefail

if [[ -z "$1" ]]; then
  echo "Usage: $0 <NEW_PROXY_PASSWORD>"; exit 1
fi
NEW_PWD="$1"
ROT_USER="USR-FR-rotate"

echo "⏳ Vérification de la bande passante Webshare…"
USED_GB=$(curl -s -u "$PROXY_USER:$PROXY_PASS" \
  "[https://proxy.webshare.io/api/v2/proxy/usage/](https://proxy.webshare.io/api/v2/proxy/usage/)" | jq -r '.bandwidth_used_gb')

[[ -z "$USED_GB" ]] && { echo "❌ Impossible de récupérer l’usage"; exit 1; }

if (( $(echo "$USED_GB >= 1" | bc -l) )); then
  echo "⚡ Quota gratuit épuisé : bascule sur le proxy Rotating Residential"
  fly secrets set PROXY_SERVER="[http://p.webshare.io:80](http://p.webshare.io:80)" \
                 PROXY_USER="$ROT_USER" \
                 PROXY_PASS="$NEW_PWD"
  echo "✅ Secrets mis à jour ; redéploiement nécessaire."
else
  echo "👍 Usage $USED_GB GB < 1 GB : rien à faire."
fi
