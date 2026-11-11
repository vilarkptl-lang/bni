"""Convierte el roster y los perfiles capturados (m_<id>.json o campos
en el roster) en members.json, listo para xl.py y los builders de cruces.

Los roles de liderazgo se leen de roles.json (o examples/roles.ejemplo.json).
El nombre del capítulo sale de BNI_CHAPTER o del roster; no hay excepciones
por miembro embebidas.
"""
import json, re, os
from pathlib import Path

DATA = Path(os.environ.get("BNI_DATA_DIR", "."))
ROOT = Path(__file__).resolve().parent
R = json.loads((DATA / "roster.json").read_text())

def load_roles():
    for p in (DATA / "roles.json", ROOT / "examples" / "roles.ejemplo.json"):
        if p.exists():
            return json.loads(p.read_text())
    return {}

ROLES = load_roles()

def lines(t):
    return [l.strip() for l in (t or "").split("\n") if l.strip()]

def between(L, starts, ends):
    out, on = [], False
    for l in L:
        if l in starts:
            on = True
            continue
        if on and l in ends:
            break
        if on:
            out.append(l)
    return out

def raw(m):
    try:
        d = json.loads((DATA / f"m_{m['memberId']}.json").read_text())
    except Exception:
        d = {}
    if "profile_main" in m:
        return m["profile_main"], m.get("horli_bio", ""), m.get("tops", ""), m.get("weekly_presentations", "")
    return d.get("main", ""), d.get("tab1", ""), d.get("tab3", ""), d.get("tab4", "")

STOP = {
    "Commercial 1", "Commercial 2", "Presentación semanal 1", "Presentación semanal 2",
    "Perfil TOPS", "Tops Profile", "Perfil HORLI", "GAINS Profile", "Commercial", "Presentaciones semanales",
}

def labeled(text, labels):
    res = {k: "" for k in labels.values()}
    cur, buf = None, []
    def flush():
        if cur:
            res[cur] = "\n".join(buf).strip()
    for l in (text or "").split("\n"):
        s = l.strip()
        if s.endswith(":") and s[:-1] in labels:
            flush()
            cur = labels[s[:-1]]
            buf = []
            continue
        if s in STOP or (s.endswith(":") and s[:-1] in STOP | {"Presentación Semanal 1", "Presentación Semanal 2"}):
            flush()
            cur, buf = None, []
            continue
        if cur:
            buf.append(l.rstrip())
    flush()
    return res

G = {
    "Goals": "goals", "Metas": "goals", "Accomplishments": "accomplishments", "Logros": "accomplishments",
    "Interests": "interests", "Intereses": "interests", "Networks": "networks", "Redes": "networks",
    "Skills": "skills", "Habilidades": "skills",
}
T = {
    "Ideal Referral": "ideal_referral", "Referancia Ideal": "ideal_referral", "Referencia Ideal": "ideal_referral",
    "Top Product": "top_product", "Producto Estrella": "top_product",
    "Top Problem Solved": "top_problem_solved", "El Problema Más Grande Que He Resuelto": "top_problem_solved",
    "My Favorite BNI Story": "favorite_bni_story", "Mi Anécdota Favorita De BNI": "favorite_bni_story",
    "My Ideal Referral Partner": "ideal_referral_partner", "Mi Socio De Referencias Ideal": "ideal_referral_partner",
}
Cmap = {"Commercial 1": "c1", "Commercial 2": "c2", "Presentación Semanal 1": "c1", "Presentación Semanal 2": "c2"}

def comm(text):
    out = {"c1": "", "c2": ""}
    cur, buf = None, []
    for l in (text or "").split("\n"):
        s = l.strip()
        if s.endswith(":") and s[:-1] in Cmap:
            if cur:
                out[cur] = "\n".join(buf).strip()
            cur = Cmap[s[:-1]]
            buf = []
            continue
        if s in STOP:
            if cur:
                out[cur] = "\n".join(buf).strip()
            cur, buf = None, []
            continue
        if cur:
            buf.append(s)
    if cur:
        out[cur] = "\n".join(buf).strip()
    return [v for v in out.values() if v]

def normphone(p):
    d = re.sub(r"\D", "", p)
    if len(d) == 13 and d[:3] in ("044", "045"):
        d = d[3:]
    if len(d) == 12 and d.startswith("52"):
        d = d[2:]
    return d if len(d) == 10 else None

isphone = lambda s: re.fullmatch(r"[+\d][\d\s\-]{6,}", s) is not None
out = []
for m in R:
    main, t1, t3, t4 = raw(m)
    L = lines(main)
    pers = [x for x in between(L, {"Personal Details", "Detalles Personales"}, {"My Bio", "Mi Biografía"}) if x != "Edit"]
    prof = [x for x in between(L, {"Professional Details", "Detalles Profesionales"},
                               {"Training History", "Historial de Capacitación", "Groups", "Grupos"}) if x != "Edit"]
    rawph = [m.get("phone_list", "")] + [x for x in pers + prof if isphone(x)]
    phones, bad = [], []
    for p in rawph:
        if not p:
            continue
        n = normphone(p)
        if n and n not in phones:
            phones.append(n)
        elif not n:
            digits = re.sub(r"\D", "", p)
            if digits not in bad:
                bad.append(digits)
    email = next((x for x in pers if "@" in x), "")
    web = next((x for x in pers if x.startswith("http") and "wa.me" not in x), "")
    wa = next((x for x in pers if "wa.me" in x), "")

    def after(lab):
        for i, x in enumerate(pers):
            if x in lab and i + 1 < len(pers):
                return pers[i + 1]
        return ""

    city = after({"City", "Ciudad de Orígen"})
    labs = {"City", "Ciudad de Orígen", "Zip / Postal Code", "Código Postal", "Country", "País"}
    addr = [x for x in pers if x not in labs and "@" not in x and not x.startswith("http") and not isphone(x)]
    addr = [x for x in addr if x not in (city, after({"Country", "País"}))]
    pt = [x for x in prof if not isphone(x) and x != "55"]
    ind = [s.strip() for s in pt[0].split(",")] if pt else []
    rest = pt[1:]
    desc = rest[0] if len(rest) > 0 else ""
    kw = rest[1] if len(rest) > 1 else ""
    company = rest[2] if len(rest) > 2 else m.get("company", "")
    g = labeled(t1 if "profile_main" not in m else t1, G)
    if not any(g.values()):
        g = labeled(t3, G)
    t = labeled(t3, T)
    for k, v in t.items():
        if v in ("", "-"):
            t[k] = ""
    name = re.sub(r"\s+", " ", m["name"]).strip()
    out.append({
        "memberId": m["memberId"],
        "name": name,
        "phones": phones,
        "phones_e164": ["+52" + p for p in phones],
        "phones_unparsed": bad,
        "whatsapp_link": wa,
        "email": email.lower() if email.isupper() else email,
        "company": company or m.get("company", ""),
        "industry": ind[0] if ind else "",
        "classification": m.get("profession", ""),
        "classification_detail": ", ".join(dict.fromkeys(ind[1:])),
        "website": web,
        "address": ", ".join(addr),
        "city": city,
        "keywords": kw,
        "business_description": desc,
        "gains": g,
        "tops": t,
        "commercials": comm(t4),
        "leadership_role": ROLES.get(name, ""),
    })

chapter = os.environ.get("BNI_CHAPTER") or (R[0].get("chapter") if R and isinstance(R[0], dict) and R[0].get("chapter") else "Capítulo")
payload = {
    "chapter": chapter,
    "region": os.environ.get("BNI_REGION", "Mexico"),
    "export_date": os.environ.get("BNI_EXPORT_DATE", ""),
    "member_count": len(out),
    "members": out,
}
(DATA / "members.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
missing_g = sum(1 for o in out if not any(o["gains"].values()))
missing_t = sum(1 for o in out if not any(o["tops"].values()))
print(json.dumps({
    "miembros": len(out),
    "con_telefono": sum(1 for o in out if o["phones"]),
    "con_correo": sum(1 for o in out if o["email"]),
    "sin_gains": missing_g,
    "sin_tops": missing_t,
    "con_rol": sum(1 for o in out if o["leadership_role"]),
}))
