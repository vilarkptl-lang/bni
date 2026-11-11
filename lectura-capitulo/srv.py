"""Receptor local de perfiles del navegador (lectura del capítulo).

Escucha solo en 127.0.0.1 (por defecto el puerto 8765) y guarda cada perfil
en m_<id>.json dentro de BNI_DATA_DIR. No expone el servicio a la red.
"""
import http.server, urllib.parse, json, os
from pathlib import Path

DATA = Path(os.environ.get("BNI_DATA_DIR", "."))
HOST = os.environ.get("BNI_SRV_HOST", "127.0.0.1")
PORT = int(os.environ.get("BNI_SRV_PORT", "8765"))
DATA.mkdir(parents=True, exist_ok=True)

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        q = urllib.parse.urlparse(s.path).query
        d = urllib.parse.parse_qs(q).get("d")
        if d:
            o = json.loads(d[0])
            mid = o.get("id")
            if mid is None:
                s.send_response(400)
                s.end_headers()
                return
            f = DATA / f"m_{mid}.json"
            e = json.loads(f.read_text()) if f.exists() else {}
            e.update(o)
            f.write_text(json.dumps(e, ensure_ascii=False, indent=1))
        s.send_response(200)
        s.send_header("Content-Type", "text/html")
        s.send_header("Access-Control-Allow-Origin", "*")
        s.end_headers()
        s.wfile.write(b"ok")
    def log_message(*a):
        pass

http.server.ThreadingHTTPServer((HOST, PORT), H).serve_forever()
