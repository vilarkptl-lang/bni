"""Empaca una copia saneada del tablero (fixtures ficticios, sin datos vivos).

No modifica el árbol de producción. Los identificadores y teléfonos reales
se detectan con patrones genéricos; este script no contiene una lista de
personas ni números.
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
src_root = Path(os.environ.get("BNI_TABLERO_SRC", HERE / "tableros"))
stage = Path(os.environ.get("BNI_PACK_STAGE", "/tmp/bni-tablero-saneado"))

if not src_root.exists():
    sys.exit(f"no existe {src_root}")
if stage.exists():
    shutil.rmtree(stage)
stage.mkdir()

# Los fixtures ya deben ser ficticios en tableros/. Solo se copian fuentes.
keep = [
    ".gitignore", "README.md", "package.json", "wrangler.toml",
    "comentarios.sh", "seguimientos.sh", "set-webhook.sh",
    "src/worker.js", "src/seguimientos-lib.js",
    "tests/seguimientos.test.js",
    "public/index.html",
    "fixtures/data.json", "fixtures/borradores-seguimiento.json",
    "docs/seguimientos.md", "bni-board-ui.js",
]
for rel in keep:
    src = src_root / rel
    if not src.exists():
        print("aviso: falta", rel)
        continue
    dest = stage / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    if rel.endswith(".sh"):
        os.chmod(dest, 0o755)

# Patrones genéricos: no listar PII real.
PATTERNS = [
    (r"(?i)\b[A-Z0-9._%+\-]+@(?!example\.com)[A-Z0-9.\-]+\.[A-Z]{2,}\b", "correo no ejemplo"),
    (r"\+52\s*1?\s*\d{2}\s*\d{4}\s*\d{4}", "telefono +52 no ficticio (0000)"),
    (r"(?<!\d)(?:55|81|33|22|66)\d{8}(?!\d)", "posible telefono MX de 10 dígitos"),
    (r"(?i)-----BEGIN ", "bloque PEM"),
    (r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]+['\"]", "secreto incrustado"),
    (r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{12,}", "bearer token"),
    (r"(?i)\.secure-vault", "ruta de bóveda"),
]

def looks_fictitious_phone(s):
    digits = re.sub(r"\D", "", s)
    return digits.startswith("550000") or digits.endswith("0000") or "0000" in digits

hits = []
for path in stage.rglob("*"):
    if not path.is_file():
        continue
    text = path.read_text(errors="replace")
    for pat, label in PATTERNS:
        for m in re.finditer(pat, text):
            if "telefono" in label and looks_fictitious_phone(m.group(0)):
                continue
            # wrangler y helpers mencionan el dominio público del Worker; no es un secreto
            if label == "correo no ejemplo" and m.group(0).endswith("@local"):
                continue
            hits.append((str(path.relative_to(stage)), label))

if hits:
    print("SCAN HITS:")
    for rel, label in hits:
        print(f"  {rel}: {label}")
    sys.exit("escaneo falló; no se empaqueta")

print("escaneo ok;", sum(1 for p in stage.rglob('*') if p.is_file()), "archivos")
if (stage / "tests/seguimientos.test.js").exists():
    r = subprocess.run(["node", "--test", "tests/seguimientos.test.js"],
                       cwd=stage, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if r.returncode != 0:
        sys.exit("pruebas fallaron; no se empaqueta")
print("ok")
