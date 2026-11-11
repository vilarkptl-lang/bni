#!/usr/bin/env bash
# Abre puentes locales (cloudflared access tcp) hacia los Chrome de WhatsApp
# que escuchan CDP solo en 127.0.0.1 de la máquina remota.
#   127.0.0.1:19222 -> $WA_HOST_PERSONAL -> remoto 127.0.0.1:9222
#   127.0.0.1:19223 -> $WA_HOST_VILAR    -> remoto 127.0.0.1:9223
# Uso: bash conectar.sh [start|stop|status]
# El token de servicio de Access se descifra solo en memoria; nunca se imprime.
set -euo pipefail
CF="${CLOUDFLARED:-$HOME/bin/cloudflared}"
KEY="${AGE_KEY_FILE:?falta AGE_KEY_FILE}"
SECRET="${ACCESS_SERVICE_TOKEN_AGE:?falta ACCESS_SERVICE_TOKEN_AGE}"
HOST_PERSONAL="${WA_HOST_PERSONAL:?falta WA_HOST_PERSONAL}"
HOST_VILAR="${WA_HOST_VILAR:?falta WA_HOST_VILAR}"
RUN="${WA_TUNNEL_RUNDIR:-/tmp/wa-tunnels}"
mkdir -p "$RUN"
chmod 700 "$RUN"

stop() {
  for p in "$RUN"/*.pid; do
    [ -f "$p" ] && kill "$(cat "$p")" 2>/dev/null || true
    rm -f "$p"
  done
  echo "Puentes detenidos."
}
status() {
  for pair in "personal:19222:$HOST_PERSONAL" "vilar:19223:$HOST_VILAR"; do
    IFS=: read -r n port _host <<<"$pair"
    if [ -f "$RUN/$n.pid" ] && kill -0 "$(cat "$RUN/$n.pid")" 2>/dev/null; then
      if curl -s -m 5 "http://127.0.0.1:$port/json/version" | grep -q Browser; then
        echo "$n: OK (CDP en 127.0.0.1:$port)"
      else
        echo "$n: puente arriba, Chrome remoto no responde"
      fi
    else
      echo "$n: apagado"
    fi
  done
}
start() {
  [ -f "$SECRET" ] || { echo "Falta el archivo AGE del token de servicio"; exit 1; }
  # Archivo cifrado con líneas: CLIENT_ID=... / CLIENT_SECRET=...
  local plain
  plain="$(age -d -i "$KEY" "$SECRET")"
  TUNNEL_SERVICE_TOKEN_ID="$(printf '%s
' "$plain" | sed -n 's/^CLIENT_ID=//p')"
  TUNNEL_SERVICE_TOKEN_SECRET="$(printf '%s
' "$plain" | sed -n 's/^CLIENT_SECRET=//p')"
  unset plain
  export TUNNEL_SERVICE_TOKEN_ID TUNNEL_SERVICE_TOKEN_SECRET
  declare -A HOSTS=([personal]="$HOST_PERSONAL" [vilar]="$HOST_VILAR")
  declare -A PORTS=([personal]=19222 [vilar]=19223)
  for n in personal vilar; do
    if [ -f "$RUN/$n.pid" ] && kill -0 "$(cat "$RUN/$n.pid")" 2>/dev/null; then
      echo "$n ya corre"
      continue
    fi
    nohup "$CF" access tcp --hostname "${HOSTS[$n]}" --url "127.0.0.1:${PORTS[$n]}" --loglevel warn       >"$RUN/$n.log" 2>&1 &
    echo $! > "$RUN/$n.pid"
  done
  unset TUNNEL_SERVICE_TOKEN_ID TUNNEL_SERVICE_TOKEN_SECRET
  sleep 3
  status
}
case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  *) echo "uso: $0 [start|stop|status]"; exit 2 ;;
esac
