"""Capa Playwright de mcp-wa. Corre SOLO en la Mac, junto a los Chrome ya
abiertos de cada cuenta.

- Se conecta con chromium.connect_over_cdp a http://localhost:PUERTO y
  mantiene la conexion viva (reconecta si se cae).
- Nunca lanza un Chrome nuevo, nunca navega a una URL, nunca escanea QR y
  nunca pulsa botones de sesion: si la pestana no esta lista, falla.
- Lectura (identidad, leer): sin clic, fill, teclado ni foco, salvo el clic
  de NAVEGACION para abrir el chat pedido.
- Acciones permitidas: abrir chat, cargar mas, descargar adjunto y dejar un
  borrador en el compositor. Esta capa NO tiene ninguna funcion que envie
  mensajes: eso vive solo en el CLI local enviar_borrador.py.
- Todos los selectores salen del archivo de selectores (selectores_wa).
"""
import concurrent.futures
import os
import queue
import re
import threading
from urllib.parse import urlsplit

import borradores
import selectores_wa as sw
from selectores_wa import ErrorSelector, ErrorWA

HOST_WA = "web.whatsapp.com"
MAX_TEXTO_SALIDA = 4000

# Devuelve SOLO booleanos: los textos de la pagina nunca salen del navegador.
JS_MARCAS = """(marcas) => {
  const partes = [document.body ? document.body.innerText : ""];
  document.querySelectorAll("[title],img[alt],[aria-label]").forEach(el => {
    for (const a of ["title", "alt", "aria-label"]) {
      const v = el.getAttribute(a);
      if (v) partes.push(v);
    }
  });
  const todo = partes.join("\\n");
  return marcas.map(m => todo.includes(m));
}"""
JS_COINCIDE = "(el, css) => el.matches(css) || el.querySelector(css) !== null"
JS_SCROLL_ARRIBA = """(el) => {
  el.scrollTop = 0;
  el.dispatchEvent(new Event("scroll"));
  return true;
}"""


def iniciar_playwright():
    """Punto unico de arranque (las pruebas lo sustituyen por un simulador)."""
    from playwright.sync_api import sync_playwright
    return sync_playwright().start()


def plazo_accion_ms():
    return int(os.environ.get("MCP_PLAZO_ACCION_MS", "8000"))


def espera_carga_ms():
    return int(os.environ.get("MCP_ESPERA_CARGA_MS", "1500"))


def marcas_cuenta_a():
    crudo = os.environ.get("MCP_MARCAS_CUENTA_A", "")
    return [m.strip() for m in crudo.split("|") if m.strip()]


def dir_descargas():
    d = os.environ.get("MCP_DIR_DESCARGAS") or os.path.join(
        os.getcwd(), "descargas")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


# ---------------------------------------------------------------- pagina ---

def es_pestana_wa(url):
    try:
        return urlsplit(url or "").hostname == HOST_WA
    except ValueError:
        return False


def buscar_pagina(navegador):
    """Pestana de WhatsApp YA abierta. No crea ni navega pestanas."""
    halladas = [p for ctx in navegador.contexts for p in ctx.pages
                if es_pestana_wa(p.url)]
    if not halladas:
        raise ErrorWA("sin_pestana_whatsapp",
                      "No hay una pestana de WhatsApp Web abierta en ese "
                      "Chrome. Abrela a mano; el servidor no navega.")
    if len(halladas) > 1:
        raise ErrorWA("varias_pestanas_whatsapp",
                      "Hay mas de una pestana de WhatsApp Web; deja solo una.")
    return halladas[0]


def _contar(loc):
    return loc.count()


def _texto(loc):
    t = loc.inner_text(timeout=plazo_accion_ms())
    return t[:MAX_TEXTO_SALIDA]


# ------------------------------------------------------ solo lectura -------

def identidad_en(page, sel):
    """Solo lectura: sin clics ni foco. No devuelve textos ni nombres."""
    marcas = marcas_cuenta_a()
    res = {"pestana_whatsapp": True, "marcas_configuradas": len(marcas),
           "coincide_marcas": None, "lista_chats_visible": None}
    if marcas:
        vistos = page.evaluate(JS_MARCAS, marcas)
        res["coincide_marcas"] = bool(
            isinstance(vistos, list) and len(vistos) == len(marcas)
            and all(v is True for v in vistos))
    if sw.configurado(sel, "lista_chats"):
        res["lista_chats_visible"] = _contar(
            sw.localizar(page, sel["lista_chats"])) > 0
    if res["coincide_marcas"] is True:
        detectada = "cuenta_a"
    elif res["coincide_marcas"] is False and res["lista_chats_visible"]:
        detectada = "cuenta_b"   # WhatsApp cargado y sin todas las marcas
    else:
        detectada = "desconocida"
    res["cuenta_detectada"] = detectada
    presentes = {}
    for clave in ("lista_chats", "panel_mensajes", "compositor",
                  "buscador_chats"):
        spec = sel.get(clave)
        if sw.es_localizador(spec) and sw.MARCADOR not in str(spec):
            presentes[clave] = _contar(sw.localizar(page, spec)) > 0
    res["selectores_presentes"] = presentes
    return res


def verificar_cuenta(page, sel, cuenta):
    if not marcas_cuenta_a():
        raise ErrorWA("marcas_no_configuradas",
                      "Define MCP_MARCAS_CUENTA_A para poder distinguir las "
                      "cuentas antes de actuar.")
    if not sw.configurado(sel, "lista_chats"):
        raise ErrorSelector("lista_chats")
    ident = identidad_en(page, sel)
    if ident["cuenta_detectada"] != cuenta:
        raise ErrorWA("cuenta_no_coincide",
                      "La pestana no se identifica como %s (detectada: %s)."
                      % (cuenta, ident["cuenta_detectada"]))
    return ident


def chat_abierto_en(page, sel, nombre):
    """Solo lectura: True si el encabezado muestra ese chat."""
    sw.validar_nombre(nombre)
    enc = sw.localizar(page, sw.localizador(sel, "encabezado_chat"), nombre)
    return _contar(enc) > 0


def leer_en(page, sel, limite):
    """Solo lectura sobre el chat ya abierto. Solo incluye los campos cuyo
    selector esta configurado; no inventa datos."""
    filas = sw.localizar(page, sw.localizador(sel, "mensaje"))
    spec_texto = sw.localizador(sel, "mensaje_texto")
    spec_hora = sel.get("mensaje_hora") if sw.configurado(
        sel, "mensaje_hora") else None
    spec_adj = sel.get("adjunto") if sw.configurado(sel, "adjunto") else None
    spec_adj_nom = sel.get("adjunto_nombre") if sw.configurado(
        sel, "adjunto_nombre") else None
    attr_id = sw.texto_opcional(sel, "mensaje_id_atributo")
    dirs = sel.get("direccion") if isinstance(sel.get("direccion"), dict) else {}
    css_sal = (dirs.get("saliente_css") or "").strip()
    css_ent = (dirs.get("entrante_css") or "").strip()

    total = _contar(filas)
    inicio = max(0, total - limite)
    salida = []
    for i in range(inicio, total):
        fila = filas.nth(i)
        m = {"posicion": i}
        t = sw.localizar(fila, spec_texto)
        m["texto"] = _texto(t.first) if _contar(t) else None
        if spec_hora:
            h = sw.localizar(fila, spec_hora)
            m["hora"] = _texto(h.first).strip() if _contar(h) else None
        if css_sal or css_ent:
            if css_sal and fila.evaluate(JS_COINCIDE, css_sal):
                m["direccion"] = "saliente"
            elif css_ent and fila.evaluate(JS_COINCIDE, css_ent):
                m["direccion"] = "entrante"
            else:
                m["direccion"] = "desconocida"
        if attr_id:
            m["id"] = fila.get_attribute(attr_id)
        if spec_adj:
            a = sw.localizar(fila, spec_adj)
            if _contar(a):
                nom = None
                if spec_adj_nom:
                    n = sw.localizar(a.first, spec_adj_nom)
                    nom = _texto(n.first).strip() if _contar(n) else None
                m["adjunto"] = {"nombre": nom}
        salida.append(m)
    return {"total_visibles": total, "mensajes": salida}


# ------------------------------------------------------------ acciones -----

def abrir_chat(page, sel, nombre):
    """Navegacion: clic en el chat de la lista. No escribe en el compositor."""
    if chat_abierto_en(page, sel, nombre):
        return False
    item = sw.localizar(page, sw.localizador(sel, "item_chat"), nombre)
    if _contar(item) == 0 and sw.configurado(sel, "buscador_chats"):
        buscador = sw.localizar(page, sel["buscador_chats"]).first
        buscador.fill(nombre, timeout=plazo_accion_ms())
        try:
            item.first.wait_for(state="visible", timeout=plazo_accion_ms())
        except Exception:
            pass
    if _contar(item) == 0:
        raise ErrorWA("chat_no_encontrado",
                      "No se encontro el chat pedido en la lista.")
    item.first.click(timeout=plazo_accion_ms())
    enc = sw.localizar(page, sel["encabezado_chat"], nombre)
    try:
        enc.first.wait_for(state="visible", timeout=plazo_accion_ms())
    except Exception:
        raise ErrorWA("chat_no_abierto",
                      "Se hizo clic pero el encabezado no muestra ese chat.")
    return True


def cargar_mas_en(page, sel):
    spec = sel.get("cargar_mas")
    modo = spec.get("modo") if isinstance(spec, dict) else None
    if modo not in ("scroll", "clic"):
        raise ErrorSelector("cargar_mas", "no tiene 'modo' (scroll o clic)")
    filas = (sw.localizar(page, sel["mensaje"])
             if sw.configurado(sel, "mensaje") else None)
    antes = _contar(filas) if filas is not None else None
    if modo == "scroll":
        panel = sw.localizar(page, sw.localizador(sel, "panel_mensajes"))
        if _contar(panel) == 0:
            raise ErrorWA("sin_panel_mensajes",
                          "No se ve el panel de mensajes del chat.")
        panel.first.evaluate(JS_SCROLL_ARRIBA)
    else:
        boton = sw.localizar(page, sw.localizador(sel, "cargar_mas"))
        if _contar(boton) == 0:
            raise ErrorWA("sin_boton_cargar_mas",
                          "No hay boton de cargar mas visible.")
        boton.first.click(timeout=plazo_accion_ms())
    page.wait_for_timeout(espera_carga_ms())
    despues = _contar(filas) if filas is not None else None
    return {"gesto": modo, "mensajes_antes": antes,
            "mensajes_despues": despues}


def nombre_seguro(nombre):
    base = os.path.basename(str(nombre or "").replace("\\", "/"))
    base = re.sub(r"[^\w.\- ]", "_", base).strip().lstrip(".")
    return (base or "descarga")[:150]


def _destino_unico(directorio, nombre):
    raiz, ext = os.path.splitext(nombre)
    destino, n = os.path.join(directorio, nombre), 1
    while os.path.exists(destino):
        destino = os.path.join(directorio, "%s_%d%s" % (raiz, n, ext))
        n += 1
    return destino


def descargar_en(page, sel, clave, directorio):
    filas = sw.localizar(page, sw.localizador(sel, "mensaje"))
    spec_adj = sw.localizador(sel, "adjunto")
    spec_btn = sw.localizador(sel, "boton_descargar")
    spec_nom = sel.get("adjunto_nombre") if sw.configurado(
        sel, "adjunto_nombre") else None
    attr_id = sw.texto_opcional(sel, "mensaje_id_atributo")
    if not spec_nom and not attr_id:
        raise ErrorSelector("adjunto_nombre",
                            "falta (o mensaje_id_atributo) para identificar "
                            "el adjunto")
    for i in reversed(range(_contar(filas))):   # lo mas reciente primero
        fila = filas.nth(i)
        adj = sw.localizar(fila, spec_adj)
        if _contar(adj) == 0:
            continue
        coincide = bool(attr_id) and fila.get_attribute(attr_id) == clave
        if not coincide and spec_nom:
            n = sw.localizar(adj.first, spec_nom)
            coincide = _contar(n) > 0 and _texto(n.first).strip() == clave
        if not coincide:
            continue
        boton = sw.localizar(adj.first, spec_btn)
        if _contar(boton) == 0:
            raise ErrorWA("sin_boton_descargar",
                          "El adjunto no muestra boton de descarga.")
        with page.expect_download(timeout=plazo_accion_ms()) as info:
            boton.first.click(timeout=plazo_accion_ms())
        descarga = info.value
        destino = _destino_unico(directorio,
                                 nombre_seguro(descarga.suggested_filename))
        descarga.save_as(destino)
        return {"archivo": os.path.basename(destino),
                "bytes": os.path.getsize(destino)}
    raise ErrorWA("adjunto_no_encontrado",
                  "No hay un adjunto visible con ese id o nombre.")


def compositor_en(page, sel):
    comp = sw.localizar(page, sw.localizador(sel, "compositor"))
    if _contar(comp) == 0:
        raise ErrorWA("sin_compositor", "No se ve el compositor del chat.")
    return comp.first


def normalizar(texto):
    return (texto or "").rstrip("\n")


def texto_compositor(comp):
    return normalizar(comp.inner_text(timeout=plazo_accion_ms()))


def escribir_borrador_en(page, sel, texto):
    """Deja el texto EXACTO en el compositor. No usa teclas de envio."""
    comp = compositor_en(page, sel)
    actual = texto_compositor(comp)
    objetivo = normalizar(texto)
    if actual and actual != objetivo:
        raise ErrorWA("compositor_ocupado",
                      "El compositor ya tiene otro texto; no se sobrescribe.")
    if actual != objetivo:
        modo = sel["compositor"].get("modo_escritura") or "fill"
        if modo == "fill":
            comp.fill(texto, timeout=plazo_accion_ms())
        elif modo == "insertar":
            comp.click(timeout=plazo_accion_ms())
            page.keyboard.insert_text(texto)
        else:
            raise ErrorSelector("compositor",
                                "tiene modo_escritura invalido (fill o "
                                "insertar)")
    if texto_compositor(comp) != objetivo:
        comp.fill("", timeout=plazo_accion_ms())
        raise ErrorWA("texto_no_coincide",
                      "El compositor no quedo con el texto exacto; se "
                      "limpio y no se guardo borrador.")


# ----------------------------------------------------- conexion viva -------

class Capa:
    """Mantiene Playwright y las conexiones CDP en UN hilo propio (la API
    sincrona de Playwright no admite varios hilos)."""

    def __init__(self, cuentas, plazo=None):
        self.cuentas = cuentas            # nombre -> puerto (referencia viva)
        self.plazo = plazo or float(os.environ.get(
            "MCP_PLAZO_HERRAMIENTA", "45"))
        self._cola = queue.Queue()
        self._hilo = None
        self._cerrojo = threading.Lock()
        self._pw = None
        self._nav = {}

    # -- hilo propio
    def _arrancar(self):
        with self._cerrojo:
            if self._hilo is None or not self._hilo.is_alive():
                self._hilo = threading.Thread(target=self._bucle,
                                              daemon=True)
                self._hilo.start()

    def _bucle(self):
        while True:
            tarea = self._cola.get()
            if tarea is None:
                return
            fn, args, futuro = tarea
            if not futuro.set_running_or_notify_cancel():
                continue
            try:
                futuro.set_result(fn(*args))
            except BaseException as e:
                futuro.set_exception(e)

    def _ejecutar(self, fn, *args):
        self._arrancar()
        futuro = concurrent.futures.Future()
        self._cola.put((fn, args, futuro))
        try:
            return futuro.result(timeout=self.plazo)
        except concurrent.futures.TimeoutError:
            futuro.cancel()
            raise ErrorWA("plazo_herramienta",
                          "La operacion tardo demasiado.")

    def cerrar(self):
        def _cerrar():
            for b in list(self._nav.values()):
                try:
                    b.close()   # en connect_over_cdp solo desconecta
                except Exception:
                    pass
            self._nav.clear()
            if self._pw is not None:
                try:
                    self._pw.stop()
                except Exception:
                    pass
                self._pw = None
        if self._hilo is not None and self._hilo.is_alive():
            try:
                self._ejecutar(_cerrar)
            finally:
                self._cola.put(None)

    # -- conexion (siempre dentro del hilo propio)
    def _navegador(self, cuenta):
        if self._pw is None:
            self._pw = iniciar_playwright()
        b = self._nav.get(cuenta)
        if b is not None and not b.is_connected():
            self._nav.pop(cuenta, None)
            b = None
        if b is None:
            try:
                b = self._pw.chromium.connect_over_cdp(
                    "http://localhost:%d" % self.cuentas[cuenta],
                    timeout=plazo_accion_ms())
            except Exception:
                raise ErrorWA("chrome_no_responde",
                              "No se pudo conectar al Chrome local de esa "
                              "cuenta.")
            self._nav[cuenta] = b
        return b

    def _con_pagina(self, cuenta, fn):
        sel_cache = []

        def sel():
            if not sel_cache:
                sel_cache.append(sw.cargar())
            return sel_cache[0]

        for intento in (1, 2):
            b = self._navegador(cuenta)
            try:
                return fn(buscar_pagina(b), sel)
            except ErrorWA:
                raise
            except Exception as e:
                if not b.is_connected() and intento == 1:
                    self._nav.pop(cuenta, None)   # se cayo: reconecta
                    continue
                if type(e).__name__ == "TimeoutError":
                    raise ErrorWA("plazo_accion",
                                  "Un elemento no aparecio a tiempo.")
                raise ErrorWA("fallo_playwright", type(e).__name__)

    # -- operaciones publicas (sin ninguna de envio)
    def identidad(self, cuenta):
        return self._ejecutar(self._con_pagina, cuenta,
                              lambda p, s: identidad_en(p, s()))

    def cargar_mas(self, cuenta, destchat):
        def op(p, s):
            verificar_cuenta(p, s(), cuenta)
            abrir_chat(p, s(), destchat)
            return cargar_mas_en(p, s())
        return self._ejecutar(self._con_pagina, cuenta, op)

    def leer(self, cuenta, destchat, limite):
        def op(p, s):
            verificar_cuenta(p, s(), cuenta)
            abrir_chat(p, s(), destchat)
            return leer_en(p, s(), limite)
        return self._ejecutar(self._con_pagina, cuenta, op)

    def descargar(self, cuenta, destchat, clave):
        def op(p, s):
            verificar_cuenta(p, s(), cuenta)
            abrir_chat(p, s(), destchat)
            return descargar_en(p, s(), clave, dir_descargas())
        return self._ejecutar(self._con_pagina, cuenta, op)

    def preparar(self, cuenta, destinatario, texto):
        def op(p, s):
            verificar_cuenta(p, s(), cuenta)
            abrir_chat(p, s(), destinatario)
            escribir_borrador_en(p, s(), texto)
            b = borradores.crear(cuenta, destinatario, texto)
            return {k: b[k] for k in ("borrador_id", "cuenta",
                                      "destinatario", "texto", "estado")}
        return self._ejecutar(self._con_pagina, cuenta, op)
