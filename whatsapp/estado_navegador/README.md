# Prueba local de estado_navegador (v0.3)

Solo en la Mac, con los Chrome de WhatsApp ya abiertos en `127.0.0.1:9222` (personal) y `127.0.0.1:9223` (vilar). No usa túnel, no instala nada, no envía mensajes y no abre una conexión de depuración con la página.

Desde esta carpeta:

```bash
python3 probar_local.py
```

Arranca un servidor MCP únicamente en `127.0.0.1`, en un puerto efímero. Llama `initialize`, `tools/list` (debe existir exactamente la herramienta `estado_navegador`) y `tools/call` para `personal` y `vilar`. Imprime un JSON reducido y cierra el servidor siempre.

`chrome_responde` indica si ese Chrome local contestó `/json/version` y `/json/list`. No verifica la sesión ni la cuenta de WhatsApp. El código de salida es 0 si ambos Chrome responden; 1 si el protocolo funcionó pero algún Chrome no respondió; 2 si falló la prueba del protocolo.
