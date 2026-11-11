---
name: invitadobni
description: >-
  Úsalo cuando el usuario pida /invitadobni o registrar invitados (visitantes)
  en BNI Connect para una sesión del capítulo.
---
# Registrar invitados en BNI Connect

## Datos necesarios por invitado
Pide o junta estos datos: nombre, apellido(s), correo, teléfono, empresa y giro.
- Si falta el correo, pídelo al usuario. Es lo más rápido.
- Solo si el usuario lo pide, léelo del chat de WhatsApp. Eso es solo lectura: nunca escribas ni envíes nada.
- Pregunta la fecha de visita si no la dio. Las fechas válidas son los días de sesión que muestra el calendario.
- Avisa que BNI puede mandarle un correo al invitado. El formulario no tiene opción para desactivarlo. Espera el OK del usuario.

## Iniciar sesión
- Página: https://www.bniconnectglobal.com/login/
- Usa el login guardado en el vault para bniconnectglobal. Pásale al subagente sus referencias de llenado por nombre (p. ej. `vault_<ITEM_ID>_username` y `vault_<ITEM_ID>_password`).
- Si no hay login guardado, manda un RequestUserForm de tipo login para www.bniconnectglobal.com.
- No hay 2FA.

## Registro (subagente computerUse)
1. Formulario: https://www.bniconnectglobal.com/web/visitors/registrations/add. Se llega por Dashboard, luego Visitantes, luego Visitor Portal y luego Agregar registro.
2. Deja seleccionado "Registrar a alguien más para visitar mi capítulo". El capítulo ya viene prellenado.
3. Fecha de visita: la que eligió el usuario.
4. Tipo de Visitante: Visitante (elegible).
5. Llena nombre, apellido, correo, teléfono y Nombre Empresa.
6. Categoría: escribe en el buscador y elige la sugerencia más cercana.
   - Para construcción, sirve "Contratista de Obra Civil".
   - Para software, sirve "Computadoras y Programación › Software para Computadoras".
7. Marca la casilla de permiso. Es obligatoria: sin ella, guardar falla.
8. Haz clic en Guardar registro. La confirmación es el toast "Registro agregado exitosamente".
9. Toma una captura del formulario lleno antes de guardar y otra del toast después.

## Notas
- El portal no muestra la lista de registros, así que no se pueden revisar duplicados. Pregunta al usuario si ya registró a alguien.
- Al final, reporta al usuario la categoría elegida para cada invitado y manda las capturas.
