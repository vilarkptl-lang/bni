"""Primera versión del Excel de cruces WhatsApp × capítulo.

Las listas de cruces, visitantes y excluidos NO van embebidas.
Se leen de cruces_manual.json (o examples/cruces_manual.ejemplo.json).
Los contactos y miembros se leen de wa_personal_contacts.json y members.json
(en BNI_DATA_DIR o el directorio de trabajo). Esos archivos no se versionan.
"""
import json, os
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("BNI_DATA_DIR", "."))

def load_manual():
    for p in (DATA / "cruces_manual.json", ROOT / "examples" / "cruces_manual.ejemplo.json"):
        if p.exists():
            return json.loads(p.read_text())
    raise SystemExit("Falta cruces_manual.json (copia examples/cruces_manual.ejemplo.json)")

C = json.loads((DATA / "wa_personal_contacts.json").read_text())
M = {m["name"]: m for m in json.loads((DATA / "members.json").read_text())["members"]}

def mm(k):
    return next(m for n, m in M.items() if n.startswith(k))

manual = load_manual()
rows = []
for item in manual.get("cruces", []):
    c = C[item["wa_index"]]
    m = mm(item["miembro_prefijo"])
    rows.append(dict(
        contacto=c["name"],
        telefono=c.get("phone", ""),
        dedica=c.get("work_profile", ""),
        miembro=m["name"],
        giro=m["classification"] + ((" – " + m["company"]) if m.get("company") else ""),
        tel_miembro=(m["phones"][0] if m.get("phones") else ""),
        direccion=item["direccion"],
        calidad=item["calidad"],
        por_que=item["por_que"],
    ))
rows.sort(key=lambda r: -r["calidad"])

bni = {int(k): v for k, v in manual.get("miembros_bni_en_whatsapp", {}).items()}
vis = {int(k): v for k, v in manual.get("visitantes", {}).items()}
exc = {int(k): v for k, v in manual.get("excluidos", {}).items()}

wb = Workbook()
H = Font(bold=True, color="FFFFFF")
F = PatternFill("solid", fgColor="1F4E78")

def sheet(ws, head, data, widths):
    ws.append(head)
    [ws.append(r) for r in data]
    for c in ws[1]:
        c.font = H
        c.fill = F
    for r in ws.iter_rows():
        for c in r:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, w_ in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w_

ws = wb.active
ws.title = "Cruces"
sheet(
    ws,
    ["Contacto WhatsApp", "Teléfono", "A qué se dedica", "Miembro BNI", "Giro del miembro",
     "Teléfono del miembro", "Dirección (prospecto para el miembro / socio de referencia)",
     "Calidad 1-5", "Por qué"],
    [list(r.values()) for r in rows],
    [26, 18, 45, 28, 32, 15, 26, 10, 60],
)

def st(i):
    if i in bni:
        return "Miembro BNI: " + bni[i]
    if i in vis:
        return "Visitante potencial"
    if i in exc:
        return "Excluido: " + exc[i]
    return ""

sheet(
    wb.create_sheet("Contactos"),
    ["Contacto", "Teléfono", "Relación", "A qué se dedica", "Necesita/ofrece", "Estatus", "# cruces"],
    [[c["name"], c.get("phone", ""), c.get("relationship", ""), c.get("work_profile", ""),
      c.get("needs_or_offers", ""), st(i), sum(r["contacto"] == c["name"] for r in rows)]
     for i, c in enumerate(C)],
    [28, 18, 32, 50, 45, 35, 9],
)
sheet(
    wb.create_sheet("Visitantes"),
    ["Contacto", "Teléfono", "A qué se dedica", "Motivo"],
    [[C[i]["name"], C[i].get("phone", ""), C[i].get("work_profile", ""), v] for i, v in vis.items()],
    [28, 18, 45, 60],
)
sheet(
    wb.create_sheet("Excluidos"),
    ["Contacto", "Teléfono", "A qué se dedica", "Motivo de exclusión"],
    [[C[i]["name"], C[i].get("phone", ""), C[i].get("work_profile", ""), v] for i, v in exc.items()],
    [30, 18, 50, 45],
)

out = DATA / "Cruces_BNI_WhatsApp.xlsx"
wb.save(out)
payload = dict(
    cruces=rows,
    miembros_bni_en_whatsapp={C[i]["name"]: v for i, v in bni.items()},
    visitantes={C[i]["name"]: v for i, v in vis.items()},
    excluidos={C[i]["name"]: v for i, v in exc.items()},
)
(DATA / "cruces.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
wbook = load_workbook(out)
print(wbook.sheetnames, [wbook[s].max_row - 1 for s in wbook.sheetnames])
