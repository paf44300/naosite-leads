FROM n8nio/n8n:1.45.1

USER root
RUN apk add --no-cache tzdata wget jq bc \
 && cp /usr/share/zoneinfo/Europe/Paris /etc/localtime \
 && echo "Europe/Paris" > /etc/timezone

USER node
RUN npx playwright install --with-deps chromium

EXPOSE 5678
