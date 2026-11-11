"""Arma el Excel de miembros del capítulo a partir de members.json.

Los cargos de la hoja Resumen se toman de leadership_role en cada miembro
(o de roles.json). La fecha y el nombre del archivo salen del propio JSON
o de variables de entorno; no hay nombres de persona embebidos.
"""
import json, os, re
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as L

DATA = Path(os.environ.get("BNI_DATA_DIR", "."))
ROOT = Path(__file__).resolve().parent
D = json.loads((DATA / "members.json").read_text())
M = D["members"]

roles = {}
for p in (DATA / "roles.json", ROOT.parent / "lectura-capitulo" / "examples" / "roles.ejemplo.json"):
    if p.exists():
        roles = json.loads(p.read_text())
        break

wb = Workbook()
ws = wb.active
ws.title = "Miembros"
H = [
    ("Nombre", 26), ("Teléfono", 16), ("Correo", 30), ("Empresa", 26), ("Giro", 28),
    ("Ciudad", 16), ("Sitio web", 28), ("Palabras clave", 40), ("Descripción", 60),
    ("Referencia ideal", 50), ("Producto estrella", 40), ("Problema que resuelve", 50),
    ("Socio de referencia ideal", 40), ("Metas", 45), ("Intereses", 35), ("Redes", 40),
    ("Habilidades", 40), ("Rol en el capítulo", 18),
]
ws.append([h for h, _ in H])
for m in M:
    g, t = m.get("gains", {}), m.get("tops", {})
    ws.append([
        m.get("name", ""), "\n".join(m.get("phones") or []), m.get("email", ""),
        m.get("company", ""), m.get("classification", ""), m.get("city", ""),
        m.get("website", ""), m.get("keywords", ""), m.get("business_description", ""),
        t.get("ideal_referral", ""), t.get("top_product", ""), t.get("top_problem_solved", ""),
        t.get("ideal_referral_partner", ""), g.get("goals", ""), g.get("interests", ""),
        g.get("networks", ""), g.get("skills", ""), m.get("leadership_role") or roles.get(m.get("name", ""), ""),
    ])
for i, (h, width) in enumerate(H, 1):
    ws.column_dimensions[L(i)].width = width
for row in ws.iter_rows():
    for c in row:
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if isinstance(c.value, str) and len(c.value) > 32000:
            c.value = c.value[:32000]
for c in ws[1]:
    c.font = Font(bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor="C8102E")
ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions

r = wb.create_sheet("Resumen")
r.append(("Capítulo", D.get("chapter", "")))
r.append(("Región", D.get("region", "")))
r.append(("Número de miembros", len(M)))
r.append(("Fecha", D.get("export_date") or os.environ.get("BNI_EXPORT_DATE", "")))
for m in M:
    rol = m.get("leadership_role") or ""
    if rol:
        r.append((rol, m.get("name", "")))
for c in r["A"]:
    c.font = Font(bold=True)
r.column_dimensions["A"].width = 22
r.column_dimensions["B"].width = 40

slug = re.sub(r"[^A-Za-z0-9_-]+", "_", D.get("chapter") or "Capitulo").strip("_") or "Capitulo"
out = DATA / os.environ.get("BNI_CAPITULO_XLSX", f"BNI_{slug}.xlsx")
wb.save(out)
wbook = load_workbook(out)
print(wbook.sheetnames, wbook["Miembros"].max_row - 1, str(out))
