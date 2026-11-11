# BNI — guía para otros capítulos

Código de los flujos BNI: leer el capítulo, extraer contactos de WhatsApp (solo lectura), cruzarlos con los miembros, armar Excel, operar un tablero de propuestas y seguimientos, y registrar referencias e invitados en BNI Connect.

**Este repositorio no contiene datos personales ni secretos.** Los contactos, miembros, chats, Excel, sesiones, tokens y claves viven fuera de git: en un directorio de datos (`BNI_DATA_DIR`), en variables de entorno o en un gestor de secretos / bindings. Los JSON de `examples/` y `fixtures/` están marcados como EJEMPLO y usan teléfonos y correos ficticios (`@example.com`, `550000…`).

Sirve para un miembro de **otro capítulo** que quiera el mismo flujo con el agente de IA que prefiera (Cursor, Claude Code, ChatGPT/Codex u otro) o a mano. Las `skills/*/SKILL.md` son instrucciones en lenguaje natural: cualquier agente puede leerlas y seguirlas; no dependen de un producto concreto.

## Flujo completo

1. **Lectura del capítulo** (`lectura-capitulo/`) — perfiles y roster de BNI Connect → `members.json`.
2. **Extracción de contactos de WhatsApp** (`whatsapp-extraccion/` + `skills/bni`) — solo lectura, por lotes, → `wa_personal_contacts.json`.
3. **Cruce** (`cruce/`) — contactos × miembros, listas en JSON externos, Excel con pasteles.
4. **Excel de miembros** (`excel/`) — libro del capítulo a partir de `members.json`.
5. **Tablero** (`tableros/`) — propuestas, comentarios, aprobaciones. Nada se envía por WhatsApp desde esta app.
6. **Seguimientos y referencias** (`docs/seguimientos.md`, `skills/referenciasbni`) — borradores en el tablero; WhatsApp y ficha en Connect solo con OK, uno a uno.
7. **Invitados en BNI Connect** (`skills/invitadobni`) — registro de visitantes en el navegador, con permiso del invitado y OK del usuario.

No hay API de WhatsApp ni de BNI Connect en este repo. La lectura y el registro se hacen en el navegador (el agente o tú), siguiendo las skills.

```text
BNI Connect (perfiles)          WhatsApp Web (solo lectura)
        │                                    │
        ▼                                    ▼
lectura-capitulo/  →  members.json     cruce/add.py  →  wa_personal_contacts.json
        │                                    │
        ├──────────── excel/xl.py            │
        │                 │                  │
        └─────────────────┴──── cruce/build2.py  →  Excel de cruces (fuera de git)
                          │
                          ▼
                    tableros/  (propuestas / comentarios / seguimientos)
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
 skills/referenciasbni              skills/invitadobni
 (WhatsApp + ficha Connect,         (visitantes en Connect,
  solo mensajes aprobados)           con OK previo)
```

## Qué hace cada módulo

| Carpeta | Qué hace |
|---|---|
| `lectura-capitulo/` | `srv.py` recibe perfiles en `127.0.0.1` y guarda `m_<id>.json`. `parse.py` junta `roster.json` + perfiles + `roles.json` → `members.json`. |
| `whatsapp-extraccion/` | Receta de lectura de WhatsApp Web (solo lectura). No hay scraper por API. |
| `cruce/` | `add.py` incorpora lotes; `build.py` es la primera versión del Excel; `build2.py` es la actual (cruces previos + nuevos + prospectos + pasteles). |
| `excel/` | `xl.py` arma el libro de miembros (hojas Miembros y Resumen). |
| `tableros/` | Worker y sitio de propuestas, comentarios, aprobaciones y seguimientos. Fixtures ficticios. Pruebas: `npm test`. |
| `bni-connect-invitados/` | Receta de `/invitadobni` (visitantes en Connect, en el navegador). |
| `bni-connect-referencias/` | Receta de `/referenciasbni` (WhatsApp a referidos + ficha en Connect). |
| `whatsapp/` | LaunchAgents de Chrome, puente CDP opcional, setup de túnel/Access y MCP `estado_navegador` (solo cuenta pestañas; no extrae chats). |
| `skills/` | Instrucciones en lenguaje natural: `bni`, `invitadobni`, `referenciasbni`, `wahtsapp`, `comunicacion`. |
| `docs/` | Seguimientos, rollback, visor de WhatsApp, plan de la sección de seguimientos. |
| `tools/` | Empaque saneado del tablero (sin listas de PII reales). |

## Requisitos

- **Python 3** — `pip install -r requirements.txt` (`openpyxl`).
- **Node.js** — para las pruebas del tablero (`node --test` / `npm test`).
- **Wrangler** (opcional) — solo si vas a desplegar el Worker. En `tableros/` está como `devDependencies` (`npm install` ahí).
- **Cuenta de Cloudflare** — opcional. Hace falta para publicar el tablero (Worker, Durable Object, dominio, Access) y, si quieres, el túnel/visor de WhatsApp. La demo local de Python y `npm test` no la necesitan.
- **Navegador** — WhatsApp Web y BNI Connect se operan a mano o con el agente (computer use), no por API.
- **macOS** — solo para los LaunchAgents de `whatsapp/` (dos Chrome con CDP). El resto del código es portable.
- **jq** y **curl** — para `tableros/comentarios.sh` y `tableros/seguimientos.sh` contra un tablero ya desplegado.

## Cómo obtener el código (clonar o copiar)

Este repo vive en Origin (`https://origin.cursor.com/vilar-kptl/BNI.git`). Origin, hoy, solo ofrece visibilidad `private` o `internal` (equipo) y **no tiene forks**. No hay visibilidad pública.

Opciones:

1. **Clonar** si te dieron acceso al namespace o al repo:
   ```bash
   git clone https://origin.cursor.com/vilar-kptl/BNI.git
   cd BNI
   ```
2. **Copiar el árbol** (zip o `cp -a`) a una carpeta tuya y, si quieres historial propio, `git init`.
3. **Publicar tu copia** en GitHub, GitLab u otro forge y hacer fork ahí. Este repositorio de Origin no sustituye ese paso.

Trabaja en tu copia. No subas tus datos reales a este remoto.

## Variables de entorno y secretos (solo nombres)

Nunca incrustes valores en el código, en `wrangler.toml` ni en las skills. El `.gitignore` ya excluye `.env`, `.dev.vars`, `*.pem`, `*.key`, `*.age`, `secrets/` y el directorio de datos reales.

**Dónde guardarlos**

| Qué | Dónde |
|---|---|
| Secretos del Worker (`ADMIN_KEY`, `NOTIFY_URL`, `NOTIFY_KEY`) | Bindings de Wrangler (`wrangler secret put`), no en git |
| Token de API de Cloudflare, IDs de cuenta/zona/túnel | Gestor de secretos o variables del entorno de la máquina; nunca en el repo |
| Login de BNI Connect | Gestor de secretos / vault. En las skills se citan solo como `vault_<ITEM_ID>_username` y `vault_<ITEM_ID>_password` (el item no se documenta aquí) |
| Clave admin para los helpers locales | Archivo local gitignorado cuya ruta va en `BNI_COMMENTS_KEY_FILE` |
| Tokens de Access cifrados con age | Archivos `.age` en un directorio gitignorado (`SECRET_DIR`) |
| Datos del capítulo | `BNI_DATA_DIR` fuera del clone (por ejemplo `/var/lib/bni-datos` o `~/bni-datos`) |

**Datos de capítulo y cruces**

- `BNI_DATA_DIR` — `members.json`, `roster.json`, `wa_personal_contacts.json`, `m_*.json`, `roles.json`, listas de cruces, Excel de salida
- `BNI_CHAPTER` — nombre del capítulo (si falta, `parse.py` usa el del roster o «Capítulo»)
- `BNI_REGION` — por defecto `Mexico`
- `BNI_EXPORT_DATE` — fecha del export
- `BNI_CAPITULO_XLSX` — nombre del xlsx de miembros (si falta, `BNI_<slug del capítulo>.xlsx`)
- `BNI_SRV_HOST` (por defecto `127.0.0.1`), `BNI_SRV_PORT` (por defecto `8765`)

**Tablero (`tableros/`)**

- `ADMIN_KEY` — secreto del Worker para `/api/admin/*`
- `NOTIFY_URL`, `NOTIFY_KEY` — webhook opcional al llegar un comentario o una aprobación
- `BNI_COMMENTS_KEY_FILE` — archivo local con la misma clave, para `comentarios.sh` y `seguimientos.sh`
- `BNI_DATA_JSON` — JSON de propuestas al cargar seguimientos (por defecto `fixtures/data.json`)
- `BNI_WEBHOOK_URL`, `BNI_WEBHOOK_KEY`, `CF_TABLERO_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` — `set-webhook.sh`

**WhatsApp / túnel (opcional)**

- `AGE_KEY_FILE`, `ACCESS_SERVICE_TOKEN_AGE`, `AGE_RECIPIENT`, `SECRET_DIR`
- `WA_HOST_PERSONAL`, `WA_HOST_VILAR` — hostnames de Access de tus dos sesiones (el segundo nombre es histórico; pon el hostname de tu cuenta de empresa)
- `CF_MAC_WHATSAPP_SETUP_TOKEN`, `CF_ACCOUNT_ID`, `CF_ZONE_ID`, `CF_TUNNEL_ID`
- `MCP_WA_HOST`, `MCP_WA_SERVICE`, `MCP_PUERTO`, `MCP_HOST_PUBLICO`
- `VNC_HOST`, `ACCESS_EMAIL`, `ACCESS_OTP_IDP_ID`

**BNI Connect**

- `vault_<ITEM_ID>_username`, `vault_<ITEM_ID>_password` — referencias de llenado en el vault; el id del ítem no va en este repo

## Cómo adaptar el repo a tu capítulo

1. **Directorio de datos** — `export BNI_DATA_DIR=…` a una ruta fuera de git. Ahí viven roster, perfiles, contactos, cruces y Excel.
2. **Nombre del capítulo y región** — `BNI_CHAPTER`, `BNI_REGION`, `BNI_EXPORT_DATE`. El Excel de miembros toma el capítulo de `members.json`.
3. **Cargos** — copia `lectura-capitulo/examples/roles.ejemplo.json` a `$BNI_DATA_DIR/roles.json` y pon los nombres reales de *tu* liderazgo (ese archivo no se versiona). `parse.py` y `xl.py` leen primero `$BNI_DATA_DIR/roles.json`.
4. **Roster y perfiles** — `roster.json` y `m_<id>.json` reales no se suben. Captúralos de BNI Connect (agente en el navegador + `srv.py`, o export que tú controles) y corre `parse.py`.
5. **Listas de cruces** — `cruces_manual.json`, `cruces_manual_nuevos.json`, `cruces_prev.json`, `prospectos_vilar.json` (el nombre del archivo de prospectos es el que espera `build2.py`; el contenido es el de *tu* capítulo). Empieza copiando los `examples/*.ejemplo.json` y sustituye por tus listas, siempre en `BNI_DATA_DIR`.
6. **Dominio del tablero** — en `tableros/wrangler.toml` cambia `name` y `routes.pattern` (hoy `bni.vilarkptl.com`). En `tableros/comentarios.sh` y `tableros/seguimientos.sh` cambia `BASE` al mismo origen. Protege el host con Cloudflare Access; no dejes `/api/admin/*` expuesto sin `ADMIN_KEY`.
7. **WhatsApp** — dos perfiles de Chrome (personal / empresa). En los plist, sustituye el marcador `USUARIO`. No copies QR, cookies ni sesiones al repo.
8. **Skills** — el tono, el directorio y las plantillas de `skills/comunicacion/` son de *tu* voz. El directorio real de contactos no se versiona (hay una plantilla vacía en esa skill).

## Demo con los ejemplos ficticios

Todo esto usa solo `examples/` y `fixtures/`. No toca WhatsApp ni BNI Connect.

```bash
python3 -m pip install -r requirements.txt
export BNI_DATA_DIR=/tmp/bni-demo
mkdir -p "$BNI_DATA_DIR"

cp cruce/examples/wa_personal_contacts.ejemplo.json "$BNI_DATA_DIR/wa_personal_contacts.json"
cp cruce/examples/members.ejemplo.json "$BNI_DATA_DIR/members.json"
cp cruce/examples/cruces_manual.ejemplo.json "$BNI_DATA_DIR/cruces_manual.json"
cp cruce/examples/cruces_manual_nuevos.ejemplo.json "$BNI_DATA_DIR/cruces_manual_nuevos.json"
cp cruce/examples/prospectos_vilar.ejemplo.json "$BNI_DATA_DIR/prospectos_vilar.json"
cp cruce/examples/cruces_prev.ejemplo.json "$BNI_DATA_DIR/cruces_prev.json"
cp lectura-capitulo/examples/roles.ejemplo.json "$BNI_DATA_DIR/roles.json"

# Excel de miembros (hojas Miembros + Resumen; cargos desde roles.json)
python3 excel/xl.py

# Excel de cruces y pasteles (builder actual)
python3 cruce/build2.py

# Incorporar un lote (el ejemplo ya está en wa_personal_contacts.json; add.py deduplica por nombre)
python3 cruce/add.py < cruce/examples/wa_personal_contacts.ejemplo.json

# Tablero: pruebas de seguimientos con fixtures ficticios
cd tableros && npm test
```

Los `.xlsx` salen en `BNI_DATA_DIR` y están gitignorados.

**Lectura del capítulo (cuando tengas un roster propio, no el ejemplo):**

```bash
export BNI_DATA_DIR=/tmp/bni-demo
export BNI_CHAPTER="Capítulo Ejemplo"
export BNI_REGION=Mexico
export BNI_EXPORT_DATE=2026-01-01
# roster.json y m_*.json viven en BNI_DATA_DIR (no se versionan)
python3 lectura-capitulo/srv.py          # solo 127.0.0.1:8765; otro proceso envía ?d=
python3 lectura-capitulo/parse.py        # → members.json
```

**Seguimientos contra un tablero ya desplegado** (requiere `BNI_COMMENTS_KEY_FILE` y tu `BASE`):

```bash
export BNI_DATA_JSON=tableros/fixtures/data.json
./tableros/seguimientos.sh cargar tableros/fixtures/borradores-seguimiento.json
./tableros/seguimientos.sh listar
./tableros/comentarios.sh aprobaciones
```

No envía WhatsApp. La aprobación de un seguimiento solo registra la decisión.

## Cómo pedirle a tu agente que use las skills

Las `SKILL.md` son el procedimiento. Pon el repo (o al menos `skills/`) en el contexto de tu agente (o del asistente que uses) y dile que las lea. En Cursor o Claude Code puedes copiar `skills/<nombre>/` a la carpeta de skills del producto; en ChatGPT, Codex u otro asistente, pega o adjunta el archivo y pide que lo siga al pie de la letra.

| Skill | Carpeta | Cuándo |
|---|---|---|
| Cruce WhatsApp × capítulo | `skills/bni/SKILL.md` | Escanear chats (solo lectura), recalcular cruces, Excel, subir a Sheets |
| Comunicación y envíos | `skills/comunicacion/SKILL.md` | Antes de redactar o enviar cualquier mensaje en tu nombre |
| Referidos aprobados | `skills/referenciasbni/SKILL.md` | WhatsApp a referidos + ficha en Connect |
| Invitados | `skills/invitadobni/SKILL.md` | Registrar visitantes en Connect |
| Visor de WhatsApp | `skills/wahtsapp/SKILL.md` | Revisar sesiones ya vinculadas, sin nuevo QR |

La carpeta se llama `wahtsapp` a propósito (así está en el repo).

**Prompts de ejemplo** (ajusta el nombre del capítulo; no pongas teléfonos ni correos reales en el prompt si el hilo se guarda en un proveedor):

> Lee `skills/bni/SKILL.md` y síguelo. Usa `BNI_DATA_DIR` en `/tmp/bni-demo` con los JSON de `cruce/examples/`. No abras WhatsApp. Corre `excel/xl.py` y `cruce/build2.py` y dime qué archivos salieron.

> Lee `skills/comunicacion/SKILL.md`. Redacta un borrador para presentar a un contacto de ejemplo con un miembro de ejemplo. No envíes nada; muestra el texto y espera mi sí.

> Lee `skills/referenciasbni/SKILL.md`. Lista las propuestas *aprobada* con `tableros/comentarios.sh`. No busques en WhatsApp Web tecleando. No envíes ningún mensaje hasta que yo diga «envíalos». Entre envíos, pausa 30–90 s.

> Lee `skills/invitadobni/SKILL.md`. Voy a registrar a un visitante para la próxima sesión. Pídeme los datos que falten. Avisa que BNI Connect puede mandarle un correo. No guardes el formulario hasta que yo lo confirme.

> Lee `skills/wahtsapp/SKILL.md`. Revisa en solo lectura si las pestañas de WhatsApp Web personal y empresa siguen vinculadas. No pulses «Usar aquí», no escanees QR y no envíes mensajes.

Si el agente no carga skills solo, empieza con: «Antes de actuar, abre `skills/<nombre>/SKILL.md` y no te desvíes de esas reglas.»

## Buenas prácticas y privacidad

- **No subas datos reales.** Contactos, roster, `members.json` vivo, Excel, `data.json` de producción, `envios.txt`, `procesadas.txt`, chats, HAR, sesiones, QR, cookies, tokens y llaves están en `.gitignore` a propósito. Los únicos nombres y teléfonos del repo son los de `examples/` y `fixtures/`, marcados EJEMPLO.
- **Mantén los datos fuera de git.** `BNI_DATA_DIR` debe ser una ruta local o un volumen que no sea el clone. No hagas commit de `.env` ni de `.dev.vars`.
- **Pide permiso** a las personas antes de registrarlas en BNI Connect o de escribirles. Connect puede enviarles un correo al guardar un visitante; las skills exigen tu OK previo.
- **WhatsApp Web: no uses el buscador tecleando.** Para abrir un chat de envío, navega a `https://web.whatsapp.com/send?phone=52…&text=…`. La extracción de contactos es solo lectura: no escribas, envíes, reacciones, reenvíes, borres ni archives.
- **Envía solo mensajes aprobados, uno por uno, con pausas.** Cada texto necesita tu sí explícito. Verifica en pantalla el chat, el número (personal o empresa) y los acentos. Espera 30–90 s al azar entre envíos. El tablero **no** envía WhatsApp.
- **Respeta los términos** de [BNI Connect](https://www.bniconnectglobal.com/) y de WhatsApp. Este código no automatiza la API de ninguno de los dos; usa la interfaz que ya tienes como miembro. No abras sesiones extra, no pulses «Usar aquí» sin autorización y no copies FIEL, PINs, CLABE ni contraseñas a archivos del repo.
- **Access y admin.** El tablero se diseña detrás de Cloudflare Access; `/api/admin/*` exige `x-admin-key`. No publiques el Worker sin eso.
- **Rollback.** Restaurar código y `wrangler rollback` / redeploy; no borres las tablas del Durable Object. Ver `docs/rollback-seguimientos.md`.

## Qué no va en este repo

Contactos, exports de chat, Excel con datos reales, `data.json` vivo, `pendientes-*.json`, `registros-*.json`, `envios.txt`, backups del tablero, sesiones de navegador, QR, cookies, tokens, llaves, IDs de cuenta de Cloudflare, directorio real de comunicación y cualquier archivo con nombres, teléfonos o correos de personas reales (salvo los ejemplos marcados como EJEMPLO en `fixtures/` y `examples/`).
