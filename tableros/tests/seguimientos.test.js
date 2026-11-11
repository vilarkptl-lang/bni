import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  escapeHtml,
  decidirAppend,
  validarSeguimiento,
  validarAprobacionSeguimiento,
  rutaBoard,
} from "../src/seguimientos-lib.js";
import { createBoardMem, handleBoard } from "../src/seguimientos-lib.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const drafts = JSON.parse(
  readFileSync(join(root, "fixtures/borradores-seguimiento.json"), "utf8")
);
const ramonPid = "1001-luismolina-0";
const ramonTexto = drafts.casos.find((c) => c.id_propuesta === ramonPid).borrador;

test("validarSeguimiento exige texto e ids y recorta longitud", () => {
  assert.equal(validarSeguimiento({}).error, "datos inválidos");
  assert.equal(validarSeguimiento({ id_propuesta: "p", id_miembro: "m", texto: "   " }).error, "datos inválidos");
  const ok = validarSeguimiento({ id_propuesta: "p", id_miembro: "m", texto: "  Hola  ", miembro: "A", contacto: "B", id: "seg-1" });
  assert.equal(ok.error, undefined);
  assert.equal(ok.texto, "Hola");
  assert.equal(ok.id_propuesta, "p");
  const long = "x".repeat(5000);
  assert.equal(validarSeguimiento({ id_propuesta: "p", id_miembro: "m", texto: long }).texto.length, 4000);
});

test("validarAprobacionSeguimiento solo acepta estados conocidos", () => {
  assert.equal(validarAprobacionSeguimiento({ id_propuesta: "p", id_miembro: "m", estado: "enviada" }).error, "datos inválidos");
  assert.equal(validarAprobacionSeguimiento({ id_propuesta: "p", id_miembro: "m", estado: "aprobada" }).estado, "aprobada");
  assert.equal(validarAprobacionSeguimiento({ id_propuesta: "p", id_miembro: "m", estado: "rechazada" }).estado, "rechazada");
  assert.equal(validarAprobacionSeguimiento({ id_propuesta: "p", id_miembro: "m", estado: null }).estado, null);
});

test("decidirAppend es append-only e idempotente", () => {
  const base = { texto: "Hola", id_propuesta: "p1", id_miembro: "m1" };
  const insert = decidirAppend({ ...base, existingById: null, sameTextoRow: null, id: "seg-1" });
  assert.equal(insert.action, "insert");
  assert.equal(insert.id, "seg-1");
  const reuseId = decidirAppend({
    ...base,
    existingById: { id: "seg-1", texto: "Hola", id_propuesta: "p1" },
    sameTextoRow: null,
    id: "seg-1",
  });
  assert.equal(reuseId.action, "reuse");
  assert.equal(reuseId.row.texto, "Hola");
  const reuseTexto = decidirAppend({
    ...base,
    existingById: null,
    sameTextoRow: { id: "seg-old", texto: "Hola", id_propuesta: "p1" },
    id: null,
  });
  assert.equal(reuseTexto.action, "reuse");
  assert.equal(reuseTexto.row.id, "seg-old");
  const otro = decidirAppend({
    ...base,
    texto: "Otro",
    existingById: { id: "seg-1", texto: "Hola", id_propuesta: "p1" },
    sameTextoRow: { id: "seg-1", texto: "Hola", id_propuesta: "p1" },
    id: "seg-1",
  });
  assert.equal(otro.action, "reuse");
  assert.equal(otro.row.texto, "Hola", "no se reescribe un borrador previo");
  const append = decidirAppend({
    ...base,
    texto: "Otro",
    existingById: null,
    sameTextoRow: { id: "seg-1", texto: "Hola", id_propuesta: "p1" },
    id: "seg-2",
  });
  assert.equal(append.action, "insert");
  assert.equal(append.id, "seg-2");
});

test("rutaBoard no cambia el esquema de acceso y no expone admin en UI", () => {
  assert.equal(rutaBoard("/api/admin/seguimientos"), "admin");
  assert.equal(rutaBoard("/api/admin/comments"), "admin");
  assert.equal(rutaBoard("/api/seguimientos"), "access-api");
  assert.equal(rutaBoard("/api/aprobaciones-seguimiento"), "access-api");
  assert.equal(rutaBoard("/api/comments"), "access-api");
  assert.equal(rutaBoard("/api/aprobaciones"), "access-api");
  assert.equal(rutaBoard("/"), "assets");
});

test("escapeHtml evita XSS en textos de seguimiento", () => {
  assert.equal(escapeHtml(`<img src=x onerror="alert(1)"> & "y"`), "&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &quot;y&quot;");
});

test("almacén en memoria: append idempotente y no toca presentaciones", async () => {
  const board = createBoardMem({
    aprobaciones: [{ id_propuesta: ramonPid, estado: "aprobada", id_miembro: "1001" }],
    comentarios: [{ id: 2, id_propuesta: ramonPid, texto: "Nunca digas que son del BNI", respuesta: "Listo", status: "atendido" }],
  });
  const h = {
    "content-type": "application/json",
    "x-admin-key": "k",
    "x-user-email": "agente@local",
  };
  const body = {
    id: "seg-20261110-1001-luismolina-0",
    id_propuesta: ramonPid,
    id_miembro: "1001",
    miembro: "Ana Pérez (EJEMPLO)",
    contacto: "Luis Molina (EJEMPLO)",
    texto: ramonTexto,
  };
  const r1 = await handleBoard(board, "POST", "/api/admin/seguimientos", h, body);
  assert.equal(r1.status, 201);
  assert.equal(r1.body.texto, ramonTexto);
  const r2 = await handleBoard(board, "POST", "/api/admin/seguimientos", h, body);
  assert.equal([200, 201].includes(r2.status), true);
  const list = await handleBoard(board, "GET", "/api/admin/seguimientos", h);
  assert.equal(list.body.length, 1);
  assert.equal(list.body[0].texto, ramonTexto);
  assert.deepEqual(board.aprobaciones, [{ id_propuesta: ramonPid, estado: "aprobada", id_miembro: "1001" }]);
  assert.equal(board.comentarios[0].respuesta, "Listo");
  assert.equal(board.comentarios[0].status, "atendido");
});

test("autorización: admin exige clave; APIs de Access exigen correo; sin credencial se niega", async () => {
  const board = createBoardMem();
  const deniedAdmin = await handleBoard(board, "GET", "/api/admin/seguimientos", {}, null, { adminOk: false, email: null });
  assert.equal(deniedAdmin.status, 403);
  const deniedAccess = await handleBoard(board, "GET", "/api/seguimientos", {}, null, { adminOk: false, email: null });
  assert.equal(deniedAccess.status, 403);
  const okAccess = await handleBoard(board, "GET", "/api/seguimientos", {}, null, { adminOk: false, email: "user@example.com" });
  assert.equal(okAccess.status, 200);
  const okAdmin = await handleBoard(board, "GET", "/api/admin/seguimientos", { "x-admin-key": "k" }, null, { adminOk: true, email: null });
  assert.equal(okAdmin.status, 200);
  const ap = await handleBoard(
    board,
    "POST",
    "/api/aprobaciones-seguimiento",
    { "content-type": "application/json" },
    { id_propuesta: ramonPid, id_miembro: "1001", estado: "aprobada" },
    { adminOk: false, email: "user@example.com" }
  );
  assert.equal(ap.status, 200);
  assert.equal(ap.body.estado, "aprobada");
  assert.equal(ap.body.envio, undefined);
});

test("UI del tablero incluye sección de seguimiento, aviso de no envío y escape", () => {
  const html = readFileSync(join(root, "public/index.html"), "utf8");
  assert.match(html, /Seguimiento/);
  assert.match(html, /solo registra tu decisión; no envía nada/);
  assert.match(html, /\/api\/seguimientos/);
  assert.match(html, /\/api\/aprobaciones-seguimiento/);
  assert.doesNotMatch(html, /x-admin-key/);
  assert.doesNotMatch(html, /ADMIN_KEY/);
  assert.match(html, /const e=s=>/);
  // la sección pinta el texto de seguimiento con escape, no en crudo
  assert.match(html, /e\([^)]*texto/);
  const dStart = html.indexOf("const D=");
  const dEnd = html.indexOf(";const f=");
  const D = html.slice(dStart, dEnd);
  assert.match(D, /"borrador_contraparte": "Hola Luis/);
  assert.equal(D.includes("¿Sí te pasé el contacto de Ana?"), false, "el HTML estático no debe cambiar las presentaciones ni anticipar el seguimiento de ejemplo");
});

test("el archivo local de ejemplo no presume contacto entregado", () => {
  assert.equal(ramonTexto, "Hola Luis, ¿cómo estás? ¿Sí te pasé el contacto de Ana? Para que puedan platicar. Venga");
  assert.doesNotMatch(ramonTexto, /ya te pasé/i);
  assert.doesNotMatch(ramonTexto, /cirug/i);
});
