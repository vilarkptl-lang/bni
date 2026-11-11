"""Añade al túnel existente una ruta HTTP para el MCP estado_navegador,
con DNS y Access (solo service token). Identificadores por entorno.

Requiere: CF_MAC_WHATSAPP_SETUP_TOKEN, CF_ACCOUNT_ID, CF_ZONE_ID, CF_TUNNEL_ID,
AGE_RECIPIENT, SECRET_DIR, MCP_WA_HOST. El primer argumento es un respaldo
JSON de la configuración previa del túnel (no se toca si cambió).
"""
import cfapi, json, os, subprocess, sys, copy

A = os.environ["CF_ACCOUNT_ID"]
Z = os.environ["CF_ZONE_ID"]
TID = os.environ["CF_TUNNEL_ID"]
H = os.environ["MCP_WA_HOST"]
SVC = os.environ.get("MCP_WA_SERVICE", "http://localhost:8765")
RCPT = os.environ["AGE_RECIPIENT"]
SECRET_PATH = os.path.join(os.environ.get("SECRET_DIR", "./secrets"), "cf-mcp-wa-service-token.age")
ST = os.environ.get("STATE_MCP_JSON", "mcp-wa-recursos.json")
os.makedirs(os.path.dirname(SECRET_PATH) or ".", exist_ok=True)
BACKUP = sys.argv[1] if len(sys.argv) > 1 else None
if not BACKUP:
    sys.exit("uso: setup_mcp_wa.py <respaldo-ingress.json>")

state = json.load(open(ST)) if os.path.exists(ST) else {}

def save():
    json.dump(state, open(ST, "w"), indent=1)

def ok(r, what):
    if not r.get("success"):
        print("FAIL", what, r.get("errors"))
        save()
        sys.exit(1)
    return r["result"]

def seal(plain, path):
    old = os.umask(0o077)
    try:
        subprocess.run([os.environ.get("AGE_BIN", "age"), "-r", RCPT, "-o", path],
                       input=plain.encode(), check=True)
    finally:
        os.umask(old)
    os.chmod(path, 0o600)

state.setdefault("host", H)
state.setdefault("tunnel_id", TID)
state.setdefault("backup_ingress", BACKUP)

TOKEN_NAME = os.environ.get("CF_MCP_TOKEN_NAME", "mcp-wa-service-token")
if "service_token_id" not in state:
    s = ok(cfapi.req("POST", f"/accounts/{A}/access/service_tokens",
                     {"name": TOKEN_NAME, "duration": "2160h"}), "service token")
    state["service_token_id"] = s["id"]
    state["service_token_expires"] = s.get("expires_at")
    save()
    seal(f"CLIENT_ID={s['client_id']}\nCLIENT_SECRET={s['client_secret']}\n", SECRET_PATH)
    del s
    state["secret_path"] = SECRET_PATH
    save()
    print("service token sealed")

if "policy_id" not in state:
    p = ok(cfapi.req("POST", f"/accounts/{A}/access/policies", {
        "name": TOKEN_NAME + " only",
        "decision": "non_identity",
        "include": [{"service_token": {"token_id": state["service_token_id"]}}],
    }), "policy")
    state["policy_id"] = p["id"]
    save()
print("policy ok")

if "app_id" not in state:
    a = ok(cfapi.req("POST", f"/accounts/{A}/access/apps", {
        "name": os.environ.get("CF_MCP_APP_NAME", "MCP estado_navegador (solo service token)"),
        "type": "self_hosted", "domain": H,
        "destinations": [{"type": "public", "uri": H}],
        "session_duration": "24h", "app_launcher_visible": False,
        "policies": [{"id": state["policy_id"], "precedence": 1}],
    }), "app")
    state["app_id"] = a["id"]
    save()
print("app ok")

if "dns_record_id" not in state:
    d = ok(cfapi.req("POST", f"/zones/{Z}/dns_records", {
        "type": "CNAME", "name": H, "content": f"{TID}.cfargotunnel.com",
        "proxied": True, "comment": "MCP estado_navegador, tras Access service token",
    }), "dns")
    state["dns_record_id"] = d["id"]
    save()
print("dns ok")

if "tunnel_version_after" not in state:
    old = json.load(open(BACKUP))["result"]
    cur = ok(cfapi.req("GET", f"/accounts/{A}/cfd_tunnel/{TID}/configurations"), "get cfg")
    if cur["config"] != old["config"] or cur.get("version") != old.get("version"):
        print("FAIL config cambió desde el respaldo; no toco")
        save()
        sys.exit(1)
    cfg = copy.deepcopy(old["config"])
    ing = cfg["ingress"]
    assert "hostname" not in ing[-1] and not any(r.get("hostname") == H for r in ing)
    ing.insert(len(ing) - 1, {"hostname": H, "service": SVC})
    state["tunnel_version_before"] = old.get("version")
    save()
    r = ok(cfapi.req("PUT", f"/accounts/{A}/cfd_tunnel/{TID}/configurations", {"config": cfg}), "put cfg")
    state["tunnel_version_after"] = r.get("version")
    save()

new = ok(cfapi.req("GET", f"/accounts/{A}/cfd_tunnel/{TID}/configurations"), "reget")
old = json.load(open(BACKUP))["result"]["config"]
prev = [r for r in old["ingress"]]
now = new["config"]["ingress"]
nowprev = [r for r in now if r.get("hostname") != H]
print("rutas previas idénticas:", nowprev == prev,
      "| warp-routing igual:", new["config"].get("warp-routing") == old.get("warp-routing"))
