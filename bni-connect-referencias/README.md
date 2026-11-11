# Automatización de referencias (BNI Connect + WhatsApp)

No hay un script que envíe WhatsApp ni que registre la ficha en BNI Connect por API. El flujo está en `skills/referenciasbni/SKILL.md`.

1. Listar aprobadas con `tableros/comentarios.sh aprobaciones aprobada` (requiere `BNI_COMMENTS_KEY_FILE`).
2. Armar el mensaje para cada referido a partir de `data.json` (no versionado) y mostrarlo al usuario. No enviar hasta que lo apruebe, uno a uno.
3. Abrir cada chat con `https://web.whatsapp.com/send?phone=52XXXXXXXXXX&text=...`. Nunca usar el buscador de WhatsApp. Esperar 30–90 s al azar entre envíos.
4. En BNI Connect, ficha de referencia externa, estatus «Le dije que le llamarías», calor «Templada». Confirmar el mensaje de registro exitoso antes de la siguiente.
