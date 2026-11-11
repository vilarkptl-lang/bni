import os, json, urllib.request, urllib.error
BASE="https://api.cloudflare.com/client/v4"
def req(method, path, body=None):
    tok=os.environ["CF_MAC_WHATSAPP_SETUP_TOKEN"]
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(BASE+path, data=data, method=method,
        headers={"Authorization":"Bearer "+tok,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp: return json.load(resp)
    except urllib.error.HTTPError as e:
        try: return json.load(e)
        except Exception: return {"success":False,"errors":[{"message":f"HTTP {e.code}"}]}
