# Plan breve: sección de seguimientos en el tablero

Agregar la sección de seguimientos al tablero BNI, sin tocar presentaciones ni enviar WhatsApp. Cambio mínimo, coherente con la UI actual. No se pide rediseño.

**Objetivo:** historial append-only de borradores de seguimiento por propuesta/contacto, visible en el bloque de cada caso (fecha + estado de la presentación), con aprobación de seguimiento separada de la de presentación.

**Arquitectura:** mismas piezas que ya existen. Tablas nuevas en el Durable Object `Board` (CREATE TABLE IF NOT EXISTS; no hay migración wrangler nueva, para no recrear la clase ni perder SQLite). Rutas gemelas de comentarios/aprobaciones, bajo el mismo Access y el mismo `x-admin-key` en `/api/admin/*`. La UI solo escapa y pinta; no recibe la clave admin.

## Alcance y no-alcance

- Sí: tablas `seguimientos` y `aprobaciones_seguimiento`; APIs; UI en cada caso; helper `seguimientos.sh`; cargar borradores locales de ejemplo; pruebas; backup/rollback; desplegar el mismo worker `bni-referidos` solo si las pruebas pasan.
- No: tocar `borrador`/`borrador_contraparte`, switches de presentación, comentarios/respuestas actuales, `procesadas.txt`/`envios.txt`, `data.json`, Access, DNS, secretos, sesiones, WhatsApp, automatismo de envío, ni un rediseño.

## Datos

- `seguimientos(id TEXT PK, id_propuesta, id_miembro, miembro, contacto, texto, email, created_at)`: solo INSERT. Si llega el mismo `id` o el mismo texto ya existente en esa propuesta, se reutiliza la fila (idempotente) y no se reescribe el texto.
- `aprobaciones_seguimiento`: igual patrón que `aprobaciones`, tabla distinta. El switch solo guarda decisión. Aviso visible: no envía nada.
- Snapshot WebSocket incluye `segs` y `apsSeg`. No se notifica envío.

## API (documentada en seguimientos.sh)

- Access (sesión del usuario): `GET/POST /api/seguimientos`, `GET/POST /api/aprobaciones-seguimiento`.
- Admin (`x-admin-key`, no se expone a la UI): `GET/POST /api/admin/seguimientos`, `GET /api/admin/aprobaciones-seguimiento`.
- Validación: JSON, texto 1–4000, ids acotados, estado solo `aprobada`|`rechazada`|null.

## UI

En el bloque de cada propuesta, debajo de la aprobación de presentación, una sección «Seguimiento» con historial (fecha, texto escapado), aviso de que no se envía, estado de la presentación, textarea para un borrador nuevo y switch propio de aprobación de seguimiento.

## Pruebas locales (antes de desplegar)

`node --test tests/seguimientos.test.js`: validación, append-only, idempotencia, no mutar presentaciones, autorización (admin vs Access vs sin credencial), escape XSS, aviso de no envío, texto de ejemplo intacto.

## Backup y rollback

Guardar una copia del código y, por separado (no en git), un snapshot del estado vivo. Rollback: restaurar esos archivos y `wrangler deploy` del worker con `CF_TABLERO_TOKEN`. El rollback de código no borra las tablas nuevas ni las de presentación. No usar `DROP`.

## Despliegue y carga

Si las pruebas pasan: `wrangler deploy` del mismo worker, sin secretos nuevos. Luego `seguimientos.sh cargar` de un JSON de borradores (fixtures de ejemplo en `tableros/fixtures/`). Si algo falla, se reporta el bloqueo y no se destruyen datos.
