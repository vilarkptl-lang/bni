// BNI referidos — Worker + Durable Object (comentarios y seguimientos en SQLite + WebSocket hibernable).
// Access (solo el usuario) protege el host. /api/admin/* tiene app Access con bypass y exige x-admin-key (secreto ADMIN_KEY).
import { DurableObject } from "cloudflare:workers";
import { S, decidirAppend, rutaBoard, validarAprobacionSeguimiento, validarSeguimiento } from "./seguimientos-lib.js";
const J = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
export class Board extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS aprobaciones(id_propuesta TEXT PRIMARY KEY, id_miembro TEXT NOT NULL, miembro TEXT, contacto TEXT, estado TEXT NOT NULL, email TEXT, updated_at TEXT NOT NULL)`);
    ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS comentarios(id INTEGER PRIMARY KEY AUTOINCREMENT, id_miembro TEXT NOT NULL, id_propuesta TEXT, miembro TEXT, contacto TEXT, email TEXT, texto TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pendiente', respuesta TEXT, respondido_at TEXT)`);
    ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS seguimientos(id TEXT PRIMARY KEY, id_propuesta TEXT NOT NULL, id_miembro TEXT NOT NULL, miembro TEXT, contacto TEXT, texto TEXT NOT NULL, email TEXT, created_at TEXT NOT NULL)`);
    ctx.storage.sql.exec(`CREATE TABLE IF NOT EXISTS aprobaciones_seguimiento(id_propuesta TEXT PRIMARY KEY, id_miembro TEXT NOT NULL, miembro TEXT, contacto TEXT, estado TEXT NOT NULL, email TEXT, updated_at TEXT NOT NULL)`);
  }
  all(q, ...a) { return this.ctx.storage.sql.exec(q, ...a).toArray(); }
  broadcast(o) { const s = JSON.stringify(o); for (const ws of this.ctx.getWebSockets()) { try { ws.send(s); } catch {} } }
  snapshot() {
    return {
      tipo: "snapshot",
      cs: this.all("SELECT * FROM comentarios ORDER BY id"),
      aps: this.all("SELECT * FROM aprobaciones"),
      segs: this.all("SELECT * FROM seguimientos ORDER BY created_at, id"),
      apsSeg: this.all("SELECT * FROM aprobaciones_seguimiento"),
    };
  }
  appendSeguimiento(b, email) {
    const v = validarSeguimiento(b);
    if (v.error) return { error: v.error, status: 400 };
    const existingById = v.id ? this.all("SELECT * FROM seguimientos WHERE id=?", v.id)[0] : null;
    const sameTextoRow = this.all("SELECT * FROM seguimientos WHERE id_propuesta=? AND texto=?", v.id_propuesta, v.texto)[0];
    const d = decidirAppend({ existingById, sameTextoRow, id: v.id, texto: v.texto });
    if (d.action === "reuse") return { row: d.row, status: 200 };
    const id = d.id || crypto.randomUUID();
    const r = this.all(`INSERT INTO seguimientos(id,id_propuesta,id_miembro,miembro,contacto,texto,email,created_at) VALUES(?,?,?,?,?,?,?,?) RETURNING *`,
      id, v.id_propuesta, v.id_miembro, v.miembro, v.contacto, v.texto, email, new Date().toISOString())[0];
    this.broadcast({ tipo: "seguimiento", s: r });
    return { row: r, status: 201 };
  }
  setAprobacionSeguimiento(b, email) {
    const v = validarAprobacionSeguimiento(b);
    if (v.error) return { error: v.error, status: 400 };
    const now = new Date().toISOString();
    let a;
    if (!v.estado) {
      this.all("DELETE FROM aprobaciones_seguimiento WHERE id_propuesta=?", v.id_propuesta);
      a = { id_propuesta: v.id_propuesta, id_miembro: v.id_miembro, miembro: v.miembro, contacto: v.contacto, estado: null, email, updated_at: now };
    } else {
      a = this.all(`INSERT INTO aprobaciones_seguimiento(id_propuesta,id_miembro,miembro,contacto,estado,email,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id_propuesta) DO UPDATE SET estado=excluded.estado, email=excluded.email, updated_at=excluded.updated_at, miembro=COALESCE(excluded.miembro,miembro), contacto=COALESCE(excluded.contacto,contacto) RETURNING *`,
        v.id_propuesta, v.id_miembro, v.miembro, v.contacto, v.estado, email, now)[0];
    }
    this.broadcast({ tipo: "aprobacion_seguimiento", a });
    return { row: a, status: 200 };
  }
  async fetch(req) {
    const url = new URL(req.url), p = url.pathname;
    if (p === "/ws") {
      if (req.headers.get("Upgrade") !== "websocket") return new Response("upgrade requerido", { status: 426 });
      const [c, s] = Object.values(new WebSocketPair());
      this.ctx.acceptWebSocket(s);
      try { s.send(JSON.stringify(this.snapshot())); } catch {}
      return new Response(null, { status: 101, webSocket: c });
    }
    if (p === "/api/comments" && req.method === "GET") return J(this.all("SELECT * FROM comentarios ORDER BY id"));
    if (p === "/api/comments" && req.method === "POST") {
      let b; try { b = await req.json(); } catch { return J({ error: "JSON inválido" }, 400); }
      const t = String(b.texto || "").trim().slice(0, 4000);
      if (!t || !b.id_miembro) return J({ error: "falta texto o id_miembro" }, 400);
      const email = req.headers.get("x-user-email");
      const r = this.all(`INSERT INTO comentarios(id_miembro,id_propuesta,miembro,contacto,email,texto,created_at) VALUES(?,?,?,?,?,?,?) RETURNING *`,
        S(b.id_miembro, 100), S(b.id_propuesta, 200), S(b.miembro), S(b.contacto), email, t, new Date().toISOString())[0];
      this.broadcast({ tipo: "comentario", c: r });
      if (this.env.NOTIFY_URL && this.env.NOTIFY_KEY) {
        const u = new URL("/", req.url); u.searchParams.set("m", r.id_miembro); if (r.id_propuesta) u.searchParams.set("p", r.id_propuesta);
        this.ctx.waitUntil(fetch(this.env.NOTIFY_URL, { method: "POST", headers: { "content-type": "application/json", authorization: `Bearer ${this.env.NOTIFY_KEY}` },
          body: JSON.stringify({ tipo: "comentario", id: r.id, id_miembro: r.id_miembro, id_propuesta: r.id_propuesta, miembro: r.miembro, contacto: r.contacto, email: r.email, texto: r.texto, url: u.toString() }) }).catch(() => {}));
      }
      return J(r, 201);
    }
    if (p === "/api/aprobaciones" && req.method === "GET") return J(this.all("SELECT * FROM aprobaciones"));
    if (p === "/api/aprobaciones" && req.method === "POST") {
      let b; try { b = await req.json(); } catch { return J({ error: "JSON inválido" }, 400); }
      const pid = S(b.id_propuesta, 200), est = b.estado;
      if (!pid || !b.id_miembro || !["aprobada", "rechazada", null].includes(est ?? null)) return J({ error: "datos inválidos" }, 400);
      const email = req.headers.get("x-user-email"), now = new Date().toISOString();
      let a;
      if (!est) { this.all("DELETE FROM aprobaciones WHERE id_propuesta=?", pid); a = { id_propuesta: pid, id_miembro: S(b.id_miembro, 100), miembro: S(b.miembro), contacto: S(b.contacto), estado: null, email, updated_at: now }; }
      else a = this.all(`INSERT INTO aprobaciones(id_propuesta,id_miembro,miembro,contacto,estado,email,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id_propuesta) DO UPDATE SET estado=excluded.estado, email=excluded.email, updated_at=excluded.updated_at, miembro=COALESCE(excluded.miembro,miembro), contacto=COALESCE(excluded.contacto,contacto) RETURNING *`,
        pid, S(b.id_miembro, 100), S(b.miembro), S(b.contacto), est, email, now)[0];
      this.broadcast({ tipo: "aprobacion", a });
      if (this.env.NOTIFY_URL && this.env.NOTIFY_KEY) {
        const u = new URL("/", req.url); u.searchParams.set("m", a.id_miembro); u.searchParams.set("p", a.id_propuesta);
        this.ctx.waitUntil(fetch(this.env.NOTIFY_URL, { method: "POST", headers: { "content-type": "application/json", authorization: `Bearer ${this.env.NOTIFY_KEY}` },
          body: JSON.stringify({ tipo: "aprobacion", estado: a.estado || "sin_decision", id_propuesta: a.id_propuesta, id_miembro: a.id_miembro, miembro: a.miembro, contacto: a.contacto, email, updated_at: now, url: u.toString() }) }).catch(() => {}));
      }
      return J(a);
    }
    if ((p === "/api/seguimientos" || p === "/api/admin/seguimientos") && req.method === "GET") {
      const pid = url.searchParams.get("id_propuesta");
      return J(pid ? this.all("SELECT * FROM seguimientos WHERE id_propuesta=? ORDER BY created_at, id", pid) : this.all("SELECT * FROM seguimientos ORDER BY created_at, id"));
    }
    if ((p === "/api/seguimientos" || p === "/api/admin/seguimientos") && req.method === "POST") {
      let b; try { b = await req.json(); } catch { return J({ error: "JSON inválido" }, 400); }
      const r = this.appendSeguimiento(b, req.headers.get("x-user-email"));
      if (r.error) return J({ error: r.error }, r.status);
      return J(r.row, r.status);
    }
    if ((p === "/api/aprobaciones-seguimiento" || p === "/api/admin/aprobaciones-seguimiento") && req.method === "GET") {
      return J(this.all("SELECT * FROM aprobaciones_seguimiento ORDER BY updated_at"));
    }
    if (p === "/api/aprobaciones-seguimiento" && req.method === "POST") {
      let b; try { b = await req.json(); } catch { return J({ error: "JSON inválido" }, 400); }
      const r = this.setAprobacionSeguimiento(b, req.headers.get("x-user-email"));
      if (r.error) return J({ error: r.error }, r.status);
      return J(r.row, r.status);
    }
    if (p === "/api/admin/aprobaciones" && req.method === "GET") {
      const e = url.searchParams.get("estado");
      return J(e ? this.all("SELECT * FROM aprobaciones WHERE estado=? ORDER BY updated_at", e) : this.all("SELECT * FROM aprobaciones ORDER BY updated_at"));
    }
    if (p === "/api/admin/comments" && req.method === "GET") {
      const e = url.searchParams.get("estado") || "pendiente";
      return J(e === "todos" ? this.all("SELECT * FROM comentarios ORDER BY id") : this.all("SELECT * FROM comentarios WHERE status=? ORDER BY id", e));
    }
    const m = p.match(/^\/api\/admin\/comments\/(\d+)\/(responder|atender)$/);
    if (m && req.method === "POST") {
      let b = {}; try { b = await req.json(); } catch {}
      const now = new Date().toISOString(), id = Number(m[1]);
      const r = m[2] === "responder"
        ? this.all(`UPDATE comentarios SET respuesta=?, respondido_at=?, status=CASE WHEN ? THEN 'atendido' ELSE status END WHERE id=? RETURNING *`, S(b.respuesta, 4000), now, b.atender === false ? 0 : 1, id)[0]
        : this.all(`UPDATE comentarios SET status='atendido' WHERE id=? RETURNING *`, id)[0];
      if (!r) return J({ error: "no existe" }, 404);
      this.broadcast({ tipo: "comentario", c: r });
      return J(r);
    }
    return new Response("no encontrado", { status: 404 });
  }
  webSocketMessage(ws, m) { if (m === "ping") ws.send("pong"); }
  webSocketClose(ws, code) { try { ws.close(code, "bye"); } catch {} }
}
async function eq(a, b) { const e = new TextEncoder(); const [x, y] = await Promise.all([crypto.subtle.digest("SHA-256", e.encode(a)), crypto.subtle.digest("SHA-256", e.encode(b))]); return crypto.subtle.timingSafeEqual(x, y); }
export default {
  async fetch(req, env) {
    const p = new URL(req.url).pathname;
    const sec = { "x-robots-tag": "noindex", "referrer-policy": "no-referrer", "x-frame-options": "DENY", "cache-control": "private, no-store" };
    const stub = () => env.BOARD.get(env.BOARD.idFromName("bni"));
    const kind = rutaBoard(p);
    if (kind === "admin") {
      const k = req.headers.get("x-admin-key") || "";
      if (!env.ADMIN_KEY || !k || !(await eq(k, env.ADMIN_KEY))) return new Response("prohibido", { status: 403, headers: sec });
      return stub().fetch(req);
    }
    const email = req.headers.get("cf-access-authenticated-user-email");
    if (!email) return new Response("prohibido", { status: 403, headers: sec });
    if (kind === "access-api") {
      const h = new Headers(req.headers); h.set("x-user-email", email);
      return stub().fetch(new Request(req, { headers: h }));
    }
    const r = await env.ASSETS.fetch(req);
    const out = new Response(r.body, r); for (const [k, v] of Object.entries(sec)) out.headers.set(k, v); return out;
  },
};
