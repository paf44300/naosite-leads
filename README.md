# Projet Naosite-Leads (MVP Loire-Atlantique)

Ce dépôt contient l'infrastructure en tant que code (IaC) pour un pipeline de génération de leads B2B entièrement automatisé.

## 🎯 Objectif

L'objectif est d'identifier les PME et indépendants du département de la Loire-Atlantique (44) qui n'ont pas de site web, d'enrichir leurs coordonnées (email + SIREN), et de les intégrer automatiquement dans un CRM (Zoho) ainsi qu'une audience publicitaire (Facebook).

## ⚙️ Architecture

Le projet est orchestré par **n8n** et déployé sur **Fly.io** via une pipeline CI/CD utilisant **GitHub Actions**.

- **Déclencheur** : Un CRON quotidien lance le workflow.
- **Scraping** : Un scraper **Playwright** interroge Google Maps via des proxys rotatifs français (**Webshare**) pour trouver des entreprises.
- **Filtrage** : Le workflow isole les entreprises n'ayant pas de site web.
- **Enrichissement** : **DropContact** est utilisé pour trouver les adresses e-mail professionnelles et les numéros SIREN.
- **Intégration** : Les leads qualifiés sont créés ou mis à jour dans **Zoho CRM** et synchronisés avec une audience **Facebook via CAPI**.
- **Sauvegarde** : Les données brutes sont archivées sur un stockage objet (S3/B2).

## 🚀 Déploiement

1.  **Cloner le dépôt** : `git clone https://github.com/your-username/naosite-leads.git`
2.  **Configurer Fly.io** : Créez une application sur Fly.io et configurez les secrets listés dans le `fly.toml` (ou le document de solution).
3.  **Configurer GitHub** : Ajoutez le secret `FLY_API_TOKEN` dans les paramètres du dépôt GitHub (`Settings > Secrets and variables > Actions`).
4.  **Déployer** : Poussez les modifications sur la branche `main` pour déclencher le déploiement automatique via GitHub Actions.

## 💻 Développement Local

Pour les tests en local, utilisez Docker Compose :

1.  Renommez `.env.example` en `.env` et remplissez les variables d'environnement.
2.  Lancez les conteneurs : `docker-compose up --build`
3.  L'interface n8n sera accessible à l'adresse `http://localhost:5678`.
