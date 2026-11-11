# BNI referidos (tablero)

Worker y Durable Object del tablero de propuestas de referidos (`bni.vilarkptl.com`). Los borradores y las aprobaciones se guardan en el tablero; nada se envía por WhatsApp desde esta aplicación.

Este árbol es una copia de fuente **saneada**. Trae fixtures claramente ficticios en `public/index.html` y `fixtures/`. No incluye contactos, chats, envíos ni estado real. El HTML vivo de producción incrustaba propuestas reales y no se incluye.

`bni-board-ui.js` es un borrador de la lógica de UI (comentarios, aprobaciones, WebSocket). Espera un arreglo `D` definido en la página.

## Pruebas

```bash
npm test
# o: node --test tests/seguimientos.test.js
```

## Variables y secretos (solo nombres)

- `ADMIN_KEY` — secreto del Worker para `/api/admin/*` (wrangler secret; no va en el código).
- `NOTIFY_URL`, `NOTIFY_KEY` — aviso opcional al llegar un comentario o una aprobación (`set-webhook.sh`).
- `BNI_COMMENTS_KEY_FILE` — ruta a un archivo local con la misma clave de admin, para `comentarios.sh` y `seguimientos.sh`.
- `BNI_DATA_JSON` — JSON de propuestas para `seguimientos.sh cargar` (por defecto `fixtures/data.json`).
- `BNI_WEBHOOK_URL`, `BNI_WEBHOOK_KEY`, `CF_TABLERO_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` — solo para `set-webhook.sh`.
- Cloudflare Access protege el host; no se incluye ninguna sesión ni token.

## Rollback

Restaurar el código previo y desplegar el mismo Worker, o `wrangler rollback` a la versión anterior. No borrar tablas del Durable Object. Ver también `docs/rollback-seguimientos.md`.
