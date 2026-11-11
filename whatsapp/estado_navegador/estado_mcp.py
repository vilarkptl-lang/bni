#!/usr/bin/env python3
"""Servidor MCP minimo (Streamable HTTP sin estado, solo biblioteca estandar).

Expone UNA herramienta: estado_navegador(cuenta).
Solo hace GET a /json/version y /json/list del Chrome local, siempre en
127.0.0.1 y en el puerto fijo de la cuenta; no sigue redirecciones.
No abre conexion de depuracion, no ejecuta JavaScript, no hace clic, no envia.
No verifica la sesion ni la cuenta de WhatsApp. No devuelve titulos ni URLs.

Protocolo: MCP con saludo initialize (revisiones 2025-03-26 a 2025-11-25).
No implementa la revision sin estado 2026-07-28.

Configuracion por variables de entorno (ninguna es secreta):
  MCP_PUERTO        puerto local (por defecto 8765)
  MCP_HOST_PUBLICO  nombre publico del tunel, para aceptar su cabecera Host
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

HOST = "127.0.0.1"  # fijo: nunca escuchar en otra interfaz
CUENTAS = {"personal": 9222, "vilar": 9223}
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

HERRAMIENTA = {
    "name": "estado_navegador",
    "description": (
        "Solo lectura. Indica si el Chrome local de la cuenta responde, su "
        "versión y cuántas pestañas de web.whatsapp.com tiene abiertas. No "
        "verifica la sesión ni la cuenta de WhatsApp, no modifica la página "
        "y no envía nada."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {"cuenta": {"type": "string", "enum": sorted(CUENTAS)}},
        "required": ["cuenta"],
        "additionalProperties": False,
    },
}


def registrar(**campos):
    # Nunca se registran cabeceras, cuerpos, URLs ni mensajes de excepcion.
    campos["t"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    SALIDA_LOG.write(json.dumps(campos, ensure_ascii=False) + "\n")
    SALIDA_LOG.flush()


class EstadoHTTPInesperado(Exception):
    pass


def leer_json(puerto, ruta):
    """GET a 127.0.0.1:puerto con plazo total. Cualquier estado que no sea
    200 (incluidas las redirecciones 3xx) es un error: nunca se sigue."""
    limite = time.monotonic() + TIMEOUT_CHROME
    con = http.client.HTTPConnection("127.0.0.1", puerto,
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
            "serverInfo": {"name": "estado-navegador", "version": "0.3.0"},
        })
    if metodo == "ping":
        return ok({})
    if metodo == "tools/list":
        return ok({"tools": [HERRAMIENTA]})
    if metodo == "tools/call":
        args = params.get("arguments", {})
        if params.get("name") != HERRAMIENTA["name"]:
            return 200, _error(ident, -32602, "Herramienta desconocida")
        if (not isinstance(args, dict) or set(args) != {"cuenta"}
                or not isinstance(args["cuenta"], str)
                or args["cuenta"] not in CUENTAS):
            return 200, _error(ident, -32602, "Argumento 'cuenta' invalido")
        res = estado_navegador(args["cuenta"])
        registrar(evento="estado_navegador", cuenta=res["cuenta"],
                  chrome=res["chrome_responde"],
                  pestanas=res["pestanas_whatsapp"])
        return ok({
            "content": [{"type": "text",
                         "text": json.dumps(res, ensure_ascii=False)}],
            "structuredContent": res,
            "isError": False,
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
    server_version = "estado-mcp/0.3"
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
    srv.hosts_permitidos = {"127.0.0.1:%d" % real, "localhost:%d" % real}
    if host_publico:
        srv.hosts_permitidos.add(host_publico.strip().lower())
    return srv


if __name__ == "__main__":
    servidor = crear_servidor(int(os.environ.get("MCP_PUERTO", "8765")),
                              os.environ.get("MCP_HOST_PUBLICO", ""))
    registrar(evento="inicio", host=HOST, puerto=servidor.server_address[1])
    servidor.serve_forever()
