---
name: bni
description: >-
  Úsalo para cruzar los contactos de WhatsApp personal con los miembros de un
  capítulo BNI: escanear chats (solo lectura), recalcular cruces, rearmar Excel
  con pasteles y subir a Google Sheets.
---
# Cruce BNI x WhatsApp

## Archivos (directorio de datos, p. ej. BNI_DATA_DIR)
- `members.json`: miembros del capítulo (de `m_*.json` vía `lectura-capitulo/parse.py`; `roster.json` es el roster original).
- `wa_personal_contacts.json`: contactos con los campos name, phone, about, business_info, relationship, work_profile, needs_or_offers, evidence y last_message_date.
- `cruce/add.py`: agrega un lote sin duplicar (`python3 add.py < lote.json`). Deduplica por nombre: si dos contactos se llaman igual, revisa también el teléfono.
- `excel/xl.py` arma el Excel de miembros. `cruce/build2.py` es el builder actual de cruces: conserva los previos, agrega los nuevos, arma los pasteles y la pestaña de Prospectos, y limpia datos sensibles. Las listas de cruces viven en JSON externos (no en el código).

## 1. Escaneo (computerUse, solo lectura)
- Abre WhatsApp Web en el perfil de Chrome de WhatsApp personal. Usa la pestaña cuyo título muestra el conteo de no leídos.
- Nunca escribas, envíes, reacciones, reenvíes, borres ni archives nada.
- Recorre la lista de chats del más reciente al más viejo, por lotes de 15 a 30 chats individuales. Cada lote empieza en el nombre donde terminó el anterior; pide al subagente que reporte el último chat procesado y el siguiente.
- Salta grupos y cuentas de empresa, bot o notificaciones.
- Por cada chat lee el panel de info (teléfono, About, info de empresa) y los mensajes que estén cargados.
- Nunca copies PINs, contraseñas, códigos, cuentas o CLABE, ni nada de FIEL.
- Abrir los chats los marca como leídos; ya está aceptado.
- Agrega cada lote con `add.py` en cuanto regresa. Reporta al usuario solo lo que ya regresó del lote, nunca antes.

## 2. Cruces
- Basa cada cruce solo en lo registrado del contacto; nunca inventes.
- Califica cada cruce del 1 al 5 y márcalo como "prospecto para el miembro" o "socio de referencia", con una razón corta.
- Los prospectos de crédito del propio usuario van en una pestaña aparte (Prospectos), no como cruces.
- Excluye familia, staff, clientes y deudores, usando el diccionario de excluidos (JSON externo).
- Corre `build2.py`, que hace los cruces, los pasteles por miembro, dirección, calidad y relación, y el filtro de datos sensibles.

## 3. Subir a Sheets
- El `update_file_content` del conector de Drive solo acepta texto.
- Para subir un xlsx, codifícalo en base64 y súbelo con `create_file` usando `"$file:/tmp/x.b64"`. Google lo convierte a Sheet.
- No compartas el archivo con nadie. Para mandar versiones viejas a la papelera, pide aprobación.

## Problemas conocidos
- WhatsApp Web solo trae lo que sincronizó el teléfono. Los chats viejos traen 0 a 2 mensajes y la lista termina antes que el historial real. Para más contexto, el usuario tendría que exportar los chats desde su teléfono.
- Muchos nombres traen prefijo "~" o vienen como número suelto, y la búsqueda por nombre exacto falla.
- Si el scroll por script se cuelga, usa el scroll del escritorio.
