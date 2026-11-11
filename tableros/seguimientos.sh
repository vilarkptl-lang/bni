#!/usr/bin/env bash
# Seguimientos en bni.vilarkptl.com. No envía WhatsApp. Uso:
#   seguimientos.sh listar [id_propuesta]
#   seguimientos.sh agregar <id_propuesta> <id_miembro> "texto" [id] [miembro] [contacto]
#   seguimientos.sh cargar <archivo.json>   (casos[].id_propuesta + borrador; id_miembro se cruza con data.json)
#   seguimientos.sh aprobaciones
# Append-only e idempotente: el mismo id o el mismo texto en una propuesta no se reescribe.
set -euo pipefail
BASE=https://bni.vilarkptl.com
K=$(cat "${BNI_COMMENTS_KEY_FILE:?falta BNI_COMMENTS_KEY_FILE}")
c(){ curl -fsS -H "x-admin-key: $K" "$@"; }
DIR=$(cd "$(dirname "$0")" && pwd)
case "${1:-}" in
  listar)
    q="${2:+?id_propuesta=$2}"
    c "$BASE/api/admin/seguimientos$q" | jq -r '.[]|"\(.created_at) · \(.id) · \(.miembro) → \(.contacto) · \(.id_propuesta)\n  \(.texto)\n"'
    ;;
  agregar)
    [ $# -ge 4 ] || { echo "uso: $0 agregar <id_propuesta> <id_miembro> \"texto\" [id] [miembro] [contacto]"; exit 2; }
    body=$(jq -n --arg p "$2" --arg m "$3" --arg t "$4" --arg id "${5:-}" --arg mi "${6:-}" --arg co "${7:-}" \
      '{id_propuesta:$p,id_miembro:$m,texto:$t}+(if $id!="" then {id:$id} else {} end)+(if $mi!="" then {miembro:$mi} else {} end)+(if $co!="" then {contacto:$co} else {} end)')
    c -X POST -H content-type:application/json "$BASE/api/admin/seguimientos" --data "$body" | jq -c '{id,id_propuesta,texto}'
    ;;
  cargar)
    [ $# -ge 2 ] || { echo "uso: $0 cargar <archivo.json>"; exit 2; }
    python3 - "${BNI_DATA_JSON:-$DIR/fixtures/data.json}" "$2" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
drafts = json.load(open(sys.argv[2]))
idx = {}
for m in data:
    for p in m.get("props") or []:
        idx[p["pid"]] = {"id_miembro": m["mid"], "miembro": m["miembro"], "contacto": p["contacto"]}
rows = []
for c in drafts["casos"]:
    i = idx[c["id_propuesta"]]
    rows.append({
        "id": "seg-20261110-" + c["id_propuesta"],
        "id_propuesta": c["id_propuesta"],
        "id_miembro": i["id_miembro"],
        "miembro": i["miembro"],
        "contacto": i["contacto"],
        "texto": c["borrador"],
    })
json.dump(rows, open("/tmp/seg-cargar.json", "w"), ensure_ascii=False)
print(len(rows), "borradores listos", file=sys.stderr)
PY
    jq -c '.[]' /tmp/seg-cargar.json | while read -r row; do
      c -X POST -H content-type:application/json "$BASE/api/admin/seguimientos" --data "$row" | jq -c '{id,id_propuesta,texto}'
    done
    ;;
  aprobaciones)
    c "$BASE/api/admin/aprobaciones-seguimiento" | jq -r '.[]|"\(.estado) · \(.miembro) → \(.contacto) · \(.id_propuesta) · \(.updated_at)"'
    ;;
  *) sed -n '2,8p' "$0"; exit 2 ;;
esac
