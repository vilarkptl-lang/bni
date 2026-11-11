# Extracción de información de WhatsApp

No hay un script que recorra WhatsApp por API. La extracción de contactos para el cruce BNI se hace a mano con el navegador (computerUse), en solo lectura, siguiendo `skills/bni/SKILL.md`.

## Receta

1. Abrir WhatsApp Web en el perfil de Chrome de WhatsApp **personal**. Usar la pestaña cuyo título muestra el conteo de no leídos.
2. Nunca escribir, enviar, reaccionar, reenviar, borrar ni archivar.
3. Recorrer la lista de chats del más reciente al más viejo, en lotes de 15 a 30 chats individuales. Saltar grupos y cuentas de empresa, bot o notificaciones.
4. Por cada chat, leer el panel de info (teléfono, About, info de empresa) y los mensajes ya cargados.
5. No copiar PINs, contraseñas, códigos, cuentas, CLABE ni nada de FIEL.
6. Armar un JSON con los campos `name`, `phone`, `about`, `business_info`, `relationship`, `work_profile`, `needs_or_offers`, `evidence`, `last_message_date`.
7. Agregar el lote con `python3 cruce/add.py < lote.json` (deduplica por nombre; si hay homónimos, revisar el teléfono).
8. Reportar al usuario solo lo que ya regresó del lote.

## Límites

WhatsApp Web solo trae lo que sincronizó el teléfono. Los chats viejos suelen traer 0 a 2 mensajes. Para más contexto, el usuario tendría que exportar los chats desde su teléfono. Esos exports son datos y no se versionan.

Los scripts de `whatsapp/` no extraen chats: abren o comprueban las sesiones de Chrome (CDP / visor / MCP `estado_navegador`).
