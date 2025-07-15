# 🛠️ Naosite-Leads — MVP Loire-Atlantique

Pipeline automatisé pour détecter les entreprises sans site web, enrichir leurs coordonnées via DropContact, puis les importer dans Zoho CRM et Facebook CAPI.

## Fonctionnement
1. **Scraping** Google Maps avec Playwright + proxy Webshare, orchestré par n8n.
2. **Filtrage** des fiches sans lien « Site Web ».
3. **Enrichissement** avec DropContact (`siren:true`).
4. **Intégration** dans Zoho CRM et une audience Facebook.
5. **Sauvegarde** des données brutes sur un stockage S3 (Scaleway, Backblaze B2, etc.).

## Déploiement sur Fly.io
```bash
# 1. Cloner le dépôt
git clone [https://github.com/votre-organisation/naosite-leads.git](https://github.com/votre-organisation/naosite-leads.git)
cd naosite-leads

# 2. Renseigner les secrets sur Fly.io (exemple partiel)
fly secrets set PROXY_PASS="votre_mdp" DROP_TOKEN="votre_token" N8N_ENCRYPTION_KEY="votre_cle_de_32_caracteres" ...

# 3. Mettre en production
git push origin main
