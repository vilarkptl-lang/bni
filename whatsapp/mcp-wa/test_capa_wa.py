#!/usr/bin/env python3
"""Pruebas de capa_wa con el simulador de Playwright (simulador_pw).
Nunca usan un Chrome real, los puertos 9222/9223 ni WhatsApp."""
import json
import os
import tempfile
import unittest

import borradores
import capa_wa
import selectores_wa as sw
import simulador_pw as sim
from selectores_wa import ErrorWA

MARCAS = "Marca Ficticia Uno|Marca Ficticia Dos"
CUERPO_A = "lista de chats Marca Ficticia Uno y Marca Ficticia Dos"
CUERPO_B = "lista de chats sin las marcas"
ENTORNO = ("MCP_MARCAS_CUENTA_A", "MCP_SELECTORES", "MCP_DIR_DESCARGAS",
           "MCP_DIR_BORRADORES", "MCP_ESPERA_CARGA_MS", "MCP_PLAZO_ACCION_MS")


class BaseSim(unittest.TestCase):
    selectores = None

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in ENTORNO}
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        os.environ["MCP_MARCAS_CUENTA_A"] = MARCAS
        os.environ["MCP_DIR_DESCARGAS"] = os.path.join(d, "descargas")
        os.environ["MCP_DIR_BORRADORES"] = os.path.join(d, "borradores")
        os.environ["MCP_ESPERA_CARGA_MS"] = "1"
        os.environ["MCP_PLAZO_ACCION_MS"] = "50"
        self.escribir_selectores(self.selectores or sim.SELECTORES_PRUEBA)
        self.wa_a = sim.WhatsAppFicticio(CUERPO_A)
        self.wa_b = sim.WhatsAppFicticio(CUERPO_B)
        self.destinos = {
            "http://localhost:41001": lambda: sim.Navegador([self.wa_a.pagina]),
            "http://localhost:41002": lambda: sim.Navegador([self.wa_b.pagina]),
        }
        self.pw = sim.Playwright(self.destinos)
        self._iniciar = capa_wa.iniciar_playwright
        capa_wa.iniciar_playwright = lambda: self.pw
        self.capa = capa_wa.Capa({"cuenta_a": 41001, "cuenta_b": 41002},
                                 plazo=10)

    def tearDown(self):
        self.capa.cerrar()
        capa_wa.iniciar_playwright = self._iniciar
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def escribir_selectores(self, datos):
        ruta = os.path.join(self.tmp.name, "selectores.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f)
        os.environ["MCP_SELECTORES"] = ruta

    def selectores_sin(self, *claves, **cambios):
        d = json.loads(json.dumps(sim.SELECTORES_PRUEBA))
        for c in claves:
            d.pop(c, None)
        d.update(cambios)
        self.escribir_selectores(d)

    def assertCodigo(self, codigo, fn, *a):
        with self.assertRaises(ErrorWA) as ctx:
            fn(*a)
        self.assertEqual(ctx.exception.codigo, codigo, ctx.exception.detalle)
        return ctx.exception


class Identidad(BaseSim):
    def test_cuenta_a_por_marcas_sin_clics(self):
        r = self.capa.identidad("cuenta_a")
        self.assertTrue(r["coincide_marcas"])
        self.assertEqual(r["cuenta_detectada"], "cuenta_a")
        self.assertEqual(r["marcas_configuradas"], 2)
        self.assertEqual(self.wa_a.pagina.acciones(), [])
        self.assertNotIn("Marca Ficticia", json.dumps(r))

    def test_cuenta_b_sin_marcas(self):
        r = self.capa.identidad("cuenta_b")
        self.assertFalse(r["coincide_marcas"])
        self.assertTrue(r["lista_chats_visible"])
        self.assertEqual(r["cuenta_detectada"], "cuenta_b")
        self.assertEqual(self.wa_b.pagina.acciones(), [])

    def test_una_marca_sola_no_basta(self):
        self.wa_a.pagina.texto_cuerpo = "solo Marca Ficticia Uno"
        self.assertEqual(self.capa.identidad("cuenta_a")["cuenta_detectada"],
                         "cuenta_b")

    def test_sin_marcas_configuradas(self):
        os.environ["MCP_MARCAS_CUENTA_A"] = ""
        r = self.capa.identidad("cuenta_a")
        self.assertIsNone(r["coincide_marcas"])
        self.assertEqual(r["cuenta_detectada"], "desconocida")
        self.assertCodigo("marcas_no_configuradas", self.capa.leer,
                          "cuenta_a", "Chat Uno", 10)
        self.assertEqual(self.wa_a.pagina.acciones(), [])

    def test_conecta_solo_a_localhost_y_no_lanza(self):
        self.capa.identidad("cuenta_a")
        self.capa.identidad("cuenta_a")
        self.assertEqual(self.pw.chromium.conexiones,
                         ["http://localhost:41001"])   # conexion persistente

    def test_reconecta_si_se_cae(self):
        self.capa.identidad("cuenta_a")
        self.capa._nav["cuenta_a"].conectado = False
        self.capa.identidad("cuenta_a")
        self.assertEqual(len(self.pw.chromium.conexiones), 2)

    def test_chrome_caido(self):
        self.capa.cuentas["cuenta_a"] = 41999
        self.assertCodigo("chrome_no_responde", self.capa.identidad,
                          "cuenta_a")

    def test_sin_pestana_o_varias(self):
        self.destinos["http://localhost:41001"] = lambda: sim.Navegador(
            [sim.Pagina("https://otra.test/")])
        self.assertCodigo("sin_pestana_whatsapp", self.capa.identidad,
                          "cuenta_a")
        self.capa._nav.clear()
        self.destinos["http://localhost:41001"] = lambda: sim.Navegador(
            [sim.Pagina(), sim.Pagina()])
        self.assertCodigo("varias_pestanas_whatsapp", self.capa.identidad,
                          "cuenta_a")


class Leer(BaseSim):
    def test_abre_chat_y_lee(self):
        r = self.capa.leer("cuenta_a", "Chat Uno", 30)
        self.assertEqual(self.wa_a.pagina.acciones(),
                         [("click", "item:Chat Uno")])
        self.assertEqual(r["total_visibles"], 4)
        m = r["mensajes"]
        self.assertEqual(m[0], {"posicion": 0, "texto": "hola",
                                "hora": "10:00", "direccion": "entrante"})
        self.assertEqual(m[1]["direccion"], "saliente")
        self.assertEqual(m[2]["texto"], None)
        self.assertEqual(m[2]["adjunto"], {"nombre": "informe.pdf"})

    def test_limite_toma_los_ultimos(self):
        r = self.capa.leer("cuenta_a", "Chat Uno", 2)
        self.assertEqual([x["texto"] for x in r["mensajes"]],
                         [None, "listo"])

    def test_chat_ya_abierto_no_hace_clic(self):
        self.wa_a.activo = "Chat Uno"
        self.capa.leer("cuenta_a", "Chat Uno", 5)
        self.assertEqual(self.wa_a.pagina.acciones(), [])

    def test_no_inventa_campos(self):
        self.selectores_sin("mensaje_hora", "direccion", "adjunto")
        r = self.capa.leer("cuenta_a", "Chat Uno", 1)
        self.assertEqual(set(r["mensajes"][0]), {"posicion", "texto"})

    def test_id_solo_si_esta_configurado(self):
        self.selectores_sin(mensaje_id_atributo="data-id")
        r = self.capa.leer("cuenta_a", "Chat Uno", 1)
        self.assertEqual(r["mensajes"][0]["id"], "m3")

    def test_chat_inexistente(self):
        self.assertCodigo("chat_no_encontrado", self.capa.leer,
                          "cuenta_a", "No Existe", 5)

    def test_cuenta_equivocada_no_toca(self):
        self.capa.cuentas["cuenta_b"] = 41001   # puerto que da cuenta_a
        self.capa._nav.clear()
        self.assertCodigo("cuenta_no_coincide", self.capa.leer,
                          "cuenta_b", "Chat Uno", 5)
        self.assertEqual(self.wa_a.pagina.acciones(), [])

    def test_selector_faltante_error_claro(self):
        self.selectores_sin("mensaje_texto")
        e = self.assertCodigo("selector_faltante", self.capa.leer,
                              "cuenta_a", "Chat Uno", 5)
        self.assertIn("mensaje_texto", e.detalle)

    def test_selector_vacio_es_faltante(self):
        self.selectores_sin(mensaje={"css": "", "role": "", "testid": ""})
        e = self.assertCodigo("selector_faltante", self.capa.leer,
                              "cuenta_a", "Chat Uno", 5)
        self.assertIn("'mensaje'", e.detalle)

    def test_ejemplo_no_sirve_como_selectores(self):
        with open(os.path.join(os.path.dirname(__file__),
                               "selectores.ejemplo.json")) as f:
            self.escribir_selectores(json.load(f))
        self.assertCodigo("selector_faltante", self.capa.leer,
                          "cuenta_a", "Chat Uno", 5)
        self.assertEqual(self.wa_a.pagina.acciones(), [])

    def test_sin_archivo(self):
        os.environ["MCP_SELECTORES"] = os.path.join(self.tmp.name, "no.json")
        self.assertCodigo("sin_archivo_selectores", self.capa.leer,
                          "cuenta_a", "Chat Uno", 5)


class CargarMas(BaseSim):
    def test_scroll(self):
        r = self.capa.cargar_mas("cuenta_a", "Chat Uno")
        self.assertEqual(r, {"gesto": "scroll", "mensajes_antes": 4,
                             "mensajes_despues": 5})
        self.assertIn(("scroll", "panel"), self.wa_a.pagina.acciones())
        self.assertEqual(self.wa_a.enviados, [])

    def test_clic(self):
        self.selectores_sin(cargar_mas={"modo": "clic", "css": "#mas"})
        self.wa_a.pagina.dom["css:#mas"] = [sim.Elemento(
            "boton-mas", al_clic=self.wa_a._cargar_antiguos)]
        r = self.capa.cargar_mas("cuenta_a", "Chat Uno")
        self.assertEqual(r["gesto"], "clic")
        self.assertIn(("click", "boton-mas"), self.wa_a.pagina.acciones())

    def test_sin_modo(self):
        self.selectores_sin(cargar_mas={"modo": ""})
        self.assertCodigo("selector_faltante", self.capa.cargar_mas,
                          "cuenta_a", "Chat Uno")

    def test_clic_sin_boton_visible(self):
        self.selectores_sin(cargar_mas={"modo": "clic", "css": "#mas"})
        self.assertCodigo("sin_boton_cargar_mas", self.capa.cargar_mas,
                          "cuenta_a", "Chat Uno")


class Descargar(BaseSim):
    def test_descarga_por_nombre(self):
        r = self.capa.descargar("cuenta_a", "Chat Uno", "informe.pdf")
        ruta = os.path.join(os.environ["MCP_DIR_DESCARGAS"], "informe.pdf")
        self.assertEqual(r, {"archivo": "informe.pdf", "bytes": 12})
        with open(ruta, "rb") as f:
            self.assertEqual(f.read(), b"PDF-FICTICIO")
        r2 = self.capa.descargar("cuenta_a", "Chat Uno", "informe.pdf")
        self.assertEqual(r2["archivo"], "informe_1.pdf")   # no sobrescribe

    def test_descarga_por_id(self):
        self.selectores_sin(mensaje_id_atributo="data-id")
        r = self.capa.descargar("cuenta_a", "Chat Uno", "m2")
        self.assertEqual(r["archivo"], "informe.pdf")

    def test_nombre_peligroso_se_sanea(self):
        self.wa_a.chats["Chat Uno"][2] = ("entra", "", "10:02",
                                          ("../../x.sh", b"x"))
        r = self.capa.descargar("cuenta_a", "Chat Uno", "../../x.sh")
        self.assertEqual(r["archivo"], "x.sh")
        self.assertTrue(os.path.exists(os.path.join(
            os.environ["MCP_DIR_DESCARGAS"], "x.sh")))
        self.assertEqual(capa_wa.nombre_seguro("..\\..\\.env"), "env")

    def test_no_encontrado(self):
        self.assertCodigo("adjunto_no_encontrado", self.capa.descargar,
                          "cuenta_a", "Chat Uno", "otro.pdf")

    def test_sin_selector_boton(self):
        self.selectores_sin("boton_descargar")
        self.assertCodigo("selector_faltante", self.capa.descargar,
                          "cuenta_a", "Chat Uno", "informe.pdf")


class Preparar(BaseSim):
    def test_deja_texto_y_no_envia(self):
        texto = "Texto de prueba\ncon dos lineas"
        r = self.capa.preparar("cuenta_a", "Chat Dos", texto)
        self.assertEqual(r["estado"], "pendiente")
        self.assertEqual((r["cuenta"], r["destinatario"], r["texto"]),
                         ("cuenta_a", "Chat Dos", texto))
        self.assertRegex(r["borrador_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(self.wa_a.compositores["Chat Dos"].texto, texto)
        self.assertEqual(self.wa_a.enviados, [])
        tipos = [a[0] for a in self.wa_a.pagina.acciones()]
        self.assertEqual(tipos, ["click", "fill"])
        self.assertNotIn("press", tipos)
        guardado = borradores.leer(r["borrador_id"])
        self.assertEqual(guardado["estado"], "pendiente")
        self.assertEqual(guardado["texto"], texto)

    def test_modo_insertar_sin_teclas(self):
        comp = dict(sim.SELECTORES_PRUEBA["compositor"],
                    modo_escritura="insertar")
        self.selectores_sin(compositor=comp)
        self.capa.preparar("cuenta_a", "Chat Dos", "hola")
        tipos = [a[0] for a in self.wa_a.pagina.acciones()]
        self.assertEqual(tipos, ["click", "click", "insert_text"])
        self.assertEqual(self.wa_a.enviados, [])

    def test_cuenta_equivocada(self):
        self.capa.cuentas["cuenta_a"] = 41002
        self.capa._nav.clear()
        self.assertCodigo("cuenta_no_coincide", self.capa.preparar,
                          "cuenta_a", "Chat Dos", "hola")
        self.assertEqual(self.wa_b.pagina.acciones(), [])
        self.assertFalse(os.listdir(borradores.directorio()))

    def test_compositor_ocupado_no_se_pisa(self):
        self.wa_a.compositores["Chat Dos"].texto = "otro borrador"
        self.assertCodigo("compositor_ocupado", self.capa.preparar,
                          "cuenta_a", "Chat Dos", "hola")
        self.assertEqual(self.wa_a.compositores["Chat Dos"].texto,
                         "otro borrador")

    def test_texto_alterado_no_guarda(self):
        self.wa_a.pagina.alterar_fill = lambda t: t[:-1]
        self.assertCodigo("texto_no_coincide", self.capa.preparar,
                          "cuenta_a", "Chat Dos", "hola")
        self.assertFalse(os.listdir(borradores.directorio()))
        self.assertEqual(self.wa_a.enviados, [])


class Selectores(unittest.TestCase):
    def test_escapa_nombre_en_css(self):
        p = sim.Pagina()
        visto = []
        p.locator = lambda css: visto.append(css)
        sw.localizar(p, {"css": '[title="{nombre}"]'}, 'a"b\\c')
        self.assertEqual(visto, ['[title="a\\"b\\\\c"]'])

    def test_una_sola_forma(self):
        self.assertFalse(sw.es_localizador({"css": "a", "testid": "b"}))
        self.assertFalse(sw.es_localizador({"css": " "}))
        self.assertTrue(sw.es_localizador({"role": "button", "name": "x"}))

    def test_nombre_invalido(self):
        with self.assertRaises(ErrorWA):
            sw.validar_nombre("a\nb")


if __name__ == "__main__":
    unittest.main(verbosity=2)
