"""Simulador minimo de la API sincrona de Playwright para las pruebas.

No abre navegadores, no usa red y no conoce WhatsApp real. Modela una
pestana de "web.whatsapp.com" con un DOM ficticio cuyos selectores son
claves de texto: "css:<selector>", "role:<rol>:<nombre>", "testid:<v>",
"texto:<v>", "aria:<v>". Registra cada accion para que las pruebas puedan
verificar que no hubo clics, teclas o envios donde no debia.
"""
import contextlib

import capa_wa


class TimeoutError(Exception):   # mismo nombre que el de Playwright
    pass


class Elemento:
    def __init__(self, nombre, texto="", attrs=None, hijos=None, clases=(),
                 al_clic=None, al_scroll=None, al_tecla=None):
        self.nombre = nombre
        self.texto = texto
        self.attrs = attrs or {}
        self.hijos = hijos or {}      # clave -> lista o funcion
        self.clases = set(clases)
        self.al_clic = al_clic
        self.al_scroll = al_scroll
        self.al_tecla = al_tecla


def _lista(v):
    return list(v() if callable(v) else v)


class Buscador:
    """Metodos comunes de Page y Locator para crear localizadores."""

    def _hijos(self, clave):
        raise NotImplementedError

    def locator(self, css):
        return Locator(self.pagina, lambda: self._hijos("css:" + css))

    def get_by_role(self, role, name=None, exact=False):
        return Locator(self.pagina,
                       lambda: self._hijos("role:%s:%s" % (role, name or "")))

    def get_by_test_id(self, v):
        return Locator(self.pagina, lambda: self._hijos("testid:" + v))

    def get_by_text(self, v, exact=False):
        return Locator(self.pagina, lambda: self._hijos("texto:" + v))

    def get_by_label(self, v, exact=False):
        return Locator(self.pagina, lambda: self._hijos("aria:" + v))


class Locator(Buscador):
    def __init__(self, pagina, obtener):
        self.pagina = pagina
        self._obtener = obtener

    def _els(self):
        return self._obtener()

    def _uno(self):
        els = self._els()
        if not els:
            raise TimeoutError("sin elemento")
        return els[0]

    def _hijos(self, clave):
        out = []
        for el in self._els():
            out += _lista(el.hijos.get(clave, []))
        return out

    def _r(self, *accion):
        self.pagina.registro.append(accion)

    @property
    def first(self):
        return Locator(self.pagina, lambda: self._els()[:1])

    def nth(self, i):
        return Locator(self.pagina, lambda: self._els()[i:i + 1])

    def count(self):
        self._r("count")
        return len(self._els())

    def inner_text(self, timeout=None):
        el = self._uno()
        self._r("inner_text", el.nombre)
        return el.texto

    def get_attribute(self, a):
        el = self._uno()
        self._r("get_attribute", el.nombre, a)
        return el.attrs.get(a)

    def wait_for(self, state="visible", timeout=None):
        if not self._els():
            raise TimeoutError("no aparecio")

    def click(self, timeout=None):
        el = self._uno()
        self._r("click", el.nombre)
        if el.al_clic:
            el.al_clic()

    def fill(self, texto, timeout=None):
        el = self._uno()
        self._r("fill", el.nombre, texto)
        el.texto = self.pagina.alterar_fill(texto)

    def press(self, tecla, timeout=None):
        el = self._uno()
        self._r("press", el.nombre, tecla)
        if el.al_tecla:
            el.al_tecla(tecla)

    def evaluate(self, js, arg=None):
        el = self._uno()
        if js == capa_wa.JS_COINCIDE:
            self._r("evaluate_lectura", el.nombre)
            return arg.lstrip(".") in el.clases
        if js == capa_wa.JS_SCROLL_ARRIBA:
            self._r("scroll", el.nombre)
            if el.al_scroll:
                el.al_scroll()
            return True
        raise AssertionError("script no esperado")


class Teclado:
    def __init__(self, pagina):
        self.pagina = pagina

    def insert_text(self, texto):
        self.pagina.registro.append(("insert_text", texto))
        comp = self.pagina.compositor_activo()
        if comp is not None:
            comp.texto = texto

    def press(self, tecla):
        self.pagina.registro.append(("keyboard.press", tecla))
        comp = self.pagina.compositor_activo()
        if comp is not None and comp.al_tecla:
            comp.al_tecla(tecla)


class Descarga:
    def __init__(self, nombre, contenido):
        self.suggested_filename = nombre
        self._contenido = contenido

    def save_as(self, ruta):
        with open(ruta, "wb") as f:
            f.write(self._contenido)


class InfoDescarga:
    def __init__(self, pagina):
        self._pagina = pagina

    @property
    def value(self):
        d = self._pagina.descarga_lista
        if d is None:
            raise TimeoutError("sin descarga")
        return d


class Pagina(Buscador):
    def __init__(self, url="https://web.whatsapp.com/"):
        self.pagina = self
        self.url = url
        self.registro = []
        self.dom = {}                 # clave -> lista o funcion
        self.texto_cuerpo = ""
        self.keyboard = Teclado(self)
        self.descarga_lista = None
        self.alterar_fill = lambda t: t
        self.compositor_activo = lambda: None

    def _hijos(self, clave):
        return _lista(self.dom.get(clave, []))

    def evaluate(self, js, arg=None):
        if js == capa_wa.JS_MARCAS:
            self.registro.append(("evaluate_lectura", "marcas"))
            return [m in self.texto_cuerpo for m in arg]
        raise AssertionError("script no esperado")

    def wait_for_timeout(self, ms):
        self.registro.append(("espera", ms))

    @contextlib.contextmanager
    def expect_download(self, timeout=None):
        self.descarga_lista = None
        yield InfoDescarga(self)

    def goto(self, *a, **k):          # existe para detectar mal uso
        self.registro.append(("goto",))
        raise AssertionError("goto prohibido")

    def acciones(self):
        """Acciones que modifican la pagina (no lecturas)."""
        mutables = {"click", "fill", "press", "insert_text", "keyboard.press",
                    "scroll", "goto"}
        return [a for a in self.registro if a[0] in mutables]


class Contexto:
    def __init__(self, paginas):
        self.pages = paginas


class Navegador:
    def __init__(self, paginas):
        self.contexts = [Contexto(paginas)]
        self.conectado = True

    def is_connected(self):
        return self.conectado

    def close(self):
        self.conectado = False


class Chromium:
    def __init__(self, destinos):
        self.destinos = destinos      # url -> funcion que crea Navegador
        self.conexiones = []

    def connect_over_cdp(self, url, timeout=None):
        self.conexiones.append(url)
        if url not in self.destinos:
            raise ConnectionError("nadie escucha")
        return self.destinos[url]()

    def launch(self, *a, **k):
        raise AssertionError("launch prohibido")

    launch_persistent_context = launch


class Playwright:
    def __init__(self, destinos):
        self.chromium = Chromium(destinos)
        self.detenido = False

    def stop(self):
        self.detenido = True


# ---------------------------------------------- WhatsApp ficticio -------

SELECTORES_PRUEBA = {
    "lista_chats": {"css": "#lista"},
    "item_chat": {"css": '[title="{nombre}"]'},
    "encabezado_chat": {"css": 'header [title="{nombre}"]'},
    "panel_mensajes": {"css": "#panel"},
    "mensaje": {"css": ".fila"},
    "mensaje_texto": {"css": ".texto"},
    "mensaje_hora": {"css": ".hora"},
    "direccion": {"saliente_css": ".sale", "entrante_css": ".entra"},
    "cargar_mas": {"modo": "scroll"},
    "adjunto": {"css": ".adj"},
    "adjunto_nombre": {"css": ".adj-nombre"},
    "boton_descargar": {"css": ".adj-bajar"},
    "compositor": {"css": "footer .caja", "modo_escritura": "fill"},
    "envio": {"modo": "enter"},
}


class WhatsAppFicticio:
    """Dos chats ficticios. Pulsar Enter con texto en el compositor 'envia'
    (se anota en self.enviados) para poder probar que NO ocurre."""

    def __init__(self, texto_cuerpo):
        self.pagina = Pagina()
        self.pagina.texto_cuerpo = texto_cuerpo
        self.activo = None
        self.enviados = []
        self.chats = {
            "Chat Uno": [("entra", "hola", "10:00", None),
                         ("sale", "que tal", "10:01", None),
                         ("entra", "", "10:02", ("informe.pdf", b"PDF-FICTICIO")),
                         ("sale", "listo", "10:03", None)],
            "Chat Dos": [("entra", "otro chat", "09:00", None)],
        }
        self.antiguos = {"Chat Uno": [("entra", "mensaje viejo", "08:00",
                                       None)]}
        self.compositores = {n: Elemento("compositor:" + n,
                                         al_tecla=self._tecla(n))
                             for n in self.chats}
        p = self.pagina
        p.dom["css:#lista"] = [Elemento("lista")]
        for nombre in self.chats:
            p.dom['css:[title="%s"]' % nombre] = [
                Elemento("item:" + nombre, al_clic=self._abrir(nombre))]
            p.dom['css:header [title="%s"]' % nombre] = self._si_activo(
                nombre)
        p.dom["css:#panel"] = lambda: ([Elemento(
            "panel", al_scroll=self._cargar_antiguos)] if self.activo else [])
        p.dom["css:.fila"] = self._filas
        p.dom["css:footer .caja"] = lambda: (
            [self.compositores[self.activo]] if self.activo else [])
        p.compositor_activo = lambda: (
            self.compositores[self.activo] if self.activo else None)

    def _abrir(self, nombre):
        def f():
            self.activo = nombre
        return f

    def _si_activo(self, nombre):
        return lambda: ([Elemento("encabezado")]
                        if self.activo == nombre else [])

    def _tecla(self, nombre):
        def f(tecla):
            comp = self.compositores[nombre]
            if tecla == "Enter" and comp.texto:
                self.enviados.append((nombre, comp.texto))
                self.chats[nombre].append(("sale", comp.texto, "11:00", None))
                comp.texto = ""
        return f

    def _cargar_antiguos(self):
        viejos = self.antiguos.pop(self.activo, [])
        self.chats[self.activo][:0] = viejos

    def _filas(self):
        if not self.activo:
            return []
        filas = []
        for i, (dir_, texto, hora, adj) in enumerate(self.chats[self.activo]):
            hijos = {"css:.texto": [Elemento("texto", texto)] if texto else [],
                     "css:.hora": [Elemento("hora", hora)]}
            if adj:
                nombre, datos = adj
                hijos["css:.adj"] = [Elemento("adjunto", hijos={
                    "css:.adj-nombre": [Elemento("adj-nombre", nombre)],
                    "css:.adj-bajar": [Elemento(
                        "adj-bajar", al_clic=self._descarga(nombre, datos))]})]
            filas.append(Elemento("fila%d" % i, attrs={"data-id": "m%d" % i},
                                  hijos=hijos, clases=[dir_]))
        return filas

    def _descarga(self, nombre, datos):
        def f():
            self.pagina.descarga_lista = Descarga(nombre, datos)
        return f
