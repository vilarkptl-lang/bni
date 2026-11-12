#!/usr/bin/env python3
"""Inspeccion de SOLO LECTURA del DOM de WhatsApp Web, para correr en la Mac.

Se conecta por CDP a los Chrome ya abiertos (http://localhost:PUERTO), busca
la pestana de WhatsApp Web ya abierta y ejecuta un script que solo LEE el
DOM. No hace clic, no escribe, no navega, no enfoca, no lanza Chrome.

Escribe un JSON ESTRUCTURAL para decidir los selectores (selectores.json):
conteos de data-testid, roles, data-icon e ids, candidatos a "cargar mas",
compositor, adjuntos y booleanos de las marcas de la cuenta_a. No vuelca
textos de chats, nombres, titulos ni identificadores de mensajes: los
aria-label solo salen si TODAS sus palabras son vocabulario generico de UI.

Uso:
  MCP_MARCAS_CUENTA_A='marca1|marca2' python3 inspeccion_ro.py \
      [--cuenta cuenta_a|cuenta_b|ambas] [--salida inspeccion_ro.json]
"""
import argparse
import json
import os
import sys

import capa_wa
import selectores_wa as sw

CUENTAS = {"cuenta_a": int(os.environ.get("MCP_PUERTO_CUENTA_A", "9222")),
           "cuenta_b": int(os.environ.get("MCP_PUERTO_CUENTA_B", "9223"))}

# Solo lee el DOM. Las marcas entran como argumento y solo salen booleanos.
JS_ESTRUCTURA = r"""(marcas) => {
  const GENERICAS = new Set(("escribe escribir un una el la los las de del a " +
    "mensaje mensajes message messages type write enviar send adjuntar attach " +
    "descargar download documento document archivo file imagen image foto " +
    "photo video audio voz voice nota note buscar search menu menú chat chats " +
    "nuevo new cargar load mas más more anteriores older earlier previous " +
    "ver view abrir open emoji emojis stickers gif grabar record " +
    "microfono micrófono microphone botón button lista list").split(" "));
  const ariaGenerico = el => {
    const a = (el.getAttribute("aria-label") || "").trim().toLowerCase();
    if (!a || a.length > 60) return a ? "(omitido)" : "";
    const palabras = a.replace(/[.,:;!?¿¡()]/g, " ").split(/\s+/).filter(Boolean);
    return palabras.every(p => GENERICAS.has(p)) ? a : "(omitido)";
  };
  const seguro = v => v && !/@|\d{5,}/.test(v) && v.length <= 60;
  const forma = el => ({
    tag: el.tagName.toLowerCase(),
    role: el.getAttribute("role") || "",
    testid: seguro(el.getAttribute("data-testid")) ? el.getAttribute("data-testid") : "",
    icon: seguro(el.getAttribute("data-icon")) ? el.getAttribute("data-icon") : "",
    data_tab: el.getAttribute("data-tab") || "",
    en_footer: !!el.closest("footer"),
    en_header: !!el.closest("header"),
    aria_generico: ariaGenerico(el),
  });
  const contar = (q, attr, filtro) => {
    const o = {}; let omitidos = 0;
    document.querySelectorAll(q).forEach(el => {
      const v = attr === "id" ? el.id : el.getAttribute(attr);
      if (filtro && !filtro(v)) { omitidos++; return; }
      o[v] = (o[v] || 0) + 1;
    });
    if (omitidos) o["(omitidos)"] = omitidos;
    return o;
  };
  const PAL = /^(cargar|load|more|m[aá]s|anteriores|older|earlier|previous)$/i;
  const cargarMas = [];
  document.querySelectorAll("button,[role=button],[role=link]").forEach(el => {
    const palabras = ((el.innerText || "") + " " + (el.getAttribute("aria-label") || ""))
      .toLowerCase().split(/\s+/);
    const hit = palabras.find(p => PAL.test(p));
    if (hit && (el.innerText || "").length <= 60)
      cargarMas.push(Object.assign({palabra: hit}, forma(el)));
  });
  const compositor = [];
  document.querySelectorAll("[contenteditable=true],[role=textbox]")
    .forEach(el => compositor.push(forma(el)));
  const ADJ = /(download|descarg|attach|document|audio|media|file|pdf)/i;
  const adjuntos = [];
  document.querySelectorAll("[data-testid],[data-icon]").forEach(el => {
    const b = (el.getAttribute("data-testid") || "") + " " + (el.getAttribute("data-icon") || "");
    if (ADJ.test(b)) adjuntos.push(forma(el));
  });
  let ids = 0, idsTrue = 0, idsFalse = 0;
  document.querySelectorAll("[data-id]").forEach(el => {
    ids++; const v = el.getAttribute("data-id") || "";
    if (v.startsWith("true_")) idsTrue++;
    if (v.startsWith("false_")) idsFalse++;
  });
  const clasesMensaje = {};
  document.querySelectorAll("[class]").forEach(el => {
    el.classList.forEach(c => {
      if (/^message-(in|out)$|^focusable-list-item$/.test(c))
        clasesMensaje[c] = (clasesMensaje[c] || 0) + 1;
    });
  });
  const partes = [document.body ? document.body.innerText : ""];
  document.querySelectorAll("[title],img[alt],[aria-label]").forEach(el => {
    for (const a of ["title", "alt", "aria-label"]) {
      const v = el.getAttribute(a); if (v) partes.push(v);
    }
  });
  const todo = partes.join("\n");
  return {
    marcas: marcas.map(m => todo.includes(m)),
    testids: contar("[data-testid]", "data-testid", seguro),
    icons: contar("[data-icon]", "data-icon", seguro),
    roles: contar("[role]", "role"),
    ids: contar("[id]", "id", v => /^[a-z][a-z_-]{0,30}$/i.test(v || "")),
    clases_mensaje: clasesMensaje,
    data_id: {total: ids, prefijo_true: idsTrue, prefijo_false: idsFalse},
    hay_header: document.querySelectorAll("header").length,
    hay_footer: document.querySelectorAll("footer").length,
    cargar_mas: cargarMas.slice(0, 20),
    compositor: compositor.slice(0, 8),
    adjuntos: adjuntos.slice(0, 30),
  };
}"""


def conteo_selectores(page):
    """Cuenta coincidencias de los selectores ya configurados (solo lee)."""
    try:
        sel = sw.cargar()
    except sw.ErrorWA:
        return {}
    out = {}
    for clave, spec in sel.items():
        if sw.es_localizador(spec) and sw.MARCADOR not in json.dumps(spec):
            try:
                out[clave] = sw.localizar(page, spec).count()
            except Exception as e:
                out[clave] = "error:" + type(e).__name__
    return out


def inspeccionar(pw, cuenta, marcas):
    r = {"cuenta": cuenta, "ok": False, "error": ""}
    navegador = None
    try:
        navegador = pw.chromium.connect_over_cdp(
            "http://localhost:%d" % CUENTAS[cuenta], timeout=8000)
        page = capa_wa.buscar_pagina(navegador)
        dom = page.evaluate(JS_ESTRUCTURA, marcas)
        vistos = dom.pop("marcas", [])
        r["marcas"] = {"m%d" % i: bool(v) for i, v in enumerate(vistos)}
        r["todas_las_marcas"] = bool(marcas) and all(r["marcas"].values())
        r["dom"] = dom
        r["selectores_configurados"] = conteo_selectores(page)
        r["ok"] = True
    except sw.ErrorWA as e:
        r["error"] = e.codigo
    except Exception as e:
        r["error"] = type(e).__name__
    finally:
        if navegador is not None:
            try:
                navegador.close()   # connect_over_cdp: solo desconecta
            except Exception:
                pass
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cuenta", choices=["cuenta_a", "cuenta_b", "ambas"],
                    default="ambas")
    ap.add_argument("--salida", default="inspeccion_ro.json")
    a = ap.parse_args(argv)
    marcas = capa_wa.marcas_cuenta_a()
    cuentas = list(CUENTAS) if a.cuenta == "ambas" else [a.cuenta]
    pw = capa_wa.iniciar_playwright()
    try:
        informe = {"marcas_configuradas": len(marcas),
                   "cuentas": {c: inspeccionar(pw, c, marcas)
                               for c in cuentas}}
    finally:
        pw.stop()
    fd = os.open(a.salida, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    print(json.dumps({c: {"ok": v["ok"], "error": v["error"],
                          "todas_las_marcas": v.get("todas_las_marcas")}
                      for c, v in informe["cuentas"].items()}))
    return 0 if all(v["ok"] for v in informe["cuentas"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
