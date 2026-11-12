#!/usr/bin/env python3
"""Herramientas nuevas por HTTP /mcp, con Chrome simulado (HTTPServer para
/json/*) y Playwright simulado. Sin WhatsApp real ni puertos 9222/9223."""
import http.client
import io
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import borradores
import capa_wa
import estado_mcp as m
import simulador_pw as sim
from test_capa_wa import BaseSim


class JsonChrome(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/json/version":
            c = {"Browser": "Chrome/TEST"}
        else:
            c = [{"type": "page", "url": "https://web.whatsapp.com/",
                  "title": "Titulo Privado"}]
        d = json.dumps(c).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(d)))
        self.end_headers()
        self.wfile.write(d)


class HerramientasHTTP(BaseSim):
    def setUp(self):
        super().setUp()
        self.chrome_a = HTTPServer(("localhost", 0), JsonChrome)
        self.chrome_b = HTTPServer(("localhost", 0), JsonChrome)
        for c in (self.chrome_a, self.chrome_b):
            threading.Thread(target=c.serve_forever, daemon=True).start()
        pa, pb = (self.chrome_a.server_address[1],
                  self.chrome_b.server_address[1])
        self.destinos.clear()
        self.destinos["http://localhost:%d" % pa] = lambda: sim.Navegador(
            [self.wa_a.pagina])
        self.destinos["http://localhost:%d" % pb] = lambda: sim.Navegador(
            [self.wa_b.pagina])
        self._cuentas = dict(m.CUENTAS)
        m.CUENTAS.update({"cuenta_a": pa, "cuenta_b": pb})
        m._CAPA.clear()
        self.log = io.StringIO()
        m.SALIDA_LOG = self.log
        self.srv = m.crear_servidor(0)
        self.puerto = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        for c in (self.chrome_a, self.chrome_b):
            c.shutdown()
            c.server_close()
        if m._CAPA:
            m._CAPA[0].cerrar()
        m._CAPA.clear()
        m.CUENTAS.clear()
        m.CUENTAS.update(self._cuentas)
        super().tearDown()

    def llamar(self, nombre, args):
        cuerpo = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": nombre, "arguments": args}})
        c = http.client.HTTPConnection("localhost", self.puerto, timeout=20)
        try:
            c.request("POST", "/mcp", body=cuerpo,
                      headers={"Content-Type": "application/json"})
            r = c.getresponse()
            return r.status, json.loads(r.read().decode())
        finally:
            c.close()

    def resultado(self, nombre, args):
        s, r = self.llamar(nombre, args)
        self.assertEqual(s, 200)
        self.assertIn("result", r, r)
        return r["result"]["structuredContent"], r["result"]["isError"]

    def sin_envios(self):
        for wa in (self.wa_a, self.wa_b):
            self.assertEqual(wa.enviados, [])
            for accion in wa.pagina.registro:
                self.assertNotIn(accion[0], ("press", "keyboard.press"))

    def test_estado_navegador_igual(self):
        res, err = self.resultado("estado_navegador", {"cuenta": "cuenta_a"})
        self.assertEqual(res, {"cuenta": "cuenta_a", "chrome_responde": True,
                               "version_chrome": "Chrome/TEST",
                               "pestanas_whatsapp": 1})
        self.assertEqual(self.pw.chromium.conexiones, [])   # sin CDP

    def test_identidad_sin_clics_ni_pii(self):
        res, err = self.resultado("identidad_cuenta", {"cuenta": "cuenta_a"})
        self.assertFalse(err)
        self.assertTrue(res["chrome_responde"])
        self.assertTrue(res["coincide_marcas"])
        self.assertTrue(res["coincide_cuenta"])
        self.assertEqual(res["cuenta_detectada"], "cuenta_a")
        self.assertEqual(self.wa_a.pagina.acciones(), [])
        res_b, _ = self.resultado("identidad_cuenta", {"cuenta": "cuenta_b"})
        self.assertEqual(res_b["cuenta_detectada"], "cuenta_b")
        todo = json.dumps([res, res_b]) + self.log.getvalue()
        for prohibido in ("Marca Ficticia", "Chat Uno", "Titulo Privado"):
            self.assertNotIn(prohibido, todo)

    def test_leer(self):
        res, err = self.resultado("leer", {"cuenta": "cuenta_a",
                                           "destchat": "Chat Uno",
                                           "limite": 2})
        self.assertFalse(err)
        self.assertEqual([x["texto"] for x in res["mensajes"]],
                         [None, "listo"])
        log = self.log.getvalue()
        self.assertNotIn("Chat Uno", log)
        self.assertNotIn("listo", log)
        self.sin_envios()

    def test_leer_limite_por_defecto_y_validacion(self):
        res, _ = self.resultado("leer", {"cuenta": "cuenta_a",
                                         "destchat": "Chat Uno"})
        self.assertEqual(len(res["mensajes"]), 4)
        for args in ({"cuenta": "cuenta_a", "destchat": "Chat Uno",
                      "limite": 0},
                     {"cuenta": "cuenta_a", "destchat": "Chat Uno",
                      "limite": True},
                     {"cuenta": "cuenta_a", "destchat": ""},
                     {"cuenta": "cuenta_a", "destchat": "a\nb"},
                     {"cuenta": "cuenta_a"}):
            s, r = self.llamar("leer", args)
            self.assertEqual(r["error"]["code"], -32602, args)

    def test_cargar_mas(self):
        res, err = self.resultado("cargar_mas", {"cuenta": "cuenta_a",
                                                 "destchat": "Chat Uno"})
        self.assertFalse(err)
        self.assertEqual(res["gesto"], "scroll")
        self.assertEqual(res["mensajes_despues"], 5)
        self.sin_envios()

    def test_descargar(self):
        res, err = self.resultado("descargar", {"cuenta": "cuenta_a",
                                                "destchat": "Chat Uno",
                                                "id_o_nombre": "informe.pdf"})
        self.assertFalse(err)
        self.assertEqual(res["archivo"], "informe.pdf")
        self.assertNotIn(self.tmp.name, json.dumps(res))

    def test_preparar_no_envia(self):
        res, err = self.resultado("preparar", {"cuenta": "cuenta_b",
                                               "destinatario": "Chat Dos",
                                               "texto": "hola exacto"})
        self.assertFalse(err)
        self.assertEqual(res["estado"], "pendiente")
        self.assertEqual(self.wa_b.compositores["Chat Dos"].texto,
                         "hola exacto")
        self.assertEqual(borradores.leer(res["borrador_id"])["estado"],
                         "pendiente")
        self.assertNotIn("hola exacto", self.log.getvalue())
        self.sin_envios()

    def test_error_de_selector_es_claro(self):
        self.selectores_sin("compositor")
        res, err = self.resultado("preparar", {"cuenta": "cuenta_a",
                                               "destinatario": "Chat Dos",
                                               "texto": "hola"})
        self.assertTrue(err)
        self.assertEqual(res["error"], "selector_faltante")
        self.assertIn("compositor", res["detalle"])

    def test_no_existe_ninguna_forma_de_enviar(self):
        self.resultado("preparar", {"cuenta": "cuenta_a",
                                    "destinatario": "Chat Dos",
                                    "texto": "hola"})
        for nombre in ("enviar", "enviar_borrador", "enviar_mensaje", "send",
                       "send_message", "confirmar", "publicar"):
            for args in ({"cuenta": "cuenta_a"},
                         {"cuenta": "cuenta_a", "borrador_id": "0" * 32}):
                s, r = self.llamar(nombre, args)
                self.assertEqual(r["error"]["code"], -32602, nombre)
        for nombre in ("preparar", "leer"):
            s, r = self.llamar(nombre, {"cuenta": "cuenta_a",
                                        "destinatario": "Chat Dos",
                                        "destchat": "Chat Dos",
                                        "texto": "hola", "enviar": True})
            self.assertEqual(r["error"]["code"], -32602)
        self.sin_envios()
        self.assertEqual(self.wa_a.compositores["Chat Dos"].texto, "hola")

    def test_tools_list_no_menciona_envio_posible(self):
        self.assertNotIn("enviar", [h["name"] for h in m.HERRAMIENTAS])
        for h in m.HERRAMIENTAS:
            self.assertNotIn("borrador_id", h["inputSchema"]["properties"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
