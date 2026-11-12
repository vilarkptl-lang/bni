#!/usr/bin/env python3
"""Servidor MCP mcp-wa (Streamable HTTP sin estado). Corre SOLO en la Mac y
escucha SOLO en localhost; se publica por un tunel ya existente.

Herramientas:
  estado_navegador(cuenta)       GET a /json/version y /json/list, nada mas.
  identidad_cuenta(cuenta)       solo lectura: marcas de cuenta, sin clics.
  leer(cuenta, destchat, limite) abre el chat (clic de navegacion) y lee.
  cargar_mas(cuenta, destchat)   gesto de cargar mas segun selectores.
  descargar(cuenta, destchat, id_o_nombre)  adjunto a MCP_DIR_DESCARGAS.
  preparar(cuenta, destinatario, texto)     deja un BORRADOR, no lo envia.

Este servidor NO tiene ninguna herramienta ni ruta que envie mensajes. El
envio solo existe en el CLI local enviar_borrador.py, que no se importa aqui.
Las operaciones de pagina viven en capa_wa (Playwright por CDP local).

Protocolo: MCP con saludo initialize (revisiones 2025-03-26 a 2025-11-25).
No implementa la revision sin estado 2026-07-28.

Configuracion por variables de entorno (ver env.ejemplo):
  MCP_PUERTO, MCP_HOST_PUBLICO, MCP_PUERTO_CUENTA_A, MCP_PUERTO_CUENTA_B,
  MCP_MARCAS_CUENTA_A, MCP_SELECTORES, MCP_DIR_DESCARGAS, MCP_DIR_BORRADORES
"""
import http.client
import io
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import capa_wa
from selectores_wa import ErrorWA

HOST = "localhost"  # fijo: nunca escuchar en otra interfaz
CUENTAS = {"cuenta_a": int(os.environ.get("MCP_PUERTO_CUENTA_A", "9222")),
           "cuenta_b": int(os.environ.get("MCP_PUERTO_CUENTA_B", "9223"))}
VERSIONES = ("2025-11-25", "2025-06-18", "2025-03-26")

MAX_CUERPO = 16 * 1024            # bytes del cuerpo JSON
MAX_PETICION = 64 * 1024          # bytes totales por conexion (linea+cabeceras+cuerpo)
MAX_RESPUESTA_CHROME = 4 * 1024 * 1024
PLAZO_PETICION = 10               # segundos TOTALES para recibir la peticion
PLAZO_ESCRITURA = 5               # segundos para entregar la respuesta
TIMEOUT_CHROME = 3                # segundos TOTALES por cada GET a Chrome
MAX_CONEXIONES = 8                # conexiones/hilos simultaneos, desde accept

METODOS = {"initialize", "ping", "tools/list", "tools/call"}
SALIDA_LOG = sys.stderr
RESPUESTA_503 = (b"HTTP/1.0 503 Service Unavailable\r\n"
                 b"Content-Length: 0\r\nConnection: close\r\n\r\n")

_CUENTA = {"type": "string", "enum": sorted(CUENTAS)}
_CHAT = {"type": "string", "minLength": 1, "maxLength": 200,
         "description": "Nombre exacto del chat tal como aparece en la lista."}


def _esquema(propiedades, requeridas):
    return {"type": "object", "properties": propiedades,
            "required": requeridas, "additionalProperties": False}


HERRAMIENTAS = [
    {
        "name": "estado_navegador",
        "description": (
            "Solo lectura. Indica si el Chrome local de la cuenta responde, su "
            "versión y cuántas pestañas de web.whatsapp.com tiene abiertas. No "
            "verifica la sesión ni la cuenta de WhatsApp, no modifica la página "
            "y no envía nada."
        ),
        "inputSchema": _esquema({"cuenta": _CUENTA}, ["cuenta"]),
    },
    {
        "name": "identidad_cuenta",
        "description": (
            "Solo lectura, sin clics. Indica si el Chrome responde, si hay "
            "pestaña de WhatsApp y si en su DOM aparecen todas las marcas de "
            "la cuenta_a configuradas en el entorno. No lista chats ni nombres."
        ),
        "inputSchema": _esquema({"cuenta": _CUENTA}, ["cuenta"]),
    },
    {
        "name": "leer",
        "description": (
            "Abre el chat indicado si hace falta (clic de navegación) y "
            "devuelve los mensajes visibles: texto y, si los selectores lo "
            "permiten, hora, dirección y adjunto. No escribe ni envía."
        ),
        "inputSchema": _esquema({
            "cuenta": _CUENTA, "destchat": _CHAT,
            "limite": {"type": "integer", "minimum": 1, "maximum": 100,
                       "default": 30}}, ["cuenta", "destchat"]),
    },
    {
        "name": "cargar_mas",
        "description": (
            "Ejecuta el gesto de cargar mensajes anteriores (scroll o clic, "
            "según el archivo de selectores) en el chat indicado. No envía."
        ),
        "inputSchema": _esquema({"cuenta": _CUENTA, "destchat": _CHAT},
                                ["cuenta", "destchat"]),
    },
    {
        "name": "descargar",
        "description": (
            "Descarga un adjunto visible del chat al directorio local de "
            "descargas de la Mac. No sube nada."
        ),
        "inputSchema": _esquema({
            "cuenta": _CUENTA, "destchat": _CHAT,
            "id_o_nombre": {"type": "string", "minLength": 1,
                            "maxLength": 255}},
            ["cuenta", "destchat", "id_o_nombre"]),
    },
    {
        "name": "preparar",
        "description": (
            "Abre el chat y deja el texto EXACTO en el compositor como "
            "borrador pendiente. NO lo envía: este servidor no puede enviar. "
            "El envío solo lo hace el dueño en la Mac tras confirmar ese "
            "mensaje concreto."
        ),
        "inputSchema": _esquema({
            "cuenta": _CUENTA, "destinatario": _CHAT,
            "texto": {"type": "string", "minLength": 1, "maxLength": 4096}},
            ["cuenta", "destinatario", "texto"]),
    },
]
POR_NOMBRE = {h["name"]: h for h in HERRAMIENTAS}
HERRAMIENTA = HERRAMIENTAS[0]   # compatibilidad con v0.3
_CAPA = []
_CAPA_CERROJO = threading.Lock()


def capa():
    with _CAPA_CERROJO:
        if not _CAPA:
            _CAPA.append(capa_wa.Capa(CUENTAS))
        return _CAPA[0]


def registrar(**campos):
    # Nunca se registran cabeceras, cuerpos, URLs ni mensajes de excepcion.
    campos["t"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    SALIDA_LOG.write(json.dumps(campos, ensure_ascii=False) + "\n")
    SALIDA_LOG.flush()


class EstadoHTTPInesperado(Exception):
    pass


def leer_json(puerto, ruta):
    """GET a localhost:puerto con plazo total. Cualquier estado que no sea
    200 (incluidas las redirecciones 3xx) es un error: nunca se sigue."""
    limite = time.monotonic() + TIMEOUT_CHROME
    con = http.client.HTTPConnection("localhost", puerto,
                                     timeout=TIMEOUT_CHROME)
    try:
        con.request("GET", ruta, headers={"Connection": "close"})
        sock = con.sock  # getresponse() puede soltarlo; el plazo lo necesita
        r = con.getresponse()
        if r.status != 200:
            raise EstadoHTTPInesperado()
        datos = bytearray()
        while not r.isclosed():  # se cierra sola al completar la respuesta
            resta = limite - time.monotonic()
            if resta <= 0:
                raise TimeoutError()
            sock.settimeout(resta)
            trozo = r.read1(65536)
            if not trozo:
                break
            datos += trozo
            if len(datos) > MAX_RESPUESTA_CHROME:
                raise ValueError()
    finally:
        con.close()
    return json.loads(datos.decode("utf-8"))


def es_whatsapp(url):
    try:
        return urlsplit(url).hostname == "web.whatsapp.com"
    except ValueError:
        return False  # URL malformada: no cuenta y no se registra


def estado_navegador(cuenta):
    puerto = CUENTAS[cuenta]
    res = {"cuenta": cuenta, "chrome_responde": False,
           "version_chrome": "", "pestanas_whatsapp": 0}
    try:
        version = leer_json(puerto, "/json/version")
        pestanas = leer_json(puerto, "/json/list")
        if not isinstance(version, dict) or not isinstance(pestanas, list):
            raise ValueError()
        total = 0
        for p in pestanas:
            if (isinstance(p, dict) and p.get("type") == "page"
                    and isinstance(p.get("url"), str)
                    and es_whatsapp(p["url"])):
                total += 1
    except Exception as e:
        res["detalle"] = type(e).__name__
        return res
    res["chrome_responde"] = True
    res["version_chrome"] = str(version.get("Browser", ""))[:80]
    res["pestanas_whatsapp"] = total
    return res


def validar_argumentos(herramienta, args):
    """Valida contra el subconjunto de JSON Schema usado arriba. Devuelve
    el diccionario con valores por defecto o None si no es valido."""
    esquema = herramienta["inputSchema"]
    props = esquema["properties"]
    if not isinstance(args, dict) or set(args) - set(props):
        return None
    if not set(esquema["required"]) <= set(args):
        return None
    final = {}
    for nombre, regla in props.items():
        if nombre not in args:
            if "default" in regla:
                final[nombre] = regla["default"]
            continue
        v = args[nombre]
        if regla["type"] == "string":
            if not isinstance(v, str):
                return None
            if "enum" in regla and v not in regla["enum"]:
                return None
            if not regla.get("minLength", 0) <= len(v) <= regla.get(
                    "maxLength", 10 ** 6):
                return None
            if nombre != "texto" and any(ord(c) < 32 for c in v):
                return None
        elif regla["type"] == "integer":
            if isinstance(v, bool) or not isinstance(v, int):
                return None
            if not regla["minimum"] <= v <= regla["maximum"]:
                return None
        final[nombre] = v
    if "cuenta" in final and final["cuenta"] not in CUENTAS:
        return None
    return final


def ejecutar_herramienta(nombre, a):
    """Despacha a la capa. Devuelve (resultado, es_error)."""
    if nombre == "estado_navegador":
        return estado_navegador(a["cuenta"]), False
    try:
        if nombre == "identidad_cuenta":
            res = {"cuenta": a["cuenta"], "chrome_responde": False}
            estado = estado_navegador(a["cuenta"])
            res["chrome_responde"] = estado["chrome_responde"]
            if not estado["chrome_responde"]:
                return res, False
            if estado["pestanas_whatsapp"] == 0:
                res["pestana_whatsapp"] = False
                return res, False
            ident = capa().identidad(a["cuenta"])
            res.update(ident)
            res["coincide_cuenta"] = (
                None if ident["cuenta_detectada"] == "desconocida"
                else ident["cuenta_detectada"] == a["cuenta"])
            return res, False
        if nombre == "leer":
            res = capa().leer(a["cuenta"], a["destchat"], a["limite"])
        elif nombre == "cargar_mas":
            res = capa().cargar_mas(a["cuenta"], a["destchat"])
        elif nombre == "descargar":
            res = capa().descargar(a["cuenta"], a["destchat"],
                                   a["id_o_nombre"])
        elif nombre == "preparar":
            res = capa().preparar(a["cuenta"], a["destinatario"], a["texto"])
        else:
            return {"error": "herramienta_desconocida"}, True
        res = dict(res)
        res.setdefault("cuenta", a["cuenta"])
        return res, False
    except ErrorWA as e:
        return {"cuenta": a["cuenta"], "error": e.codigo,
                "detalle": e.detalle}, True
    except Exception as e:
        return {"cuenta": a["cuenta"], "error": "fallo_interno",
                "detalle": type(e).__name__}, True


def _error(ident, codigo, texto):
    return {"jsonrpc": "2.0", "id": ident,
            "error": {"code": codigo, "message": texto}}


def atender(msg):
    """Devuelve (estado_http, respuesta). respuesta None = sin cuerpo."""
    if (not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0"
            or not isinstance(msg.get("method"), str)):
        return 400, _error(None, -32600, "Peticion invalida")
    metodo = msg["method"]
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return 400, _error(None, -32600, "Peticion invalida")
    if "id" not in msg:
        return 202, None  # notificacion: se acepta y no se hace nada
    ident = msg["id"]
    if isinstance(ident, bool) or not isinstance(ident, (str, int)):
        return 400, _error(None, -32600, "Peticion invalida")

    def ok(resultado):
        return 200, {"jsonrpc": "2.0", "id": ident, "result": resultado}

    if metodo == "initialize":
        pedida = params.get("protocolVersion")
        registrar(evento="initialize", version_pedida=re.sub(
            r"[^0-9-]", "", str(pedida))[:10])
        return ok({
            "protocolVersion": pedida if pedida in VERSIONES else VERSIONES[0],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "mcp-wa", "version": "0.4.0"},
        })
    if metodo == "ping":
        return ok({})
    if metodo == "tools/list":
        return ok({"tools": HERRAMIENTAS})
    if metodo == "tools/call":
        nombre = params.get("name")
        herramienta = POR_NOMBRE.get(nombre) if isinstance(nombre, str) else None
        if herramienta is None:
            return 200, _error(ident, -32602, "Herramienta desconocida")
        args = validar_argumentos(herramienta, params.get("arguments", {}))
        if args is None:
            if set(herramienta["inputSchema"]["properties"]) == {"cuenta"}:
                return 200, _error(ident, -32602, "Argumento 'cuenta' invalido")
            return 200, _error(ident, -32602, "Argumentos invalidos")
        res, es_error = ejecutar_herramienta(nombre, args)
        if nombre == "estado_navegador":
            registrar(evento="estado_navegador", cuenta=res["cuenta"],
                      chrome=res["chrome_responde"],
                      pestanas=res["pestanas_whatsapp"])
        else:
            # Nunca se registran chats, textos, nombres de archivo ni detalles.
            registrar(evento="herramienta", nombre=nombre,
                      cuenta=args["cuenta"], ok=not es_error,
                      error=res.get("error", "") if es_error else "")
        return ok({
            "content": [{"type": "text",
                         "text": json.dumps(res, ensure_ascii=False)}],
            "structuredContent": res,
            "isError": es_error,
        })
    return 200, _error(ident, -32601, "Metodo no soportado")


class LectorConPlazo(io.RawIOBase):
    """Lee del socket con un plazo TOTAL y un tope de bytes por conexion.
    Un cliente que gotea bytes no puede retener el hilo mas alla del plazo."""

    def __init__(self, sock, segundos, max_bytes):
        self._sock = sock
        self._limite = time.monotonic() + segundos
        self._quedan = max_bytes

    def readable(self):
        return True

    def readinto(self, b):
        resta = self._limite - time.monotonic()
        if resta <= 0:
            raise TimeoutError()
        if self._quedan <= 0:
            return 0  # tope alcanzado: se trata como fin de datos
        self._sock.settimeout(resta)
        vista = memoryview(b)[:self._quedan]
        n = self._sock.recv_into(vista)
        self._quedan -= n
        return n


class Manejador(BaseHTTPRequestHandler):
    server_version = "mcp-wa/0.4"
    sys_version = ""

    def setup(self):
        super().setup()
        self.rfile = io.BufferedReader(LectorConPlazo(
            self.connection, PLAZO_PETICION, MAX_PETICION))

    error_message_format = "%(code)d\n"  # sin reflejar datos del cliente
    error_content_type = "text/plain"

    def log_message(self, *a):
        pass  # sin registro automatico de peticiones

    def log_error(self, formato, *args):
        # http.server avisa aqui de plazos vencidos y de HTTP mal formado.
        # Sus argumentos pueden contener datos del cliente: no se registran.
        lento = "timed out" in formato
        registrar(evento="rechazo", http=0 if lento else 400,
                  motivo="cliente_lento" if lento else "http_invalido")

    def responder(self, codigo, cuerpo=None):
        datos = b"" if cuerpo is None else json.dumps(
            cuerpo, ensure_ascii=False).encode("utf-8")
        self.connection.settimeout(PLAZO_ESCRITURA)
        self.send_response(codigo)
        if datos:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(datos)

    def rechazar(self, codigo, motivo):
        registrar(evento="rechazo", http=codigo, motivo=motivo)
        self.responder(codigo)

    def do_GET(self):
        self.rechazar(405, "metodo_http")

    do_DELETE = do_PUT = do_PATCH = do_HEAD = do_OPTIONS = do_GET

    def do_POST(self):
        try:
            self._post()
        except (TimeoutError, ConnectionError):
            registrar(evento="rechazo", http=0, motivo="cliente_lento")
            self.close_connection = True
        except Exception as e:
            # Red de seguridad: se responde 500 generico y solo se registra
            # el tipo de la excepcion, nunca su mensaje.
            registrar(evento="error_interno", tipo=type(e).__name__)
            try:
                self.responder(500, _error(None, -32603, "Error interno"))
            except Exception:
                self.close_connection = True

    def _post(self):
        h = self.headers
        if h.get("Host", "").lower() not in self.server.hosts_permitidos:
            return self.rechazar(403, "host")
        if h.get("Origin") is not None:
            return self.rechazar(403, "origin")  # ningun navegador debe llamar
        if self.path != "/mcp":
            return self.rechazar(404, "ruta")
        tipo = h.get("Content-Type", "").split(";")[0].strip().lower()
        if tipo != "application/json":
            return self.rechazar(415, "content_type")
        if h.get("Transfer-Encoding") or not h.get("Content-Length"):
            return self.rechazar(411, "sin_longitud")
        try:
            largo = int(h["Content-Length"])
        except ValueError:
            return self.rechazar(400, "longitud")
        if largo <= 0:
            return self.rechazar(400, "longitud")
        if largo > MAX_CUERPO:
            return self.rechazar(413, "tamano")
        version = h.get("MCP-Protocol-Version")
        if version is not None and version not in VERSIONES:
            registrar(evento="rechazo", http=400, motivo="version_mcp",
                      version=re.sub(r"[^0-9-]", "", version)[:10])
            return self.responder(400, _error(
                None, -32600, "Version de protocolo no soportada"))
        crudo = self.rfile.read(largo)
        if len(crudo) != largo:
            return self.rechazar(400, "cuerpo_incompleto")
        try:
            msg = json.loads(crudo.decode("utf-8"))
        except Exception:
            registrar(evento="rechazo", http=400, motivo="json")
            return self.responder(400, _error(None, -32700, "JSON invalido"))
        metodo = msg.get("method") if isinstance(msg, dict) else None
        registrar(evento="peticion", metodo=metodo if metodo in METODOS
                  else ("notificacion" if isinstance(metodo, str)
                        and metodo.startswith("notifications/") else "otro"))
        codigo, respuesta = atender(msg)
        self.responder(codigo, respuesta)


class Servidor(ThreadingHTTPServer):
    """Limita conexiones desde accept: si no hay cupo, no se crea hilo."""
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, direccion, manejador):
        super().__init__(direccion, manejador)
        self.cupo = threading.BoundedSemaphore(MAX_CONEXIONES)
        self._ultimo_aviso = 0.0

    def process_request(self, request, client_address):
        if not self.cupo.acquire(blocking=False):
            ahora = time.monotonic()
            if ahora - self._ultimo_aviso >= 1:  # como mucho un aviso/segundo
                self._ultimo_aviso = ahora
                registrar(evento="rechazo", http=503, motivo="saturado")
            try:
                request.settimeout(0)
                request.send(RESPUESTA_503)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.cupo.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.cupo.release()

    def handle_error(self, request, client_address):
        # Sin traza: solo el tipo de la excepcion.
        registrar(evento="error_interno", tipo=sys.exc_info()[0].__name__)


def crear_servidor(puerto, host_publico=""):
    srv = Servidor((HOST, puerto), Manejador)
    real = srv.server_address[1]
    srv.hosts_permitidos = {"localhost:%d" % real}
    if host_publico:
        srv.hosts_permitidos.add(host_publico.strip().lower())
    return srv


if __name__ == "__main__":
    servidor = crear_servidor(int(os.environ.get("MCP_PUERTO", "8765")),
                              os.environ.get("MCP_HOST_PUBLICO", ""))
    registrar(evento="inicio", host=HOST, puerto=servidor.server_address[1])
    servidor.serve_forever()
