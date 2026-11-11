"""Builder actual de cruces: conserva los previos, agrega los nuevos,
arma pasteles y la pestaña de Prospectos, y limpia datos sensibles en perfiles.

Las listas nuevas (X) y de prospectos (L) se leen de JSON externos, no van embebidas.
"""
import json, re, collections, os
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.chart import PieChart, Reference

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("BNI_DATA_DIR", "."))

def load_named(*names):
    for name in names:
        for p in (DATA / name, ROOT / "examples" / name.replace(".json", ".ejemplo.json")):
            if p.exists():
                return json.loads(p.read_text())
    raise SystemExit(f"Falta {' o '.join(names)}")

C = json.loads((DATA / "wa_personal_contacts.json").read_text())
for c in C:
    for k in ("relationship", "work_profile", "needs_or_offers"):
        c[k] = re.sub(r'\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6,}\b|\b\d{8,}\b', '[omitido]', c.get(k) or '')
    for k in ("relationship", "work_profile", "needs_or_offers"):
        c[k] = re.sub(r"[^;]*FIEL[^;]*", "[trámite SAT omitido]", c[k])
N = {c["name"]: c for c in C}
M = json.loads((DATA / "members.json").read_text())["members"]

def mm(k):
    return next(m for m in M if m["name"].startswith(k))

prev_path = DATA / "cruces_prev.json"
prev = json.loads(prev_path.read_text()) if prev_path.exists() else {
    "cruces": [], "excluidos": {}, "miembros_bni_en_whatsapp": {}, "visitantes": {}
}

nuevos = load_named("cruces_manual_nuevos.json")
prospectos = load_named("prospectos_vilar.json")

rows = []
for r in prev.get("cruces", []):
    r = dict(r)
    r["origen"] = "Previo"
    rows.append(r)
seen = {(r["contacto"], r["miembro"]) for r in rows}
for item in nuevos.get("cruces", []):
    n = item["contacto"]
    c = N[n]
    m = mm(item["miembro_prefijo"])
    if (n, m["name"]) in seen:
        continue
    rows.append(dict(
        contacto=n,
        telefono=c.get("phone", ""),
        dedica=c.get("work_profile", ""),
        miembro=m["name"],
        giro=m["classification"] + ((" – " + m["company"]) if m.get("company") else ""),
        tel_miembro=(m["phones"][0] if m.get("phones") else ""),
        direccion=item["direccion"],
        calidad=item["calidad"],
        por_que=item["por_que"],
        origen="Nuevo",
    ))
rows.sort(key=lambda r: -r["calidad"])

def bucket(c):
    s = (c.get("relationship", "") + " " + c.get("work_profile", "")).lower()
    for k, v in [
        ("bni", "Miembro BNI"), ("family", "Familia"), ("famil", "Familia"),
        ("client", "Cliente"), ("loan", "Prospecto crédito"), ("prospect", "Prospecto"),
        ("tenant", "Arrendatario"), ("broker", "Aliado de negocio"),
        ("business", "Aliado de negocio"), ("professional", "Aliado de negocio"),
        ("credit", "Aliado de negocio"), ("real estate", "Inmobiliario"),
        ("accountant", "Contador"), ("vendor", "Proveedor"), ("supplier", "Proveedor"),
        ("service", "Proveedor"), ("driver", "Proveedor"), ("friend", "Amigo/personal"),
        ("personal", "Amigo/personal"), ("hockey", "Amigo/personal"), ("staff", "Staff"),
    ]:
        if k in s:
            return v
    return "Sin información"

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

def pie(ws, title, counter, anchor_col):
    base = ws.max_row + 2 if ws.max_row > 1 else 1
    ws.cell(base, anchor_col, title).font = Font(bold=True)
    items = counter.most_common()
    for j, (k, v) in enumerate(items, 1):
        ws.cell(base + j, anchor_col, k)
        ws.cell(base + j, anchor_col + 1, v)
    ch = PieChart()
    ch.title = title
    ch.height = 9
    ch.width = 14
    ch.add_data(Reference(ws, min_col=anchor_col + 1, min_row=base + 1, max_row=base + len(items)))
    ch.set_categories(Reference(ws, min_col=anchor_col, min_row=base + 1, max_row=base + len(items)))
    ws.add_chart(ch, ws.cell(base, anchor_col + 3).coordinate)
    for _ in range(max(0, 19 - len(items))):
        ws.append([])

wb = Workbook()
ws = wb.active
ws.title = "Cruces"
sheet(
    ws,
    ["Contacto WhatsApp", "Teléfono", "A qué se dedica", "Miembro BNI", "Giro del miembro",
     "Teléfono del miembro", "Dirección", "Calidad 1-5", "Por qué", "Origen"],
    [[r[k] for k in ["contacto", "telefono", "dedica", "miembro", "giro", "tel_miembro",
                     "direccion", "calidad", "por_que", "origen"]] for r in rows],
    [26, 18, 45, 28, 32, 15, 24, 10, 60, 10],
)
cnt = collections.Counter(r["contacto"] for r in rows)
L = [(p["contacto"], p["prioridad"], p["necesidad"]) for p in prospectos.get("prospectos", [])]
sheet(
    wb.create_sheet("Prospectos"),
    ["Contacto", "Teléfono", "Prioridad 1-5", "Necesidad (según chat)", "Último mensaje"],
    [[n, N[n].get("phone", ""), p, w_, N[n].get("last_message_date", "")] for n, p, w_ in sorted(L, key=lambda x: -x[1])],
    [28, 18, 10, 60, 16],
)
ex = prev.get("excluidos", {})
bm = prev.get("miembros_bni_en_whatsapp", {})
vi = prev.get("visitantes", {})

def st(n):
    if n in bm:
        return "Miembro BNI: " + bm[n]
    if n in vi:
        return "Visitante potencial"
    if n in ex:
        return "Excluido: " + ex[n]
    return ""

sheet(
    wb.create_sheet("Contactos"),
    ["Contacto", "Teléfono", "Relación", "Categoría", "A qué se dedica", "Necesita/ofrece",
     "Último mensaje", "Estatus", "# cruces"],
    [[c["name"], c.get("phone", ""), c.get("relationship", ""), bucket(c), c.get("work_profile", ""),
      c.get("needs_or_offers", ""), c.get("last_message_date", ""), st(c["name"]), cnt.get(c["name"], 0)]
     for c in C],
    [28, 18, 30, 18, 45, 45, 14, 30, 9],
)
sheet(wb.create_sheet("Visitantes"), ["Contacto", "Teléfono", "Motivo"],
      [[n, N[n].get("phone", ""), v] for n, v in vi.items() if n in N], [28, 18, 60])
sheet(wb.create_sheet("Excluidos"), ["Contacto", "Teléfono", "Motivo"],
      [[n, N.get(n, {}).get("phone", ""), v] for n, v in ex.items()], [30, 18, 50])
g = wb.create_sheet("Pasteles")
pie(g, "Cruces por miembro BNI", collections.Counter(r["miembro"] for r in rows), 1)
pie(g, "Cruces por dirección", collections.Counter(r["direccion"] for r in rows), 1)
pie(g, "Cruces por calidad", collections.Counter(str(r["calidad"]) for r in rows), 1)
pie(g, "Contactos WhatsApp por categoría de relación", collections.Counter(bucket(c) for c in C), 1)
g.column_dimensions["A"].width = 40
out = DATA / "Cruces_BNI_WhatsApp.xlsx"
wb.save(out)
(DATA / "cruces.json").write_text(json.dumps(dict(
    cruces=rows,
    prospectos=[dict(contacto=n, prioridad=p, necesidad=w_) for n, p, w_ in L],
    miembros_bni_en_whatsapp=bm, visitantes=vi, excluidos=ex,
), ensure_ascii=False, indent=1))

cap = DATA / os.environ.get("BNI_CAPITULO_XLSX", "BNI_Capitulo.xlsx")
if cap.exists():
    wbook = load_workbook(cap)
    if "Pasteles" in wbook.sheetnames:
        del wbook["Pasteles"]
    g = wbook.create_sheet("Pasteles")
    pie(g, "Miembros por industria", collections.Counter(m.get("industry") or "Sin dato" for m in M), 1)
    pie(g, "Cruces WhatsApp por miembro", collections.Counter(r["miembro"] for r in rows), 1)
    g.column_dimensions["A"].width = 40
    wbook.save(cap)
print(len(rows), collections.Counter(r["origen"] for r in rows), collections.Counter(bucket(c) for c in C))
