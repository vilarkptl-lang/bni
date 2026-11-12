#!/usr/bin/env python3
"""CLI local enviar_borrador.py con Playwright SIMULADO. Ninguna prueba
envia un mensaje real: el "envio" solo existe dentro del simulador."""
import ast
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import borradores
import capa_wa
import enviar_borrador as cli
import selectores_wa as sw
import simulador_pw as sim
from selectores_wa import ErrorWA
from test_capa_wa import BaseSim


class EnvioLocal(BaseSim):
    def preparar(self, texto="mensaje exacto", cuenta="cuenta_a",
                 chat="Chat Dos"):
        return self.capa.preparar(cuenta, chat, texto)["borrador_id"]

    def enviar(self, bid, wa=None, plataforma="darwin"):
        wa = wa or self.wa_a
        return cli.enviar(bid, wa.pagina, sw.cargar(), plataforma=plataforma)

    def sin_envio(self, wa=None):
        wa = wa or self.wa_a
        self.assertEqual(wa.enviados, [])
        self.assertNotIn("press", [a[0] for a in wa.pagina.registro])

    def test_envia_solo_tras_verificar(self):
        bid = self.preparar()
        self.wa_a.pagina.registro.clear()
        res = self.enviar(bid)
        self.assertEqual(res["estado"], "enviado")
        self.assertTrue(res["compositor_vacio"])
        self.assertEqual(self.wa_a.enviados, [("Chat Dos", "mensaje exacto")])
        reg = self.wa_a.pagina.registro
        i_press = [i for i, a in enumerate(reg) if a[0] == "press"]
        self.assertEqual(len(i_press), 1)
        antes = reg[:i_press[0]]
        # Antes de Enter: marcas, encabezado y texto del compositor leidos,
        # y ninguna otra accion sobre la pagina.
        self.assertIn(("evaluate_lectura", "marcas"), antes)
        self.assertIn(("inner_text", "compositor:Chat Dos"), antes)
        self.assertEqual([a for a in antes if a[0] in
                          ("click", "fill", "insert_text", "scroll")], [])
        self.assertEqual(reg[i_press[0]], ("press", "compositor:Chat Dos",
                                           "Enter"))
        self.assertEqual(borradores.leer(bid)["estado"], "enviado")

    def test_no_reenvia(self):
        bid = self.preparar()
        self.enviar(bid)
        self.wa_a.compositores["Chat Dos"].texto = "mensaje exacto"
        with self.assertRaises(ErrorWA) as c:
            self.enviar(bid)
        self.assertEqual(c.exception.codigo, "borrador_no_pendiente")
        self.assertEqual(len(self.wa_a.enviados), 1)

    def test_solo_mac(self):
        bid = self.preparar()
        with self.assertRaises(ErrorWA) as c:
            self.enviar(bid, plataforma="linux")
        self.assertEqual(c.exception.codigo, "solo_mac")
        self.sin_envio()
        self.assertEqual(borradores.leer(bid)["estado"], "pendiente")

    def _falla(self, codigo, bid, wa=None):
        with self.assertRaises(ErrorWA) as c:
            self.enviar(bid, wa)
        self.assertEqual(c.exception.codigo, codigo, c.exception.detalle)
        self.sin_envio(wa)
        if borradores.PATRON_ID.match(bid):
            try:
                self.assertEqual(borradores.leer(bid)["estado"], "pendiente")
            except FileNotFoundError:
                pass

    def test_texto_cambiado(self):
        bid = self.preparar()
        self.wa_a.compositores["Chat Dos"].texto = "mensaje exacto!"
        self._falla("texto_distinto", bid)

    def test_compositor_vacio(self):
        bid = self.preparar()
        self.wa_a.compositores["Chat Dos"].texto = ""
        self._falla("texto_distinto", bid)

    def test_otro_chat_abierto_no_navega(self):
        bid = self.preparar()
        self.wa_a.activo = "Chat Uno"
        self.wa_a.pagina.registro.clear()
        self._falla("chat_distinto", bid)
        self.assertEqual(self.wa_a.pagina.acciones(), [])

    def test_otra_cuenta(self):
        bid = self.preparar()
        self.wa_b.activo = "Chat Dos"
        self.wa_b.compositores["Chat Dos"].texto = "mensaje exacto"
        self._falla("cuenta_no_coincide", bid, self.wa_b)

    def test_borrador_inexistente_o_invalido(self):
        self._falla("borrador_inexistente", "0" * 32)
        self._falla("borrador_inexistente", "../../etc/passwd")

    def test_modo_boton(self):
        self.selectores_sin(envio={"modo": "boton", "css": "#enviar"})
        bid = self.preparar()
        self.wa_a.pagina.dom["css:#enviar"] = [sim.Elemento(
            "boton-enviar", al_clic=lambda: self.wa_a._tecla("Chat Dos")(
                "Enter"))]
        self.enviar(bid)
        self.assertEqual(len(self.wa_a.enviados), 1)

    def test_modo_boton_sin_boton_no_marca(self):
        self.selectores_sin(envio={"modo": "boton", "css": "#enviar"})
        bid = self.preparar()
        self._falla("sin_boton_envio", bid)


class Main(BaseSim):
    def test_requiere_bandera_explicita(self):
        with mock.patch.object(capa_wa, "iniciar_playwright",
                               side_effect=AssertionError("no debe")):
            with redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["a" * 32]), 2)
                self.assertEqual(cli.main([]), 2)
                self.assertEqual(cli.main(["a" * 32, "--si"]), 2)

    def test_fuera_de_mac_no_conecta(self):
        with mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(capa_wa, "iniciar_playwright",
                                  side_effect=AssertionError("no debe")):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(cli.main(["a" * 32, cli.BANDERA]), 1)
        self.assertEqual(json.loads(out.getvalue())["error"], "solo_mac")

    def test_main_en_mac_simulada(self):
        bid = self.capa.preparar("cuenta_a", "Chat Dos", "hola")["borrador_id"]
        destinos = {"http://localhost:%d" % cli.CUENTAS["cuenta_a"]:
                    lambda: sim.Navegador([self.wa_a.pagina])}
        pw = sim.Playwright(destinos)
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(capa_wa, "iniciar_playwright",
                                  return_value=pw):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main([bid, cli.BANDERA]), 0)
        self.assertEqual(self.wa_a.enviados, [("Chat Dos", "hola")])
        self.assertTrue(pw.detenido)
        self.assertEqual(pw.chromium.conexiones,
                         ["http://localhost:%d" % cli.CUENTAS["cuenta_a"]])


class Separacion(unittest.TestCase):
    def test_servidor_no_importa_el_cli(self):
        aqui = os.path.dirname(os.path.abspath(__file__))
        for nombre in ("estado_mcp.py", "capa_wa.py", "selectores_wa.py",
                       "borradores.py"):
            with open(os.path.join(aqui, nombre), encoding="utf-8") as f:
                arbol = ast.parse(f.read())
            importados = set()
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    importados |= {a.name for a in nodo.names}
                elif isinstance(nodo, ast.ImportFrom):
                    importados.add(nodo.module)
                elif (isinstance(nodo, ast.Call)
                      and getattr(nodo.func, "id", "") == "__import__"):
                    importados.add("__import__")
            self.assertFalse(importados & {"enviar_borrador", "__import__",
                                           "importlib"}, nombre)


if __name__ == "__main__":
    unittest.main(verbosity=2)
