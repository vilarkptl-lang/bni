#!/usr/bin/env bash
# Comentarios del usuario en bni.vilarkptl.com. Uso:
#   comentarios.sh pendientes | todos
#   comentarios.sh responder <id> "texto"   (guarda respuesta y marca atendido; visible en el tablero)
#   comentarios.sh atender <id>             (marca atendido sin respuesta)
#   comentarios.sh aprobaciones [aprobada|rechazada]
set -euo pipefail
BASE=https://bni.vilarkptl.com
K=$(cat "${BNI_COMMENTS_KEY_FILE:?falta BNI_COMMENTS_KEY_FILE}")
c(){ curl -fsS -H "x-admin-key: $K" "$@"; }
case "${1:-}" in
  pendientes) c "$BASE/api/admin/comments?estado=pendiente" | jq -r '.[]|"#\(.id) [\(.created_at)] \(.email)\n  \(.miembro)\(if .contacto then " → "+.contacto else " (miembro)" end) · m=\(.id_miembro) p=\(.id_propuesta)\n  > \(.texto)\n"' ;;
  todos) c "$BASE/api/admin/comments?estado=todos" | jq . ;;
  responder) [ $# -ge 3 ] || { echo "uso: $0 responder <id> \"texto\""; exit 2; }
    c -X POST -H content-type:application/json "$BASE/api/admin/comments/$2/responder" --data "$(jq -n --arg r "$3" '{respuesta:$r}')" | jq -c '{id,status,respuesta}' ;;
  atender) [ $# -ge 2 ] || { echo "uso: $0 atender <id>"; exit 2; }
    c -X POST -H content-type:application/json "$BASE/api/admin/comments/$2/atender" -d '{}' | jq -c '{id,status}' ;;
  aprobaciones) c "$BASE/api/admin/aprobaciones${2:+?estado=$2}" | jq -r '.[]|"\(.estado) · \(.miembro) → \(.contacto) · \(.id_propuesta) · \(.email) · \(.updated_at)"' ;;
  *) sed -n '2,7p' "$0"; exit 2 ;;
esac
