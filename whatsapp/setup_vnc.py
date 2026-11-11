"""Ensayo opcional de visor VNC por Access (IdP). Identificadores por entorno.
No incrusta correos, IDs de cuenta, túnel, zona ni IdP.

Requiere: CF_MAC_WHATSAPP_SETUP_TOKEN, CF_ACCOUNT_ID, CF_ZONE_ID, CF_TUNNEL_ID,
VNC_HOST, ACCESS_EMAIL, ACCESS_OTP_IDP_ID.
"""
import cfapi, json, os, sys

A = os.environ["CF_ACCOUNT_ID"]
Z = os.environ["CF_ZONE_ID"]
T = os.environ["CF_TUNNEL_ID"]
H = os.environ["VNC_HOST"]
EMAIL = os.environ["ACCESS_EMAIL"]
OTP = os.environ["ACCESS_OTP_IDP_ID"]
ST = os.environ.get("STATE_VNC_JSON", "state-vnc.json")
s = json.load(open(ST)) if os.path.exists(ST) else {}

def save():
    json.dump(s, open(ST, "w"), indent=1)

def ok(r, w):
    if not r.get("success"):
        print("FAIL", w, r.get("errors"))
        save()
        sys.exit(1)
    return r["result"]

cfg = ok(cfapi.req("GET", f"/accounts/{A}/cfd_tunnel/{T}/configurations"), "getcfg")["config"]
ing = cfg["ingress"]
if not any(i.get("hostname") == H for i in ing):
    new = [i for i in ing if i.get("hostname")] + [{"hostname": H, "service": "tcp://localhost:5900"}] + [i for i in ing if not i.get("hostname")]
    cfg["ingress"] = new
    ok(cfapi.req("PUT", f"/accounts/{A}/cfd_tunnel/{T}/configurations", {"config": cfg}), "putcfg")
print("ingress ok")

if "dns_id" not in s:
    ex = ok(cfapi.req("GET", f"/zones/{Z}/dns_records?name={H}"), "dnsget")
    if ex:
        print("DNS conflict")
        sys.exit(1)
    s["dns_id"] = ok(cfapi.req("POST", f"/zones/{Z}/dns_records", {
        "type": "CNAME", "name": H, "content": f"{T}.cfargotunnel.com",
        "proxied": True, "comment": "Ensayo VNC en el navegador, Access OTP",
    }), "dns")["id"]
    save()
print("dns ok")

if "policy_id" not in s:
    s["policy_id"] = ok(cfapi.req("POST", f"/accounts/{A}/access/policies", {
        "name": os.environ.get("VNC_POLICY_NAME", "vnc-test allow email"),
        "decision": "allow",
        "include": [{"email": {"email": EMAIL}}],
        "session_duration": "24h",
    }), "policy")["id"]
    save()
print("policy ok")

if "app_id" not in s:
    s["app_id"] = ok(cfapi.req("POST", f"/accounts/{A}/access/apps", {
        "name": os.environ.get("VNC_APP_NAME", "vnc-test (visor remoto)"),
        "type": "vnc", "domain": H, "session_duration": "24h",
        "allowed_idps": [OTP], "auto_redirect_to_identity": True,
        "app_launcher_visible": False,
        "policies": [{"id": s["policy_id"], "precedence": 1}],
    }), "app")["id"]
    save()
print("app ok")
