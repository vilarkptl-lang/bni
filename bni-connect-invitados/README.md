# Automatización de subida de invitados (BNI Connect)

No hay un script que llame a la API de BNI Connect. El registro de visitantes se hace en el navegador, siguiendo `skills/invitadobni/SKILL.md`.

Resumen: iniciar sesión en https://www.bniconnectglobal.com/login/ con el login del vault (`vault_<ITEM_ID>_username` / `vault_<ITEM_ID>_password`); abrir el formulario de Agregar registro; llenar datos del invitado; marcar el permiso; guardar; confirmar el toast «Registro agregado exitosamente». Si falta el correo, pedirlo al usuario. Leer WhatsApp solo si el usuario lo pide, y en solo lectura. Esperar su OK antes de registrar, porque BNI puede enviarle un correo al invitado.
