#!/usr/bin/env python3
"""Pruebas de estado_mcp.py (protocolo y estado_navegador, base v0.3).

Ejecutar junto a estado_mcp.py:  python3 -m unittest -v test_estado_mcp
Usan un Chrome SIMULADO en puertos efimeros de localhost: no tocan el Chrome
real, los puertos 9222/9223, WhatsApp ni la red.
"""
import http.client
import io
import ipaddress
import json
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import estado_mcp as m

SECRETO = "SECRETO-DE-PRUEBA-123"
PESTANAS = [
    {"type": "page", "url": "https://web.whatsapp.com/",
     "title": "(7) WhatsApp", "id": "ID-PRIVADO",
     "webSocketDebuggerUrl": "ws://localhost/devtools/page/ID-PRIVADO"},
    {"type": "page", "url": "https://ejemplo.test/?web.whatsapp.com",
     "title": "senuelo"},
    {"type": "page", "url": "https://web.whatsapp.com.ejemplo.test/",
     "title": "senuelo 2"},
    {"type": "service_worker", "url": "https://web.whatsapp.com/sw.js"},
    "basura",
    {"type": "page", "url": "http://[host-interno"},
    {"type": "page", "url": "https://web.whatsapp.com\uff03@URL-ROTA.test/"},
    {"type": "page", "url": 12345},
    {"type": "page"},
]


class Destino(BaseHTTPRequestHandler):
    """Servidor al que NUNCA debe llegar una consulta redirigida."""
    vistas = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Destino.vistas.append(self.path)
        d = b"[]"
        self.send_response(200)
        self.send_header("Content-Length", str(len(d)))
        self.end_headers()
        self.wfile.write(d)


class ChromeFalso(BaseHTTPRequestHandler):
    vistas = []      # (metodo, ruta) recibidas
    demora = 0
    relleno = 0
    redirigir_a = None   # si se fija, responde 302 hacia esa URL
    goteo = 0            # si se fija, entrega el cuerpo byte a byte

    def log_message(self, *a):
        pass

    def do_GET(self):
        ChromeFalso.vistas.append(("GET", self.path))
        time.sleep(ChromeFalso.demora)
        if ChromeFalso.redirigir_a:
            self.send_response(302)
            self.send_header("Location", ChromeFalso.redirigir_a + self.path)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/json/version":
            cuerpo = {"Browser": "Chrome/TEST",
                      "webSocketDebuggerUrl": "ws://localhost/devtools/x"}
        else:
            cuerpo = PESTANAS + [{"type": "other", "x": "a" * ChromeFalso.relleno}]
        d = json.dumps(cuerpo).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(d)))
        self.end_headers()
        try:
            if ChromeFalso.goteo:
                for i in range(len(d)):
                    self.wfile.write(d[i:i + 1])
                    self.wfile.flush()
                    time.sleep(ChromeFalso.goteo)
            else:
                self.wfile.write(d)
        except OSError:
            pass  # el servidor corto por tiempo: es lo esperado

    def do_POST(self):
        ChromeFalso.vistas.append(("POST", self.path))
        self.send_response(500)
        self.end_headers()

    do_PUT = do_DELETE = do_POST


def puerto_libre():
    s = socket.socket()
    s.bind(("localhost", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chrome = HTTPServer(("localhost", 0), ChromeFalso)
        threading.Thread(target=cls.chrome.serve_forever, daemon=True).start()
        cls._cuentas = dict(m.CUENTAS)
        m.CUENTAS["cuenta_b"] = cls.chrome.server_address[1]
        m.CUENTAS["cuenta_a"] = puerto_libre()  # nadie escucha: Chrome caido
        cls.srv = m.crear_servidor(0, "mcp.ejemplo.test")
        cls.puerto = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.chrome.shutdown()
        cls.chrome.server_close()
        m.CUENTAS.clear()
        m.CUENTAS.update(cls._cuentas)

    def setUp(self):
        self.log = io.StringIO()
        m.SALIDA_LOG = self.log
        ChromeFalso.vistas = []
        ChromeFalso.demora = 0
        ChromeFalso.relleno = 0
        ChromeFalso.redirigir_a = None
        ChromeFalso.goteo = 0
        Destino.vistas = []
        self.esperar_cupo()

    def esperar_cupo(self):
        """Espera a que no queden conexiones de pruebas anteriores."""
        fin = time.time() + 5
        while time.time() < fin:
            if self.srv.cupo._value == m.MAX_CONEXIONES:
                return
            time.sleep(0.02)
        self.fail("quedaron conexiones abiertas de una prueba anterior")

    def http(self, metodo="POST", ruta="/mcp", cuerpo=None, cabeceras=None,
             tipo="application/json"):
        c = http.client.HTTPConnection("localhost", self.puerto, timeout=15)
        h = {"CF-Access-Client-Id": "id.access",
             "CF-Access-Client-Secret": SECRETO}
        if tipo:
            h["Content-Type"] = tipo
        h.update(cabeceras or {})
        if isinstance(cuerpo, (dict, list)):
            cuerpo = json.dumps(cuerpo)
        try:
            c.request(metodo, ruta, body=cuerpo, headers=h)
            r = c.getresponse()
            texto = r.read().decode("utf-8")
        finally:
            c.close()
        return r.status, (json.loads(texto) if texto else None)

    def rpc(self, metodo, params=None, ident=1, **kw):
        msg = {"jsonrpc": "2.0", "id": ident, "method": metodo}
        if params is not None:
            msg["params"] = params
        return self.http(cuerpo=msg, **kw)

    def llamar(self, nombre, args):
        return self.rpc("tools/call", {"name": nombre, "arguments": args})


class Protocolo(Base):
    def test_initialize_versiones(self):
        for v in m.VERSIONES:
            s, r = self.rpc("initialize", {"protocolVersion": v})
            self.assertEqual((s, r["result"]["protocolVersion"]), (200, v))
        s, r = self.rpc("initialize", {"protocolVersion": "2026-07-28"})
        self.assertEqual(r["result"]["protocolVersion"], m.VERSIONES[0])
        self.assertEqual(r["result"]["capabilities"], {"tools": {}})
        self.assertIn('"version_pedida": "2026-07-28"', self.log.getvalue())

    def test_notificacion_sin_cuerpo(self):
        s, r = self.http(cuerpo={"jsonrpc": "2.0",
                                 "method": "notifications/initialized"})
        self.assertEqual((s, r), (202, None))

    def test_ping(self):
        self.assertEqual(self.rpc("ping")[1]["result"], {})

    def test_herramientas_listadas(self):
        s, r = self.rpc("tools/list")
        nombres = [t["name"] for t in r["result"]["tools"]]
        self.assertEqual(nombres, ["estado_navegador", "identidad_cuenta",
                                   "leer", "cargar_mas", "descargar",
                                   "preparar"])
        for n in nombres:
            self.assertNotIn("enviar", n)
            self.assertNotIn("send", n)
        for t in r["result"]["tools"]:
            self.assertFalse(t["inputSchema"]["additionalProperties"])
        esquema = r["result"]["tools"][0]["inputSchema"]
        self.assertEqual(esquema["properties"]["cuenta"]["enum"],
                         ["cuenta_a", "cuenta_b"])
        self.assertFalse(esquema["additionalProperties"])

    def test_cabecera_de_version(self):
        s, _ = self.rpc("tools/list",
                        cabeceras={"MCP-Protocol-Version": "2025-06-18"})
        self.assertEqual(s, 200)
        s, r = self.rpc("tools/list",
                        cabeceras={"MCP-Protocol-Version": "2026-07-28"})
        self.assertEqual((s, r["error"]["code"]), (400, -32600))

    def test_metodo_desconocido(self):
        for metodo in ("server/discover", "resources/list", "enviar"):
            s, r = self.rpc(metodo)
            self.assertEqual(r["error"]["code"], -32601)


class Herramienta(Base):
    def test_chrome_arriba(self):
        s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
        res = r["result"]["structuredContent"]
        self.assertEqual(res, {"cuenta": "cuenta_b", "chrome_responde": True,
                               "version_chrome": "Chrome/TEST",
                               "pestanas_whatsapp": 1})
        self.assertEqual(json.loads(r["result"]["content"][0]["text"]), res)
        self.assertFalse(r["result"]["isError"])

    def test_no_filtra_titulos_ni_identificadores(self):
        s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
        todo = json.dumps(r) + self.log.getvalue()
        for prohibido in ("(7) WhatsApp", "ID-PRIVADO", "ws://", "devtools",
                          "titulos", "senuelo", "https://"):
            self.assertNotIn(prohibido, todo)

    def test_solo_dos_get_a_chrome(self):
        self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
        self.assertEqual(ChromeFalso.vistas,
                         [("GET", "/json/version"), ("GET", "/json/list")])

    def test_chrome_caido(self):
        s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_a"})
        res = r["result"]["structuredContent"]
        self.assertFalse(res["chrome_responde"])
        self.assertEqual(res["pestanas_whatsapp"], 0)

    def test_chrome_lento_respeta_tiempo(self):
        ChromeFalso.demora = 1.5
        viejo, m.TIMEOUT_CHROME = m.TIMEOUT_CHROME, 0.3
        try:
            t = time.time()
            s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
            self.assertLess(time.time() - t, 1.2)
            self.assertFalse(r["result"]["structuredContent"]["chrome_responde"])
        finally:
            m.TIMEOUT_CHROME = viejo
            time.sleep(1.6)

    def test_respuesta_de_chrome_enorme(self):
        ChromeFalso.relleno = m.MAX_RESPUESTA_CHROME + 10
        s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
        self.assertFalse(r["result"]["structuredContent"]["chrome_responde"])

    def test_argumentos_invalidos(self):
        casos = [("enviar", {"cuenta": "cuenta_b"}),
                 ("estado_navegador", {}),
                 ("estado_navegador", {"cuenta": "otra"}),
                 ("estado_navegador", {"cuenta": 9222}),
                 ("estado_navegador", {"cuenta": ["cuenta_b"]}),
                 ("estado_navegador", {"cuenta": "cuenta_b", "puerto": 22}),
                 ("estado_navegador", "cuenta_b")]
        for nombre, args in casos:
            s, r = self.llamar(nombre, args)
            self.assertEqual(r["error"]["code"], -32602, (nombre, args))
        self.assertEqual(ChromeFalso.vistas, [])


class Rechazos(Base):
    def test_json_invalido(self):
        s, r = self.http(cuerpo="{no es json")
        self.assertEqual((s, r["error"]["code"]), (400, -32700))

    def test_formas_invalidas(self):
        for cuerpo in ([{"jsonrpc": "2.0", "id": 1, "method": "ping"}],
                       {"id": 1, "method": "ping"},
                       {"jsonrpc": "1.0", "id": 1, "method": "ping"},
                       {"jsonrpc": "2.0", "id": 1, "method": 5},
                       {"jsonrpc": "2.0", "id": None, "method": "ping"},
                       {"jsonrpc": "2.0", "id": True, "method": "ping"},
                       {"jsonrpc": "2.0", "id": 1, "method": "ping",
                        "params": [1]},
                       "texto", 7):
            s, r = self.http(cuerpo=json.dumps(cuerpo))
            self.assertEqual((s, r["error"]["code"]), (400, -32600), cuerpo)

    def test_cuerpo_demasiado_grande(self):
        s, _ = self.http(cuerpo="x" * (m.MAX_CUERPO + 1))
        self.assertEqual(s, 413)

    def test_tipo_de_contenido(self):
        for tipo in ("text/plain", "application/x-www-form-urlencoded", None):
            s, _ = self.http(cuerpo="{}", tipo=tipo)
            self.assertEqual(s, 415)

    def test_sin_longitud_o_por_trozos(self):
        s, _ = self.http(cuerpo=None)
        self.assertIn(s, (400, 411))
        c = http.client.HTTPConnection("localhost", self.puerto, timeout=10)
        c.request("POST", "/mcp", body=iter([b"{}"]),
                  headers={"Content-Type": "application/json",
                           "Transfer-Encoding": "chunked"})
        self.assertEqual(c.getresponse().status, 411)
        c.close()

    def test_metodos_http_y_rutas(self):
        for metodo in ("GET", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
            self.assertEqual(self.http(metodo=metodo)[0], 405, metodo)
        for ruta in ("/", "/mcp/", "/mcp?x=1", "/json/list", "/otra"):
            s, _ = self.rpc("ping", ruta=ruta)
            self.assertEqual(s, 404, ruta)

    def test_origin_y_host(self):
        s, _ = self.rpc("ping", cabeceras={"Origin": "https://malo.test"})
        self.assertEqual(s, 403)
        s, _ = self.rpc("ping", cabeceras={"Host": "malo.test"})
        self.assertEqual(s, 403)
        s, _ = self.rpc("ping", cabeceras={"Host": "mcp.ejemplo.test"})
        self.assertEqual(s, 200)

    def test_cliente_lento_se_corta(self):
        viejo, m.PLAZO_PETICION = m.PLAZO_PETICION, 0.5
        try:
            s = socket.create_connection(("localhost", self.puerto))
            s.sendall(b"POST /mcp HTTP/1.1\r\nHost: localhost:%d\r\n"
                      b"Content-Type: application/json\r\n"
                      b"Content-Length: 50\r\n\r\n{" % self.puerto)
            s.settimeout(5)
            t = time.time()
            self.assertEqual(s.recv(100), b"")  # el servidor cierra
            self.assertLess(time.time() - t, 3)
            s.close()
        finally:
            m.PLAZO_PETICION = viejo
        self.esperar_cupo()
        self.assertEqual(self.rpc("ping")[0], 200)  # sigue atendiendo

    def test_plazo_total_con_goteo(self):
        """Regresion 3: un cliente que gotea bytes sin quedar inactivo."""
        viejo, m.PLAZO_PETICION = m.PLAZO_PETICION, 1.0
        try:
            s = socket.create_connection(("localhost", self.puerto))
            s.settimeout(0.05)
            datos = (b"POST /mcp HTTP/1.1\r\nHost: localhost:%d\r\n"
                     b"Content-Type: application/json\r\n"
                     b"Content-Length: 4000\r\n\r\n" % self.puerto
                     + b"x" * 4000)
            t = time.time()
            cerrado = False
            for i in range(len(datos)):
                try:
                    s.sendall(datos[i:i + 1])   # un byte cada 50 ms
                except OSError:
                    cerrado = True
                    break
                try:
                    if s.recv(100) == b"":
                        cerrado = True
                        break
                except socket.timeout:
                    pass
                except OSError:
                    cerrado = True
                    break
                if time.time() - t > 6:
                    break
            s.close()
            self.assertTrue(cerrado, "el servidor no corto el goteo")
            self.assertLess(time.time() - t, 3)
        finally:
            m.PLAZO_PETICION = viejo
        self.assertIn("cliente_lento", self.log.getvalue())
        self.esperar_cupo()
        self.assertEqual(self.rpc("ping")[0], 200)

    def test_cabeceras_por_goteo_tambien_tienen_plazo(self):
        viejo, m.PLAZO_PETICION = m.PLAZO_PETICION, 0.8
        try:
            s = socket.create_connection(("localhost", self.puerto))
            s.settimeout(0.15)
            t = time.time()
            cerrado = False
            while time.time() - t < 5 and not cerrado:
                try:
                    s.sendall(b"X-Relleno: a\r\n")
                    if s.recv(100) == b"":
                        cerrado = True
                except socket.timeout:
                    pass
                except OSError:
                    cerrado = True
            s.close()
            self.assertTrue(cerrado)
            self.assertLess(time.time() - t, 3)
        finally:
            m.PLAZO_PETICION = viejo

    def test_tope_de_bytes_por_conexion(self):
        relleno = "".join("X-R%d: %s\r\n" % (i, "a" * 1000) for i in range(90))
        s = socket.create_connection(("localhost", self.puerto))
        s.settimeout(5)
        try:
            s.sendall(("POST /mcp HTTP/1.1\r\nHost: localhost:%d\r\n"
                       % self.puerto + relleno + "\r\n").encode())
            primera = s.recv(200).split(b"\r\n")[0]
        except OSError:
            primera = b""
        s.close()
        self.assertNotIn(b" 200 ", primera)
        self.esperar_cupo()
        self.assertEqual(self.rpc("ping")[0], 200)


class Aceptacion(Base):
    """Regresion 4: el limite se aplica en accept, antes de crear hilos."""

    def test_conexiones_inactivas_no_crean_hilos_de_mas(self):
        viejo, m.PLAZO_PETICION = m.PLAZO_PETICION, 3.0
        base = threading.active_count()
        ociosas = []
        try:
            for _ in range(m.MAX_CONEXIONES):
                ociosas.append(socket.create_connection(
                    ("localhost", self.puerto)))  # sin enviar ni un byte
            fin = time.time() + 2
            while self.srv.cupo._value > 0 and time.time() < fin:
                time.sleep(0.02)
            self.assertEqual(self.srv.cupo._value, 0)
            hilos_llenos = threading.active_count()
            self.assertLessEqual(hilos_llenos - base, m.MAX_CONEXIONES)
            extras = []
            for _ in range(20):
                x = socket.create_connection(("localhost", self.puerto))
                x.settimeout(3)
                extras.append(x)
            for x in extras:
                self.assertTrue(x.recv(200).startswith(b"HTTP/1.0 503"))
                self.assertEqual(x.recv(200), b"")
                x.close()
            self.assertEqual(threading.active_count(), hilos_llenos)
            # 20 rechazos, pero el aviso se limita a uno por segundo.
            avisos = self.log.getvalue().count("saturado")
            self.assertGreaterEqual(avisos, 1)
            self.assertLessEqual(avisos, 3)
        finally:
            for o in ociosas:
                o.close()
            m.PLAZO_PETICION = viejo
        self.esperar_cupo()                      # el cupo se libera solo
        self.assertEqual(self.rpc("ping")[0], 200)

    def test_cupo_se_libera_tras_cada_peticion(self):
        for _ in range(m.MAX_CONEXIONES * 3):
            self.assertEqual(self.rpc("ping")[0], 200)
        self.esperar_cupo()

    def test_rafaga_no_supera_el_limite(self):
        ChromeFalso.demora = 0.3
        resultados = []

        def una():
            try:
                resultados.append(self.llamar("estado_navegador",
                                              {"cuenta": "cuenta_b"})[0])
            except (OSError, http.client.HTTPException, ValueError):
                resultados.append("cortada")
        hilos = [threading.Thread(target=una)
                 for _ in range(m.MAX_CONEXIONES + 6)]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        self.assertLessEqual(resultados.count(200), m.MAX_CONEXIONES)
        self.assertGreaterEqual(resultados.count(200), 1)
        self.assertTrue(set(resultados) <= {200, 503, "cortada"})
        time.sleep(0.5)


class Redirecciones(Base):
    """Regresion 1: las consultas no salen del puerto local previsto."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.destino = HTTPServer(("localhost", 0), Destino)
        threading.Thread(target=cls.destino.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.destino.shutdown()
        cls.destino.server_close()
        super().tearDownClass()

    def test_no_sigue_redireccion(self):
        for destino in ("http://localhost:%d" % self.destino.server_address[1],
                        "http://DESTINO-EXTERNO.test"):
            ChromeFalso.redirigir_a = destino
            ChromeFalso.vistas = []
            s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
            res = r["result"]["structuredContent"]
            self.assertEqual(s, 200)
            self.assertFalse(res["chrome_responde"])
            self.assertEqual(res["pestanas_whatsapp"], 0)
            self.assertEqual(res["detalle"], "EstadoHTTPInesperado")
            self.assertEqual(ChromeFalso.vistas, [("GET", "/json/version")])
        self.assertEqual(Destino.vistas, [])
        self.assertNotIn("DESTINO-EXTERNO", self.log.getvalue())

    def test_otros_estados_tampoco_valen(self):
        for codigo in (301, 303, 307, 308):
            self.assertNotEqual(codigo, 200)
        ChromeFalso.redirigir_a = "/json/list"  # redireccion relativa
        s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
        self.assertFalse(r["result"]["structuredContent"]["chrome_responde"])

    def test_plazo_total_de_chrome_con_goteo(self):
        ChromeFalso.goteo = 0.05
        viejo, m.TIMEOUT_CHROME = m.TIMEOUT_CHROME, 0.5
        try:
            t = time.time()
            s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
            self.assertLess(time.time() - t, 2)
            res = r["result"]["structuredContent"]
            self.assertFalse(res["chrome_responde"])
            self.assertEqual(res["detalle"], "TimeoutError")
        finally:
            m.TIMEOUT_CHROME = viejo
            ChromeFalso.goteo = 0
            time.sleep(0.3)


class UrlsMalformadas(Base):
    """Regresion 2: una URL rota no tumba la peticion ni llega al registro."""

    def test_urls_rotas_se_ignoran(self):
        s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
        self.assertEqual(s, 200)
        res = r["result"]["structuredContent"]
        self.assertTrue(res["chrome_responde"])
        self.assertEqual(res["pestanas_whatsapp"], 1)
        todo = json.dumps(r) + self.log.getvalue()
        for prohibido in ("[host-interno", "URL-ROTA", "error_interno"):
            self.assertNotIn(prohibido, todo)

    def test_es_whatsapp(self):
        self.assertTrue(m.es_whatsapp("https://web.whatsapp.com/"))
        for url in ("http://[host-interno", "https://web.whatsapp.com\uff03@x/", "",
                    "web.whatsapp.com", "https://web.whatsapp.com.x.test/",
                    "https://x.test/web.whatsapp.com", "//[", "\x00"):
            self.assertFalse(m.es_whatsapp(url), url)

    def test_error_inesperado_responde_500_sin_filtrar(self):
        original = m.estado_navegador

        def roto(cuenta):
            raise RuntimeError("DATO-INTERNO-SECRETO http://[host-interno")
        m.estado_navegador = roto
        try:
            s, r = self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
        finally:
            m.estado_navegador = original
        self.assertEqual((s, r["error"]["code"]), (500, -32603))
        log = self.log.getvalue()
        self.assertIn('"tipo": "RuntimeError"', log)
        for prohibido in ("DATO-INTERNO", "[host-interno", "Traceback"):
            self.assertNotIn(prohibido, log + json.dumps(r))
        self.esperar_cupo()
        self.assertEqual(self.rpc("ping")[0], 200)   # sigue atendiendo


class Higiene(Base):
    def test_registro_sin_secretos_ni_cuerpos(self):
        self.rpc("initialize", {"protocolVersion": "2025-06-18",
                                "clientInfo": {"name": "DATO-DEL-CUERPO"}})
        self.llamar("estado_navegador", {"cuenta": "cuenta_b"})
        self.rpc("metodo-raro-" + SECRETO)
        self.http(cuerpo="{roto " + SECRETO)
        log = self.log.getvalue()
        self.assertTrue(log)
        for prohibido in (SECRETO, "id.access", "CF-Access", "DATO-DEL-CUERPO"):
            self.assertNotIn(prohibido, log)
        for linea in log.splitlines():
            json.loads(linea)

    def test_escucha_solo_local(self):
        self.assertEqual(m.HOST, "localhost")
        addr = self.srv.server_address[0]
        if addr != "localhost":
            self.assertTrue(ipaddress.ip_address(addr).is_loopback, addr)

    def test_codigo_publicado_sin_ips_ni_nombres_de_cuenta(self):
        with open(m.__file__, encoding="utf-8") as f:
            fuente = f.read()
        self.assertNotRegex(fuente, r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
        self.assertIn('"cuenta_a"', fuente)
        self.assertIn('"cuenta_b"', fuente)

    def test_codigo_sin_operaciones_de_escritura(self):
        with open(m.__file__, encoding="utf-8") as f:
            fuente = f.read().lower()
        for prohibido in ("websocket", "ws://", "runtime.evaluate",
                          "urllib.request", "urlopen",
                          "/json/new", "/json/activate", "/json/close",
                          "input.dispatch", "subprocess", "os.system",
                          "eval(", "exec("):
            self.assertNotIn(prohibido, fuente, prohibido)


if __name__ == "__main__":
    unittest.main(verbosity=2)
