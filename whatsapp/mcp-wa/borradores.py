"""Almacen local de borradores (un archivo JSON por borrador).

El servidor MCP solo CREA borradores en estado "pendiente". Unicamente el CLI
local enviar_borrador.py los pasa a "enviando" y "enviado".
Directorio: MCP_DIR_BORRADORES (por defecto ./borradores).
"""
import json
import os
import re
import secrets
import time

PATRON_ID = re.compile(r"^[0-9a-f]{32}$")


def directorio():
    d = os.environ.get("MCP_DIR_BORRADORES") or os.path.join(
        os.getcwd(), "borradores")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def _ruta(borrador_id):
    if not isinstance(borrador_id, str) or not PATRON_ID.match(borrador_id):
        raise ValueError("borrador_id invalido")
    return os.path.join(directorio(), borrador_id + ".json")


def _escribir(ruta, datos):
    tmp = ruta + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def crear(cuenta, destinatario, texto):
    borrador = {
        "borrador_id": secrets.token_hex(16),
        "cuenta": cuenta,
        "destinatario": destinatario,
        "texto": texto,
        "estado": "pendiente",
        "creado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    _escribir(_ruta(borrador["borrador_id"]), borrador)
    return borrador


def leer(borrador_id):
    with open(_ruta(borrador_id), encoding="utf-8") as f:
        return json.load(f)


def cambiar_estado(borrador_id, estado, **extra):
    b = leer(borrador_id)
    b["estado"] = estado
    b["actualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    b.update(extra)
    _escribir(_ruta(borrador_id), b)
    return b
