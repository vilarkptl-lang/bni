# Rollback — sección seguimientos

Worker: `bni-referidos`. El dominio de producción se configura en `tableros/wrangler.toml`.

Las versiones concretas de despliegue no se versionan aquí; consúltalas en el panel de Cloudflare Workers o con `wrangler deployments list`.

## Cómo volver atrás

1. Restaurar el código previo del Worker (`src/worker.js`, `public/index.html`, `wrangler.toml`, `comentarios.sh`) sobre `tableros/`.
2. Desplegar con las variables de entorno (no incrustadas):

   `CLOUDFLARE_API_TOKEN=$CF_TABLERO_TOKEN CLOUDFLARE_ACCOUNT_ID=$CLOUDFLARE_ACCOUNT_ID wrangler deploy`

   O: `wrangler rollback <VERSION_PREVIA>`
3. No ejecutar DROP de tablas. El rollback de código deja las tablas `seguimientos` y `aprobaciones_seguimiento` intactas y no toca `aprobaciones` ni `comentarios`.

El Durable Object no se revierte con el código; por eso no se borra estado de presentación.
