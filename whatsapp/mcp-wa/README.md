# mcp-wa

Servidor MCP (Streamable HTTP, sin estado) para consultar WhatsApp Web desde los
Chrome que ya están abiertos en la Mac. Corre **solo en la Mac**, escucha **solo
en `localhost`** y se publica mediante un túnel que ya existe (este repositorio
no configura ningún túnel).

## Herramientas MCP (`POST /mcp`)

| Herramienta | Qué hace |
|---|---|
| `estado_navegador(cuenta)` | Solo `GET /json/version` y `/json/list`. Indica si Chrome responde y cuántas pestañas de WhatsApp tiene. Sin títulos ni URLs. |
| `identidad_cuenta(cuenta)` | Solo lectura, sin clics. Indica si en el DOM aparecen **todas** las marcas de `MCP_MARCAS_CUENTA_A` (`coincide_marcas`), la cuenta detectada y si coincide con la pedida. No lista chats ni nombres. |
| `leer(cuenta, destchat, limite?)` | Abre el chat si hace falta (clic de navegación) y devuelve los mensajes visibles: `texto` y, si hay selector, `hora`, `direccion`, `id` y `adjunto`. No inventa campos. |
| `cargar_mas(cuenta, destchat)` | Ejecuta el gesto de cargar mensajes anteriores (`scroll` o `clic`, según los selectores). Sin confirmación. No envía. |
| `descargar(cuenta, destchat, id_o_nombre)` | Descarga un adjunto visible a `MCP_DIR_DESCARGAS`. No sube nada. |
| `preparar(cuenta, destinatario, texto)` | Abre el chat y deja el texto **exacto** en el compositor. **No** pulsa Enter ni enviar. Devuelve `{borrador_id, cuenta, destinatario, texto, estado: "pendiente"}` y lo guarda en `MCP_DIR_BORRADORES`. |

Antes de actuar, `leer`, `cargar_mas`, `descargar` y `preparar` verifican que la
pestaña sea la de la cuenta pedida (marcas) y que el encabezado muestre el chat
correcto. Si falta un selector, la herramienta responde `selector_faltante` y
explica cuál falta: no adivina.

## No existe “enviar” en el MCP

El servidor no tiene ninguna herramienta ni ruta HTTP que envíe un mensaje; no
se puede disparar con `curl` ni con `tools/call`. El envío real lo hace solo el
CLI local `enviar_borrador.py`, que no importa ni registra el servidor:

```bash
python3 enviar_borrador.py BORRADOR_ID --confirmado-por-dueno
```

Úsalo **solo** después de que el dueño confirme de forma explícita, en el chat de
Oficina, **ese** mensaje concreto (cuenta, destinatario y texto). El CLI corre
solo en macOS y, antes de pulsar enviar, verifica que el borrador esté
pendiente, que la cuenta coincida, que el chat abierto sea el destinatario y que
el compositor tenga exactamente ese texto. Si algo no coincide, no envía.

## Cómo corre en la Mac

1. Abre los Chrome de cada cuenta con depuración local (por defecto `cuenta_a` en
   `localhost:9222` y `cuenta_b` en `localhost:9223`), con WhatsApp Web ya
   abierto y con la sesión iniciada. El servidor nunca lanza Chrome, nunca navega
   a WhatsApp, no escanea códigos QR y no pulsa “Usar aquí”.
2. `pip install playwright` (no hace falta descargar navegadores: solo se usa
   `connect_over_cdp`).
3. Inspección previa, de solo lectura, para sacar los selectores:
   ```bash
   MCP_MARCAS_CUENTA_A='...' python3 inspeccion_ro.py --salida inspeccion_ro.json
   ```
   Escribe un JSON estructural (testids, roles, iconos, candidatos a cargar más,
   compositor, adjuntos, booleanos de las marcas) sin textos de chats ni
   nombres.
4. Copia `selectores.observados.json` (selectores estructurales de una
   inspección de solo lectura, sin textos ni nombres) a `selectores.json`,
   o copia `selectores.ejemplo.json` y llénalo tú. Los campos vacíos se
   consideran no configurados y no se adivinan. Las marcas de
   `MCP_MARCAS_CUENTA_A` solo se detectan si están en el DOM visible
   (la lista de chats está virtualizada).
5. Carga tus variables (ver `env.ejemplo`) y arranca:
   ```bash
   python3 estado_mcp.py
   ```

## Variables de entorno

| Variable | Uso | Por defecto |
|---|---|---|
| `MCP_PUERTO` | Puerto local del servidor | `8765` |
| `MCP_HOST_PUBLICO` | Valor de `Host` que manda el túnel | vacío |
| `MCP_PUERTO_CUENTA_A` / `MCP_PUERTO_CUENTA_B` | Puertos CDP locales | `9222` / `9223` |
| `MCP_MARCAS_CUENTA_A` | Marcas del DOM de la cuenta_a, separadas por `\|` | vacío |
| `MCP_SELECTORES` | Archivo de selectores | `./selectores.json` |
| `MCP_DIR_DESCARGAS` | Directorio de descargas | `./descargas` |
| `MCP_DIR_BORRADORES` | Directorio de borradores | `./borradores` |
| `MCP_PLAZO_HERRAMIENTA`, `MCP_PLAZO_ACCION_MS`, `MCP_ESPERA_CARGA_MS` | Plazos | `45`, `8000`, `1500` |

Las marcas y cualquier secreto van solo en el entorno, nunca en el código.

## Seguridad HTTP (igual que v0.3)

Solo `POST /mcp` con `Content-Type: application/json` y `Content-Length`
(sin él responde 411, y no se acepta `Transfer-Encoding`); se valida `Host`; se
rechaza cualquier petición con `Origin`; hay límites de tamaño, de plazo y de
conexiones. Versiones de `initialize`: 2025-03-26, 2025-06-18 y 2025-11-25. El
registro no guarda cabeceras, cuerpos, chats, textos ni nombres de archivo.

## Pruebas

```bash
python3 -m unittest discover
```

Usan un Chrome simulado (`HTTPServer`) y un Playwright simulado
(`simulador_pw.py`). Nunca tocan WhatsApp ni los puertos 9222/9223, y ninguna
envía un mensaje real. Antes de publicar, puedes añadir una lista negra local:
`MCP_PALABRAS_PROHIBIDAS='a|b' python3 -m unittest test_higiene`.
