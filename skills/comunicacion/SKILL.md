---
name: comunicacion
description: >-
  Úsalo SIEMPRE antes de redactar, proponer o enviar un mensaje (WhatsApp,
  correo) a cualquier persona en nombre del usuario: dice desde qué número va
  (WhatsApp de la empresa o personal), cómo le escribe a cada quien y las reglas
  de envío. También para actualizar el directorio después de cada envío.
---
# Cómo escribe el usuario a cada persona

## Reglas que nunca cambian
- Hay dos WhatsApp en la computadora:
  - **Empresa (Business)**: perfil de Chrome por defecto.
  - **Personal del usuario**: perfil de Chrome de WhatsApp personal.
- **Cada mensaje necesita la aprobación explícita del usuario**, por mensaje, en cualquiera de los dos números. Si dicta el texto ("dile textualmente…"), eso ya es la aprobación de ese texto exacto y ese destinatario. Si pide que lo redacte el asistente, se muestra el borrador y se espera su sí.
- Antes de enviar, verifica en pantalla que el chat abierto sea el de la persona correcta, en el número correcto, y que el texto esté completo con acentos, ñ y ¿. Teclea una acción a la vez, nunca en paralelo con Enter.
- Si se manda desde el número equivocado: borrar "para todos" de inmediato, avisar al usuario y reenviar desde el correcto solo con su OK.
- La ventana para editar un mensaje es de unos 15 minutos.
- Escribe en la voz del usuario, en primera persona, nunca como asistente ni como bot. No firmes con el nombre del asistente.
- Nunca manejes FIEL/e.firma ni contraseñas que lleguen por chat.

## Cómo decidir el número
1. Busca a la persona en el directorio local (no versionado; ver plantilla abajo).
2. Si no está: familia, amigos y contactos que el usuario atiende en persona van por el **personal**. Cobranza, clientes, onboarding y proveedores de la empresa van por el WhatsApp **empresarial**. Si hay duda, **pregunta al usuario** antes de redactar.
3. Si el usuario dice "por mi personal" o "proponlo personal", eso manda sobre el directorio. Actualiza el directorio.

## Cómo aprender el tono
- Antes de redactar para alguien nuevo, lee (solo lectura) los últimos mensajes que el usuario le escribió en ese chat. Fíjate en tú o usted, en saludo y despedida, en emojis y en lo largo de los mensajes, e imítalo.
- Estilo general: mensajes cortos y directos, a veces partidos en varios; sin emojis; sin despedida; a veces sin signos de apertura.
- Por defecto, en clientes de la empresa va directo y cordial, con tú salvo que el usuario use usted. Con la familia va cariñoso y corto.

## Directorio
El directorio real (nombres, relación, número y notas) **no se versiona**. Mantén una copia local gitignorada. Plantilla:

| Persona | Relación | Número | Tono / notas |
|---|---|---|---|
| NOMBRE_CONTACTO | Relación de ejemplo | Personal o Empresa | Notas de tono. Sin teléfonos reales en este repositorio. |

Campos vacíos o "Por confirmar": complétalos leyendo el chat o preguntando al usuario, y actualiza el directorio local.

## Plantillas (solo estructura; sin datos bancarios ni destinatarios reales)
- Recordatorio de liquidación: «Estimado <Nombre>, buen día. ¿Cómo estás? Te recuerdo que el saldo para liquidar el <día> es de $<monto>, solo interés ordinario, sin penas ni comisiones. Los datos van a nombre de <EMPRESA>, en <BANCO>, cuenta <CUENTA>, CLABE <CLABE>, con el concepto "pago en nombre de <Nombre completo>". ¿Me confirmas si lo tienes programado? Mil gracias.»
- Consulta a socio sobre cobro a un grupo: «Ya con lo de <cliente> firmado, ¿quieres que yo mande los recordatorios de cobro directo al grupo de <grupo>, o prefieres llevarlos tú? Como te acomode mejor.»
- Recordatorio de cobro a un contacto de seguimiento: «Hola <Nombre>, buen día. ¿Cómo estás? Te escribo para darle seguimiento a la quincena pendiente de <mes> por $<monto>, y hoy <fecha> toca la siguiente. ¿Me confirmas cuándo las tendrían? Mil gracias.»

Los datos bancarios reales de cada entidad se leen de la fuente autorizada al momento de redactar; no se guardan en esta skill.
