# Sección de seguimientos

Historial append-only de borradores de seguimiento por propuesta, visible en el bloque de cada caso, con fecha y estado de la presentación. La aprobación de un seguimiento es independiente de la de la presentación y solo registra la decisión; no envía mensajes.

## API

- Access: `GET/POST /api/seguimientos`, `GET/POST /api/aprobaciones-seguimiento`
- Admin (`x-admin-key`): `GET/POST /api/admin/seguimientos`, `GET /api/admin/aprobaciones-seguimiento`

Idempotencia: el mismo `id` o el mismo texto en una propuesta reutiliza la fila y no reescribe el historial.

Helper: `./seguimientos.sh listar|agregar|cargar|aprobaciones`
