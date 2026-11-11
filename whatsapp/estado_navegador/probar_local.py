#!/usr/bin/env python3
"""Prueba local de estado_navegador contra los Chrome ya abiertos en esta Mac.

Arranca el servidor MCP solo en 127.0.0.1, en un puerto efimero. Llama
initialize, tools/list y tools/call (personal y vilar) con http.client.
No sustituye puertos, no abre tunel, no usa CDP de pagina ni envia mensajes.
Cierra el servidor siempre, incluso si hay error.
"""
import http.client
import json
import re
import sys
import threading

import estado_mcp as m

CAMPOS = ("cuenta", "chrome_responde", "version_chrome",
          "pestanas_whatsapp", "detalle")


def rpc(puerto, metodo, params=None, ident=1):
    msg = {"jsonrpc": "2.0", "id": ident, "method": metodo}
    if params is not None:
        msg["params"] = params
    cuerpo = json.dumps(msg).encode("utf-8")
    c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=20)
    try:
        c.request("POST", "/mcp", body=cuerpo, headers={
            "Host": "127.0.0.1:%d" % puerto,
            "Content-Type": "application/json",
        })
        r = c.getresponse()
        crudo = r.read().decode("utf-8")
        return r.status, (json.loads(crudo) if crudo else None)
    finally:
        c.close()


def sanitizar(res):
    if not isinstance(res, dict):
        return {"error": "respuesta_inesperada"}
    out = {}
    for k in CAMPOS:
        if k not in res:
            continue
        v = res[k]
        if k == "cuenta":
            out[k] = v if v in ("personal", "vilar") else "?"
        elif k == "chrome_responde":
            out[k] = bool(v)
        elif k == "pestanas_whatsapp":
            out[k] = v if isinstance(v, int) and 0 <= v < 10000 else None
        elif k == "version_chrome":
            out[k] = re.sub(r"[\x00-\x1f]", "", str(v))[:80]
        elif k == "detalle":
            out[k] = re.sub(r"[^A-Za-z0-9_]", "", str(v))[:80]
    return out


def resultado_herramienta(respuesta):
    if not isinstance(respuesta, dict):
        return {"error": "respuesta_inesperada"}
    if "error" in respuesta:
        codigo = respuesta["error"].get("code") if isinstance(
            respuesta["error"], dict) else None
        return {"error": "rpc", "codigo": codigo}
    res = (respuesta.get("result") or {}).get("structuredContent")
    return sanitizar(res)


def correr():
    # Los puertos salen de estado_mcp.CUENTAS (9222 personal, 9223 vilar).
    # Este runner no los sustituye.
    m.SALIDA_LOG = open("/dev/null", "w")
    srv = m.crear_servidor(0)
    puerto = srv.server_address[1]
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    informe = {"mcp": "127.0.0.1:%d" % puerto, "ok": False}
    codigo_salida = 1
    try:
        s, r = rpc(puerto, "initialize",
                   {"protocolVersion": "2025-11-25",
                    "clientInfo": {"name": "probar-local", "version": "0.3"}})
        if s != 200 or not isinstance(r, dict) or "result" not in r:
            informe["error"] = "initialize"
            return 2, informe

        s, r = rpc(puerto, "tools/list")
        nombres = []
        if s == 200 and isinstance(r, dict):
            herramientas = (r.get("result") or {}).get("tools") or []
            if isinstance(herramientas, list):
                nombres = [t.get("name") for t in herramientas
                           if isinstance(t, dict)]
        informe["herramientas"] = nombres
        if nombres != ["estado_navegador"]:
            informe["error"] = "herramientas"
            return 2, informe

        for cuenta in ("personal", "vilar"):
            s, r = rpc(puerto, "tools/call",
                       {"name": "estado_navegador",
                        "arguments": {"cuenta": cuenta}})
            informe[cuenta] = (resultado_herramienta(r) if s == 200
                               else {"error": "http", "codigo": s})

        ambos = all(
            isinstance(informe.get(c), dict)
            and informe[c].get("chrome_responde") is True
            and informe[c].get("cuenta") == c
            for c in ("personal", "vilar")
        )
        informe["ok"] = ambos
        codigo_salida = 0 if ambos else 1
        return codigo_salida, informe
    finally:
        try:
            srv.shutdown()
        finally:
            srv.server_close()
            try:
                m.SALIDA_LOG.close()
            except Exception:
                pass


def main():
    try:
        codigo, informe = correr()
    except Exception as e:
        codigo, informe = 2, {"ok": False, "error": type(e).__name__}
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
