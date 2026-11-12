#!/usr/bin/env python3
"""CLI LOCAL de envio de un borrador ya preparado. NO es parte del MCP.

- Solo corre en la Mac (sys.platform == "darwin"), en la terminal local.
- No lo importa estado_mcp.py y no aparece en tools/list: no existe ninguna
  herramienta ni ruta HTTP que envie, ni se puede disparar con curl.
- Uso permitido UNICAMENTE despues de que el dueno confirme de forma
  explicita, en el chat de Oficina, ESE mensaje concreto (cuenta,
  destinatario y texto exactos del borrador).

Uso:
  python3 enviar_borrador.py BORRADOR_ID --confirmado-por-dueno

Antes de pulsar enviar verifica, en este orden:
  1. el borrador existe y esta "pendiente";
  2. la pestana del Chrome de esa cuenta se identifica como esa cuenta
     (marcas de MCP_MARCAS_CUENTA_A);
  3. el chat abierto es el destinatario del borrador (no navega);
  4. el compositor tiene EXACTAMENTE el texto del borrador.
Si algo no coincide, no envia. Marca el borrador "enviando" antes de pulsar
y "enviado" despues, asi un borrador nunca se envia dos veces.
"""
import json
import os
import sys

import borradores
import capa_wa
import selectores_wa as sw
from selectores_wa import ErrorSelector, ErrorWA

CUENTAS = {"cuenta_a": int(os.environ.get("MCP_PUERTO_CUENTA_A", "9222")),
           "cuenta_b": int(os.environ.get("MCP_PUERTO_CUENTA_B", "9223"))}
BANDERA = "--confirmado-por-dueno"


def cargar_borrador(borrador_id):
    try:
        b = borradores.leer(borrador_id)
    except (ValueError, FileNotFoundError):
        raise ErrorWA("borrador_inexistente", "No existe ese borrador.")
    if b.get("estado") != "pendiente":
        raise ErrorWA("borrador_no_pendiente",
                      "El borrador no esta pendiente (estado: %s)."
                      % b.get("estado"))
    if b.get("cuenta") not in CUENTAS:
        raise ErrorWA("borrador_invalido", "Cuenta desconocida.")
    return b


def enviar(borrador_id, page, sel, plataforma=None):
    """Verifica todo y SOLO entonces pulsa enviar."""
    if (plataforma or sys.platform) != "darwin":
        raise ErrorWA("solo_mac", "Este CLI solo corre en la Mac.")
    b = cargar_borrador(borrador_id)
    capa_wa.verificar_cuenta(page, sel, b["cuenta"])
    if not capa_wa.chat_abierto_en(page, sel, b["destinatario"]):
        raise ErrorWA("chat_distinto",
                      "El chat abierto no es el destinatario del borrador.")
    comp = capa_wa.compositor_en(page, sel)
    if capa_wa.texto_compositor(comp) != capa_wa.normalizar(b["texto"]):
        raise ErrorWA("texto_distinto",
                      "El compositor no tiene el texto exacto del borrador.")
    envio = sel.get("envio") if isinstance(sel.get("envio"), dict) else {}
    modo = envio.get("modo") or "enter"
    boton = None
    if modo == "boton":
        boton = sw.localizar(page, sw.localizador(sel, "envio"))
        if boton.count() == 0:
            raise ErrorWA("sin_boton_envio", "No se ve el boton de enviar.")
    elif modo != "enter":
        raise ErrorSelector("envio", "tiene modo invalido (enter o boton)")

    borradores.cambiar_estado(borrador_id, "enviando")
    if boton is not None:
        boton.first.click(timeout=capa_wa.plazo_accion_ms())
    else:
        comp.press("Enter", timeout=capa_wa.plazo_accion_ms())
    page.wait_for_timeout(capa_wa.espera_carga_ms())
    vacio = capa_wa.texto_compositor(comp) == ""
    borradores.cambiar_estado(borrador_id, "enviado", compositor_vacio=vacio)
    return {"borrador_id": borrador_id, "cuenta": b["cuenta"],
            "estado": "enviado", "compositor_vacio": vacio}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[1] != BANDERA:
        print("Uso: enviar_borrador.py BORRADOR_ID %s" % BANDERA,
              file=sys.stderr)
        return 2
    borrador_id = argv[0]
    pw = navegador = None
    try:
        if sys.platform != "darwin":
            raise ErrorWA("solo_mac", "Este CLI solo corre en la Mac.")
        b = cargar_borrador(borrador_id)
        sel = sw.cargar()
        pw = capa_wa.iniciar_playwright()
        navegador = pw.chromium.connect_over_cdp(
            "http://localhost:%d" % CUENTAS[b["cuenta"]],
            timeout=capa_wa.plazo_accion_ms())
        res = enviar(borrador_id, capa_wa.buscar_pagina(navegador), sel)
        print(json.dumps(res, ensure_ascii=False))
        return 0
    except ErrorWA as e:
        print(json.dumps({"error": e.codigo, "detalle": e.detalle},
                         ensure_ascii=False))
        return 1
    finally:
        if navegador is not None:
            try:
                navegador.close()   # connect_over_cdp: solo desconecta
            except Exception:
                pass
        if pw is not None:
            try:
                pw.stop()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
