#!/usr/bin/env python3
"""Higiene de lo que se publica: sin IPs, hostnames reales, correos,
telefonos, tokens ni operaciones prohibidas.

Lista negra adicional (nombres de personas, empresas, cuentas): se pasa SOLO
por entorno al correr la prueba antes de publicar, para no escribirla aqui:
  MCP_PALABRAS_PROHIBIDAS='palabra1|palabra2' python3 -m unittest test_higiene
"""
import ast
import os
import re
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
PUBLICADOS = sorted(
    n for n in os.listdir(AQUI)
    if os.path.isfile(os.path.join(AQUI, n))
    and (n.endswith((".py", ".json", ".md")) or n in ("env.ejemplo",
                                                      ".gitignore"))
    and not n.startswith("inspeccion_ro.") or n == "inspeccion_ro.py")
DOMINIOS_PERMITIDOS = {"web.whatsapp.com"}
CON_PAGINA = ("capa_wa.py", "selectores_wa.py", "borradores.py")


def leer(nombre):
    with open(os.path.join(AQUI, nombre), encoding="utf-8") as f:
        return f.read()


LOCAL_IP = ".".join(["127", "0", "0", "1"])   # no escrito literal aqui


def hallados(patron, texto, permitido=lambda x: False):
    return [x.group(0) for x in re.finditer(patron, texto)
            if not permitido(x.group(0))]


class Publicable(unittest.TestCase):
    def test_hay_archivos(self):
        for n in ("estado_mcp.py", "capa_wa.py", "enviar_borrador.py",
                  "inspeccion_ro.py", "README.md", "env.ejemplo",
                  "selectores.ejemplo.json"):
            self.assertIn(n, PUBLICADOS)

    def test_sin_ips(self):
        for n in PUBLICADOS:
            t = leer(n)
            self.assertEqual(hallados(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", t), [], n)
            self.assertFalse(LOCAL_IP in t, n)
            self.assertEqual(hallados(r"(?i)\b(?:[0-9a-f]{1,4}:){4,}", t), [], n)

    def test_sin_hostnames_reales(self):
        patron = (r"(?i)\b(?:[a-z0-9-]+\.)+(?:com|net|org|mx|io|dev|app|cloud"
                  r"|co|ai|me|info|biz|xyz|site|online)\b")
        for n in PUBLICADOS:
            self.assertEqual(hallados(patron, leer(n),
                                      lambda d: d.lower() in DOMINIOS_PERMITIDOS),
                             [], n)

    def test_sin_correos_telefonos_ni_tokens(self):
        for n in PUBLICADOS:
            t = leer(n)
            self.assertEqual(hallados(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", t,
                                      lambda x: x.lower().endswith(".test")),
                             [], n)
            self.assertEqual(hallados(r"\+\d[\d ]{9,}", t), [], n)
            self.assertEqual(hallados(r"\b\d{10,}\b", t), [], n)
            self.assertEqual(hallados(
                r"\b(?:eyJ[\w-]{10,}|gh[pousr]_\w{20,}|sk-\w{20,}|xox[abp]-)",
                t), [], n)
            self.assertEqual(hallados(r"\b[0-9a-f]{32,}\b", t), [], n)

    def test_sin_tunel_ni_archivos_de_setup(self):
        for n in os.listdir(AQUI):
            self.assertFalse(n.endswith((".plist", ".zip", ".bak", "~",
                                         ".yml", ".yaml", ".pem", ".key")), n)
            self.assertNotIn("cloud" + "flared", n.lower())
        prohibidos = ["cloud" + "flared", "tunnel" + ":", "credentials" +
                      "-file", "try" + "cloud" + "flare"]
        for n in PUBLICADOS:
            t = leer(n).lower()
            for p in prohibidos:
                self.assertFalse(p in t, n)

    def test_env_ejemplo_sin_valores_sensibles(self):
        valores = dict(l.split("=", 1) for l in leer("env.ejemplo").splitlines()
                       if l and not l.startswith("#"))
        self.assertEqual(valores["MCP_MARCAS_CUENTA_A"], "")
        self.assertEqual(valores["MCP_HOST_PUBLICO"], "")

    def test_ejemplo_de_selectores_vacio(self):
        import json
        datos = json.loads(leer("selectores.ejemplo.json"))
        for clave, spec in datos.items():
            if isinstance(spec, dict):
                for k in ("css", "role", "name", "testid", "texto", "aria",
                          "saliente_css", "entrante_css"):
                    self.assertEqual(spec.get(k, ""), "", (clave, k))

    def test_palabras_prohibidas_por_entorno(self):
        palabras = [p.strip().lower() for p in os.environ.get(
            "MCP_PALABRAS_PROHIBIDAS", "").split("|") if p.strip()]
        if not palabras:
            self.skipTest("MCP_PALABRAS_PROHIBIDAS no definida")
        for n in PUBLICADOS:
            t = leer(n).lower()
            encontradas = [i for i, p in enumerate(palabras) if p in t]
            self.assertEqual(encontradas, [], n)   # solo indices, sin texto


class ServidorSinEnvio(unittest.TestCase):
    def test_servidor_sin_ws_ni_envio(self):
        t = leer("estado_mcp.py")
        for p in ("websocket", "ws://", LOCAL_IP, ".press(", '"Enter"',
                  "connect_over_cdp", "playwright", "subprocess",
                  "os.system", "goto("):
            self.assertFalse(p in t, p)

    def test_capa_sin_teclas_de_envio_ni_navegacion(self):
        for n in CON_PAGINA:
            t = leer(n)
            for p in (".press(", "Enter", '"envio"', "goto(", ".launch(",
                      "launch_persistent_context", "new_page", "reload(",
                      LOCAL_IP, "ws://", "dispatch_event",
                      "keyboard.type", "keyboard.down"):
                self.assertFalse(p in t, (n, p))

    def test_capa_solo_conecta_a_localhost(self):
        t = leer("capa_wa.py")
        urls = re.findall(r'"(https?://[^"]*)"', t)
        self.assertEqual(urls, ["http://localhost:%d"])

    def test_inspeccion_solo_lectura(self):
        t = leer("inspeccion_ro.py")
        for p in (".click(", ".fill(", ".press(", ".hover(", ".focus(",
                  ".type(", "goto(", ".launch(", "insert_text",
                  LOCAL_IP, ".innerText.slice", "title:"):
            self.assertFalse(p in t, p)
        arbol = ast.parse(t)
        js = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant)
              and isinstance(n.value, str) and "=>" in n.value]
        self.assertTrue(js)
        for codigo in js:
            for p in (".click(", ".focus(", "dispatchEvent", "scrollTop =",
                      ".value =", "innerHTML =", "fetch(", "localStorage"):
                self.assertFalse(p in codigo, p)

    def test_solo_el_cli_pulsa_enviar(self):
        con_press = [n for n in PUBLICADOS
                     if n.endswith(".py") and ".press(" in leer(n)
                     and not n.startswith(("test_", "simulador_"))]
        self.assertEqual(con_press, ["enviar_borrador.py"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
