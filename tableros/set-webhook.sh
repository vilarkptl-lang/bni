#!/usr/bin/env bash
# Configura NOTIFY_URL y NOTIFY_KEY del Worker desde variables de entorno.
# No imprime valores. Requiere:
#   BNI_WEBHOOK_URL, BNI_WEBHOOK_KEY, CF_TABLERO_TOKEN, CLOUDFLARE_ACCOUNT_ID
set -euo pipefail
: "${BNI_WEBHOOK_URL:?falta BNI_WEBHOOK_URL}"
: "${BNI_WEBHOOK_KEY:?falta BNI_WEBHOOK_KEY}"
: "${CF_TABLERO_TOKEN:?falta CF_TABLERO_TOKEN}"
: "${CLOUDFLARE_ACCOUNT_ID:?falta CLOUDFLARE_ACCOUNT_ID}"
DIR=$(cd "$(dirname "$0")" && pwd)
cd "$DIR"
export CLOUDFLARE_API_TOKEN="$CF_TABLERO_TOKEN"
printf "%s" "$BNI_WEBHOOK_URL" | npx wrangler secret put NOTIFY_URL >/dev/null && echo "NOTIFY_URL listo"
printf "%s" "$BNI_WEBHOOK_KEY" | npx wrangler secret put NOTIFY_KEY >/dev/null && echo "NOTIFY_KEY listo"
