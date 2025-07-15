# n8n Community – Debian + Playwright
FROM n8nio/n8n:latest-ubuntu

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends wget jq bc tzdata \
 && npx --yes playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*

USER node
EXPOSE 5678
