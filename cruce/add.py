import json, os, sys
from pathlib import Path

DATA = Path(os.environ.get("BNI_DATA_DIR", "."))
f = DATA / "wa_personal_contacts.json"
d = json.loads(f.read_text()) if f.exists() else []
new = json.loads(sys.stdin.read())
have = {x["name"] for x in d}
added = 0
for n in new:
    if n["name"] not in have:
        d.append(n)
        have.add(n["name"])
        added += 1
    # Si dos contactos se llaman igual, revisa también el teléfono antes de descartar.
f.write_text(json.dumps(d, ensure_ascii=False, indent=1))
print(json.dumps({"total": len(d), "agregados": added}))
