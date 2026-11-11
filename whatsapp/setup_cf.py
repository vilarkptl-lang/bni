"""Crea (idempotente) el túnel, DNS y Access para exponer el CDP de los Chrome
de WhatsApp. Todos los identificadores salen de variables de entorno; nada va
embebido. El token del túnel y el service token se cifran con age y no se imprimen.

Requiere: CF_MAC_WHATSAPP_SETUP_TOKEN (vía cfapi), CF_ACCOUNT_ID, CF_ZONE_ID,
AGE_RECIPIENT, SECRET_DIR, WA_HOST_PERSONAL, WA_HOST_VILAR.
El estado (solo IDs de recursos) se guarda en STATE_CF_JSON (gitignorado).
"""
import cfapi, json, os, subprocess, sys

A = os.environ["CF_ACCOUNT_ID"]
Z = os.environ["CF_ZONE_ID"]
RCPT = os.environ["AGE_RECIPIENT"]
V = os.environ.get("SECRET_DIR", "./secrets")
ST = os.environ.get("STATE_CF_JSON", "state-cf.json")
os.makedirs(V, exist_ok=True)
HOSTS = {
    os.environ["WA_HOST_PERSONAL"]: "tcp://localhost:9222",
    os.environ["WA_HOST_VILAR"]: "tcp://localhost:9223",
}
TUNNEL_NAME = os.environ.get("CF_TUNNEL_NAME", "mac-whatsapp")
TOKEN_NAME = os.environ.get("CF_SERVICE_TOKEN_NAME", "mac-whatsapp")
APP_NAME = os.environ.get("CF_ACCESS_APP_NAME", "Mac WhatsApp CDP (solo service token)")

state = json.load(open(ST)) if os.path.exists(ST) else {}

def save():
    json.dump(state, open(ST, "w"), indent=1)

def ok(r, what):
    if not r.get("success"):
        print("FAIL", what, r.get("errors"))
        save()
        sys.exit(1)
    return r["result"]

def seal(plain: str, path):
    old = os.umask(0o077)
    try:
        subprocess.run(["age", "-r", RCPT, "-o", path], input=plain.encode(), check=True)
    finally:
        os.umask(old)
    os.chmod(path, 0o600)

if "tunnel_id" not in state:
    t = ok(cfapi.req("POST", f"/accounts/{A}/cfd_tunnel",
                     {"name": TUNNEL_NAME, "config_src": "cloudflare"}), "tunnel")
    state["tunnel_id"] = t["id"]
    save()
tid = state["tunnel_id"]
print("tunnel listo")
ok(cfapi.req("PUT", f"/accounts/{A}/cfd_tunnel/{tid}/configurations",
             {"config": {"ingress": [{"hostname": h, "service": s} for h, s in HOSTS.items()]
                         + [{"service": "http_status:404"}]}}), "config")
print("config ok")
tok = ok(cfapi.req("GET", f"/accounts/{A}/cfd_tunnel/{tid}/token"), "tunnel token")
seal(tok, os.path.join(V, "cf-mac-whatsapp-tunnel-token.age"))
del tok
print("tunnel token sealed")

for h in HOSTS:
    k = "dns_" + h
    if k not in state:
        d = ok(cfapi.req("POST", f"/zones/{Z}/dns_records", {
            "type": "CNAME", "name": h, "content": f"{tid}.cfargotunnel.com",
            "proxied": True, "comment": "Chrome WhatsApp CDP, tras Access service token",
        }), k)
        state[k] = d["id"]
        save()
    print("dns ok", h)

if "service_token_id" not in state:
    s = ok(cfapi.req("POST", f"/accounts/{A}/access/service_tokens",
                     {"name": TOKEN_NAME, "duration": "8760h"}), "service token")
    state["service_token_id"] = s["id"]
    state["service_token_expires"] = s.get("expires_at")
    save()
    seal(f"CLIENT_ID={s['client_id']}\nCLIENT_SECRET={s['client_secret']}\n",
         os.path.join(V, "cf-mac-whatsapp-service-token.age"))
    del s
    print("service token sealed")

if "policy_id" not in state:
    p = ok(cfapi.req("POST", f"/accounts/{A}/access/policies", {
        "name": TOKEN_NAME + " service token only",
        "decision": "non_identity",
        "include": [{"service_token": {"token_id": state["service_token_id"]}}],
    }), "policy")
    state["policy_id"] = p["id"]
    save()
print("policy ok")

if "app_id" not in state:
    hosts = list(HOSTS)
    a = ok(cfapi.req("POST", f"/accounts/{A}/access/apps", {
        "name": APP_NAME, "type": "self_hosted", "domain": hosts[0],
        "destinations": [{"type": "public", "uri": h} for h in hosts],
        "session_duration": "24h", "app_launcher_visible": False,
        "policies": [{"id": state["policy_id"], "precedence": 1}],
    }), "app")
    state["app_id"] = a["id"]
    save()
print("app ok")
