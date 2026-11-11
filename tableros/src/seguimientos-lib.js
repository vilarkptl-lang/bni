export const S = (v, n = 500) => (v == null || v === "" ? null : String(v).slice(0, n));

export function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

export function rutaBoard(p) {
  if (p.startsWith("/api/admin")) return "admin";
  if (
    p === "/ws" ||
    p === "/api/comments" ||
    p === "/api/aprobaciones" ||
    p === "/api/seguimientos" ||
    p === "/api/aprobaciones-seguimiento"
  ) {
    return "access-api";
  }
  return "assets";
}

export function validarSeguimiento(b = {}) {
  const texto = String(b.texto || "").trim().slice(0, 4000);
  const id_propuesta = S(b.id_propuesta, 200);
  const id_miembro = S(b.id_miembro, 100);
  if (!texto || !id_propuesta || !id_miembro) return { error: "datos inválidos" };
  return {
    texto,
    id_propuesta,
    id_miembro,
    miembro: S(b.miembro),
    contacto: S(b.contacto),
    id: S(b.id, 200),
  };
}

export function validarAprobacionSeguimiento(b = {}) {
  const id_propuesta = S(b.id_propuesta, 200);
  const id_miembro = S(b.id_miembro, 100);
  const est = b.estado;
  if (!id_propuesta || !id_miembro || !["aprobada", "rechazada", null].includes(est ?? null)) {
    return { error: "datos inválidos" };
  }
  return {
    id_propuesta,
    id_miembro,
    miembro: S(b.miembro),
    contacto: S(b.contacto),
    estado: est ?? null,
  };
}

export function decidirAppend({ existingById, sameTextoRow, id, texto }) {
  if (existingById) return { action: "reuse", row: existingById };
  if (sameTextoRow && sameTextoRow.texto === texto) return { action: "reuse", row: sameTextoRow };
  return { action: "insert", id: id || null };
}

export function createBoardMem(seed = {}) {
  return {
    aprobaciones: (seed.aprobaciones || []).map((x) => ({ ...x })),
    comentarios: (seed.comentarios || []).map((x) => ({ ...x })),
    seguimientos: (seed.seguimientos || []).map((x) => ({ ...x })),
    aprobaciones_seguimiento: (seed.aprobaciones_seguimiento || []).map((x) => ({ ...x })),
  };
}

function json(status, body) {
  return { status, body };
}

export async function handleBoard(board, method, path, headers = {}, body = null, auth = { adminOk: true, email: "agente@local" }) {
  const url = new URL(path, "https://bni.vilarkptl.com");
  const p = url.pathname;
  const kind = rutaBoard(p);
  const email = headers["x-user-email"] || auth.email || null;
  if (kind === "admin") {
    if (!auth.adminOk) return json(403, "prohibido");
  } else if (kind === "access-api") {
    if (!email) return json(403, "prohibido");
  }

  const now = new Date().toISOString();

  if ((p === "/api/seguimientos" || p === "/api/admin/seguimientos") && method === "GET") {
    const pid = url.searchParams.get("id_propuesta");
    const rows = pid ? board.seguimientos.filter((s) => s.id_propuesta === pid) : board.seguimientos;
    return json(200, rows);
  }

  if ((p === "/api/seguimientos" || p === "/api/admin/seguimientos") && method === "POST") {
    const v = validarSeguimiento(body || {});
    if (v.error) return json(400, { error: v.error });
    const existingById = v.id ? board.seguimientos.find((s) => s.id === v.id) || null : null;
    const sameTextoRow = board.seguimientos.find((s) => s.id_propuesta === v.id_propuesta && s.texto === v.texto) || null;
    const d = decidirAppend({ existingById, sameTextoRow, id: v.id, texto: v.texto });
    if (d.action === "reuse") return json(200, d.row);
    const row = {
      id: d.id || "seg-" + String(board.seguimientos.length + 1),
      id_propuesta: v.id_propuesta,
      id_miembro: v.id_miembro,
      miembro: v.miembro,
      contacto: v.contacto,
      texto: v.texto,
      email,
      created_at: now,
    };
    board.seguimientos.push(row);
    return json(201, row);
  }

  if ((p === "/api/aprobaciones-seguimiento" || p === "/api/admin/aprobaciones-seguimiento") && method === "GET") {
    return json(200, board.aprobaciones_seguimiento);
  }

  if (p === "/api/aprobaciones-seguimiento" && method === "POST") {
    const v = validarAprobacionSeguimiento(body || {});
    if (v.error) return json(400, { error: v.error });
    if (!v.estado) {
      board.aprobaciones_seguimiento = board.aprobaciones_seguimiento.filter((a) => a.id_propuesta !== v.id_propuesta);
      return json(200, { ...v, email, updated_at: now });
    }
    const row = { ...v, email, updated_at: now };
    const i = board.aprobaciones_seguimiento.findIndex((a) => a.id_propuesta === v.estado && false);
    const j = board.aprobaciones_seguimiento.findIndex((a) => a.id_propuesta === v.id_propuesta);
    if (j >= 0) board.aprobaciones_seguimiento[j] = row;
    else board.aprobaciones_seguimiento.push(row);
    return json(200, row);
  }

  return json(404, "no encontrado");
}
