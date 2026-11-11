# Sesiones y puentes de WhatsApp

Plantillas para tener dos Chrome en macOS (personal en el puerto 9222, empresa en el 9223), un puente `cloudflared` opcional y un MCP de solo lectura que cuenta pestañas de web.whatsapp.com (`estado_navegador/`).

No extraen chats ni envían mensajes. Ver `../whatsapp-extraccion/` y `../docs/whatsapp-visor.md`.

## Variables (solo nombres)

- `AGE_KEY_FILE`, `ACCESS_SERVICE_TOKEN_AGE` — `conectar.sh`
- `WA_HOST_PERSONAL`, `WA_HOST_VILAR` — hostnames de Access (sin tokens en la URL)
- `CF_MAC_WHATSAPP_SETUP_TOKEN` — token de API para `cfapi.py` / `setup_*.py`
- `CF_ACCOUNT_ID`, `CF_ZONE_ID`, `CF_TUNNEL_ID` — nunca incrustados
- `AGE_RECIPIENT`, `SECRET_DIR` — cifrado de tokens con age
- `MCP_WA_HOST`, `MCP_WA_SERVICE` — ruta HTTP del MCP
- `VNC_HOST`, `ACCESS_EMAIL`, `ACCESS_OTP_IDP_ID` — ensayo opcional del visor
- `MCP_PUERTO`, `MCP_HOST_PUBLICO` — `estado_navegador/estado_mcp.py`
