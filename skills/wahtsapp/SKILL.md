---
name: wahtsapp
description: >-
  Úsalo cuando el usuario invoque /wahtsapp o pida revisar WhatsApp mediante un
  visor remoto ya configurado, sin volver a vincular sesiones.
---
# WhatsApp en sesiones existentes mediante visor remoto

## Preparar
1. Consultar el contexto y la memoria del asistente para obtener el visor remoto configurado, cuenta solicitada y responsables de las sesiones. No inventar accesos ni compartir credenciales entre asistentes. Si falta la configuración, localizarla en los archivos autorizados o preguntarle al usuario.
2. Cargar `box-desktop` antes del primer trabajo en navegador; cargar `sign-in` y `vault` si hay autenticación. Para redactar o enviar, cargar también `comunicacion` y `send-on-behalf`. Respetar los conectores disponibles y las reglas de acceso vigentes.
3. Toda interacción con el navegador o escritorio se delega a computerUse. No manejar WhatsApp mediante Shell, CDP, scripts de navegador, cookies ni APIs internas.

## Entrar y comprobar
4. Preferir la pestaña del visor que ya está conectada. No recargar ni cerrar sin necesidad. Si el usuario acaba de devolver el control, empezar con Screenshot de solo lectura.
5. Distinguir dos autenticaciones: la contraseña HTML del visor y el desbloqueo del sistema remoto. Para el visor, usar BrowserSecureFill con el valor seguro disponible y el dominio correcto; nunca leer, copiar ni mostrar el secreto. Si hace falta una contraseña nueva, usar el flujo Secure Form.
6. Si el sistema remoto está bloqueado dentro de un canvas y Secure Fill no puede dirigirse al campo, entregar la pantalla con request_box_help. Pedir que desbloquee hasta ver el escritorio, incluyendo Enter. No extraer el secreto ni improvisar otro método de inyección. Después de la devolución, verificar el estado con Screenshot.
7. Localizar las ventanas o pestañas de WhatsApp existentes. No escanear QR, cerrar sesión, pulsar «Usar aquí» ni abrir sesiones adicionales sin autorización específica. Que una ventana diga WhatsApp o Business no prueba su identidad: verificar el perfil/número contra la cuenta solicitada antes de leer chats.

## Revisar y preparar
8. Acotar los contactos y el intervalo a lo pedido. Abrir solo los chats pertinentes y comprobar nombre/número. Leer mensajes recientes y ejemplos reales del usuario antes de adaptar tono, saludo y tratamiento. No asumir contacto previo a partir de una aprobación en otro tablero.
9. No copiar contraseñas, códigos, datos bancarios ni conversaciones ajenas a la tarea. Adjuntar capturas solo cuando aporten algo y sin exponer información privada innecesaria.
10. Guardar propuestas en el destino pedido usando sus herramientas soportadas, sin sustituir un tablero existente por otra página, sobrescribir presentaciones ni modificar aprobaciones. Si falta un mecanismo de guardado, coordinar acceso con su responsable cuando el usuario lo haya autorizado.
11. Leer y preparar borradores no autoriza enviar. Seguir las reglas vigentes de revisión y envío de mensajes externos; una marca en un tablero no sustituye la confirmación requerida en el chat. No escribir en el compositor durante una revisión de solo lectura.

## Cerrar
12. Verificar y reportar únicamente lo observado: conexión, cuenta identificada, chats revisados, borradores guardados y pendientes. No afirmar que una sesión está lista si solo se vio la pantalla de bloqueo. Si se bloquea otra vez, informar el estado real y usar el mismo flujo de desbloqueo, sin bucles de reintentos.
