"""Carga y resolucion de selectores de WhatsApp Web.

Los selectores NO estan en el codigo: salen de un archivo JSON (por defecto
./selectores.json, o la ruta de MCP_SELECTORES) que se llena a partir de una
inspeccion previa de solo lectura (inspeccion_ro.py). La forma del archivo se
documenta en selectores.ejemplo.json.

Si un selector falta o esta vacio, se lanza ErrorSelector con un mensaje
claro: nunca se adivina un selector.

Un "localizador" es un objeto con exactamente UNA de estas claves no vacias:
  css     selector CSS
  role    rol ARIA (opcional "name": nombre accesible exacto)
  testid  valor de data-testid
  texto   texto visible exacto
  aria    aria-label exacto
El marcador literal {nombre} se sustituye por el nombre del chat pedido.
"""
import json
import os

CLAVES_LOCALIZADOR = ("css", "role", "testid", "texto", "aria")
MARCADOR = "{nombre}"


class ErrorWA(Exception):
    """Error con codigo estable y detalle seguro (sin PII) para devolver."""

    def __init__(self, codigo, detalle=""):
        super().__init__(codigo)
        self.codigo = codigo
        self.detalle = detalle


class ErrorSelector(ErrorWA):
    def __init__(self, clave, motivo="falta o esta vacio"):
        super().__init__(
            "selector_faltante",
            "El selector '%s' %s en el archivo de selectores. Completalo a "
            "partir de una inspeccion previa (inspeccion_ro.py); no se "
            "adivina." % (clave, motivo))
        self.clave = clave


def ruta_selectores():
    return os.environ.get("MCP_SELECTORES") or os.path.join(
        os.getcwd(), "selectores.json")


def cargar(ruta=None):
    ruta = ruta or ruta_selectores()
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError:
        raise ErrorWA("sin_archivo_selectores",
                      "No existe el archivo de selectores. Copia "
                      "selectores.ejemplo.json a selectores.json y llenalo "
                      "con el resultado de inspeccion_ro.py.")
    except ValueError:
        raise ErrorWA("selectores_invalidos",
                      "El archivo de selectores no es JSON valido.")
    if not isinstance(datos, dict):
        raise ErrorWA("selectores_invalidos",
                      "El archivo de selectores debe ser un objeto JSON.")
    return datos


def _valor(v):
    return v.strip() if isinstance(v, str) else ""


def es_localizador(spec):
    if not isinstance(spec, dict):
        return False
    return sum(1 for k in CLAVES_LOCALIZADOR if _valor(spec.get(k))) == 1


def configurado(sel, clave):
    return es_localizador(sel.get(clave))


def localizador(sel, clave):
    spec = sel.get(clave)
    if not isinstance(spec, dict) or not any(
            _valor(spec.get(k)) for k in CLAVES_LOCALIZADOR):
        raise ErrorSelector(clave)
    if not es_localizador(spec):
        raise ErrorSelector(clave, "tiene mas de una forma de localizar")
    return spec


def texto_opcional(sel, clave):
    return _valor(sel.get(clave))


def _escapar_css(valor):
    return valor.replace("\\", "\\\\").replace('"', '\\"')


def validar_nombre(nombre):
    if (not isinstance(nombre, str) or not nombre.strip()
            or any(ord(c) < 32 for c in nombre)):
        raise ErrorWA("nombre_invalido", "Nombre de chat invalido.")
    return nombre


def localizar(raiz, spec, nombre=None):
    """Devuelve un Locator de Playwright a partir de un localizador del
    archivo. raiz puede ser una Page o un Locator."""
    def sub(v, css=False):
        v = _valor(v)
        if MARCADOR in v:
            if nombre is None:
                raise ErrorWA("selector_requiere_nombre",
                              "El selector usa {nombre} pero no se dio chat.")
            v = v.replace(MARCADOR, _escapar_css(nombre) if css else nombre)
        return v

    if _valor(spec.get("css")):
        return raiz.locator(sub(spec["css"], css=True))
    if _valor(spec.get("role")):
        nombre_acc = _valor(spec.get("name"))
        if nombre_acc:
            return raiz.get_by_role(sub(spec["role"]), name=sub(nombre_acc),
                                    exact=True)
        return raiz.get_by_role(sub(spec["role"]))
    if _valor(spec.get("testid")):
        return raiz.get_by_test_id(sub(spec["testid"]))
    if _valor(spec.get("texto")):
        return raiz.get_by_text(sub(spec["texto"]), exact=True)
    return raiz.get_by_label(sub(spec["aria"]), exact=True)
