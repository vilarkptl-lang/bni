---
name: referenciasbni
description: >-
  Úsalo cuando el usuario pida /referenciasbni: enviar por WhatsApp a los referidos
  las conexiones que aprobó en el tablero y subir esas referencias a BNI
  Connect como contacto frío.
---
# Referencias BNI aprobadas: WhatsApp + BNI Connect

## 1. Juntar las aprobadas
- Corre `./comentarios.sh aprobaciones aprobada` en `tableros/`. Sale una línea por propuesta con: estado, miembro → contacto, id_propuesta, email y fecha.
- Descarta las que ya se procesaron. Llévalas en `procesadas.txt` (gitignorado), un id_propuesta por línea.
- De `data.json` (no versionado) saca, por cada id: el contacto, su teléfono y `borrador_contraparte`.
- Revisa cada texto antes de enviarlo:
  - en español;
  - sin mencionar BNI, grupo ni capítulo;
  - que diga «Es de toda mi confianza»;
  - sin datos privados del contacto;
  - redacción natural.

## 2. Confirmar con el usuario
- Mándale la lista: contacto, teléfono y mensaje.
- No envíes nada hasta que diga "envíalos" o algo equivalente.
- Por ahora no se envía nada a los miembros del capítulo; solo a los referidos.

## 3. Enviar por WhatsApp Web (subagente computerUse)
- Arma un archivo con un URL por mensaje: `https://web.whatsapp.com/send?phone=52XXXXXXXXXX&text=<texto con URL-encode>`. El teléfono va con 52, sin el 1 de celular y sin espacios.
- Reglas estrictas:
  - NUNCA escribas en el buscador ni en la lista de chats. Abre cada URL navegando directo.
  - Antes de enviar, verifica que el nombre del chat corresponda al contacto y que el compositor tenga exactamente ese texto. Si algo no cuadra, sáltalo.
  - Un clic en enviar, una sola vez. Confirma que aparezca una burbuja nueva.
  - Espera al azar de 30 a 90 segundos entre envíos.
  - Si la primera carga se queda en "Iniciando chat" y regresa al inicio, recarga ese URL; no se envió nada.

## 4. Subir a BNI Connect (subagente computerUse)
- Inicia sesión en https://www.bniconnectglobal.com/login/ con el login guardado en el vault. Pasa sus referencias de llenado por nombre, por ejemplo `vault_<ITEM_ID>_username` y `vault_<ITEM_ID>_password`. No hay 2FA.
- En /web/dashboard, en el recuadro "Referencias Dadas", da clic en **Enviar**. Se abre la ventana "BNI ficha de referencia".
- Llena:
  - Para: el miembro del capítulo.
  - Referencia: nombre del contacto.
  - Tipo: Externa.
  - Estatus: marca "Le dije que le llamarías". Es obligatorio.
  - Teléfono: +52 y el número, sin espacios.
  - Comentarios: el motivo, más "Ya le escribí presentando a <NOMBRE_MIEMBRO>".
  - Escala de calor: el último botón, "Templada". Es lo más frío que ofrece el formulario.
- Da clic en **Registrar**. Espera el mensaje «El Formato Ha Sido Registrado Exitosamente» antes de pasar a la siguiente. Una sola vez cada una.

## 5. Cerrar
- Agrega los ids a `procesadas.txt`.
- Repórtale al usuario qué se envió y a qué hora (zona del usuario), qué se registró, y manda capturas.
- No guardes contactos ni escribas a nadie más sin que lo pida.
