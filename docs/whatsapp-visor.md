# Visor y sesiones de WhatsApp

Hay dos Chrome en la máquina del usuario, cada uno con una sesión de WhatsApp Web ya vinculada:

- personal: CDP en `127.0.0.1:9222`
- empresa: CDP en `127.0.0.1:9223`

Los LaunchAgents (`whatsapp/com.vilarkptl.whatsapp-*.plist`) y `instalar.sh` se corren en macOS. El marcador `USUARIO` se sustituye por el usuario local. No se incluye ningún QR, cookie ni sesión.

## Puente remoto (opcional)

`whatsapp/conectar.sh` abre `cloudflared access tcp` hacia los hostnames indicados en `WA_HOST_PERSONAL` y `WA_HOST_VILAR`. El token de servicio de Access se descifra en memoria con `age` (`AGE_KEY_FILE`, `ACCESS_SERVICE_TOKEN_AGE`) y no se imprime.

La creación de túnel, DNS y políticas está en `setup_cf.py`, `setup_mcp_wa.py` y `setup_vnc.py`. Todos los IDs (cuenta, zona, túnel, correo del IdP) salen de variables de entorno. El estado se guarda en archivos `state-*.json` gitignorados.

La lectura y el envío de mensajes **no** se hacen por CDP ni por scripts: se usan el visor o WhatsApp Web en el navegador, con las skills `wahtsapp` y `comunicacion`. No escanear QR, no pulsar «Usar aquí» y no abrir sesiones adicionales sin autorización.
