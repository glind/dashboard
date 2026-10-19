/*!
 * Buster Design System — network-universe.js
 * <buster-network height="240" labels="auto|on|off" static>
 *
 *   net.nodes = [{ id, label, kind, status, group, meta }]
 *       kind:   server | laptop | desktop | phone | router | iot | cloud | nas | printer | tv | hub
 *       status: ok | warn | degraded | down | offline
 *   net.links = [{ source, target, status, traffic }]   // source defaults to the hub, traffic 0..1
 *   net.update({ nodes, links })                         // throttled (≤ 2 applies / s)
 *
 * Devices orbit a glowing globe/hub; light lines carry data pulses. Unhealthy links dim or
 * glow AMBER (never red flashing). Hover/focus a node for a tooltip. Static when motion is off.
 * Events: "buster-node-hover", "buster-node-click" { detail: node }.
 */
import { Motion, bindMotion } from "./motion.js";

const KIND_COLOR = {
  hub: "#67e8f9", server: "#22d3ee", nas: "#38bdf8", router: "#60a5fa", cloud: "#7dd3fc",
  laptop: "#a78bfa", desktop: "#8b5cf6", phone: "#f472b6", tv: "#e879f9", iot: "#34d399", printer: "#93c5fd",
};
const WARN = "#fbbf24";
const DIM = "#5b6488";
const isWarn = (s) => s === "warn" || s === "degraded" || s === "slow";
const isDown = (s) => s === "down" || s === "offline" || s === "failed";

const STYLE = `
:host { display: block; position: relative; height: var(--net-height, 240px); min-height: 160px; contain: layout paint; outline: none; }
canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
.tip { position: absolute; z-index: 2; pointer-events: none; min-width: 140px; padding: 8px 10px; border-radius: 10px;
  font: 500 12px/1.4 var(--font-sans, system-ui, sans-serif); color: var(--text-primary, #f1f4ff);
  background: rgba(10, 14, 40, .92); border: 1px solid var(--border-strong, rgba(148,163,255,.3));
  box-shadow: 0 10px 30px -10px rgba(0,0,0,.8); opacity: 0; transform: translate(-50%, calc(-100% - 12px)) scale(.96);
  transition: opacity .12s ease, transform .18s cubic-bezier(.34,1.45,.64,1); white-space: nowrap; }
.tip.show { opacity: 1; transform: translate(-50%, calc(-100% - 12px)); }
.tip b { display: block; font-weight: 600; font-size: 12.5px; }
.tip .row { display: flex; align-items: center; gap: 6px; color: var(--text-muted, #919cc8); }
.tip .d { width: 7px; height: 7px; border-radius: 50%; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
:host(:focus-visible) { box-shadow: var(--focus-ring, 0 0 0 2px #67e8f9); border-radius: 12px; }
`;

function sprite(color, size = 64) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  const grd = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grd.addColorStop(0, color);
  grd.addColorStop(0.18, color + "cc");
  grd.addColorStop(0.45, color + "33");
  grd.addColorStop(1, color + "00");
  g.fillStyle = grd;
  g.fillRect(0, 0, size, size);
  return c;
}

class BusterNetwork extends HTMLElement {
  static get observedAttributes() { return ["height", "labels", "static"]; }

  constructor() {
    super();
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${STYLE}</style><canvas part="canvas"></canvas><div class="tip" part="tooltip"></div><ul class="sr" aria-live="polite"></ul>`;
    this._canvas = root.querySelector("canvas");
    this._ctx = this._canvas.getContext("2d");
    this._tip = root.querySelector(".tip");
    this._sr = root.querySelector(".sr");
    this._nodes = [];
    this._links = [];
    this._pos = new Map();
    this._sprites = new Map();
    this._hover = null;
    this._lastApply = 0;
    this._visible = true;
    this._dots = Array.from({ length: 260 }, (_, i) => {
      // golden-spiral points on a unit sphere (globe "data dots")
      const y = 1 - (i / 259) * 2, r = Math.sqrt(1 - y * y), th = i * 2.399963;
      return { lat: Math.asin(y), lon: th % (Math.PI * 2), r };
    });
  }

  connectedCallback() {
    this.tabIndex = this.tabIndex >= 0 ? this.tabIndex : 0;
    this.setAttribute("role", "img");
    if (!this.hasAttribute("aria-label")) this.setAttribute("aria-label", "Network map");
    if (this.hasAttribute("height")) this.style.setProperty("--net-height", `${parseInt(this.getAttribute("height"), 10)}px`);
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(this);
    this._io = new IntersectionObserver((es) => { this._visible = es.some((e) => e.isIntersecting); this._sync(); });
    this._io.observe(this);
    this._unsubMotion = bindMotion(this);
    this._onMove = (e) => this._pointer(e);
    this._onLeave = () => this._setHover(null);
    this._onClick = () => this._hover && this.dispatchEvent(new CustomEvent("buster-node-click", { bubbles: true, detail: this._hover }));
    this._onKey = (e) => this._key(e);
    this.addEventListener("pointermove", this._onMove);
    this.addEventListener("pointerleave", this._onLeave);
    this.addEventListener("click", this._onClick);
    this.addEventListener("keydown", this._onKey);
    this.addEventListener("blur", this._onLeave);
    this._resize();
  }

  disconnectedCallback() {
    this._ro?.disconnect(); this._io?.disconnect(); this._unsubMotion?.(); this._stop();
    clearTimeout(this._applyTimer);
  }

  attributeChangedCallback(n, _o, v) {
    if (n === "height" && v) this.style.setProperty("--net-height", `${parseInt(v, 10)}px`);
    if (this.isConnected) { this._layout(); this._sync(); }
  }

  get nodes() { return this._nodes; }
  set nodes(v) { this.update({ nodes: v }); }
  get links() { return this._links; }
  set links(v) { this.update({ links: v }); }

  /** Throttled data update (≤ 2 applies per second). */
  update({ nodes, links } = {}) {
    this._pending = { nodes: nodes ?? this._pending?.nodes ?? this._nodes, links: links ?? this._pending?.links ?? this._links };
    const wait = 500 - (performance.now() - this._lastApply);
    clearTimeout(this._applyTimer);
    if (wait <= 0) this._apply();
    else this._applyTimer = setTimeout(() => this._apply(), wait);
  }

  _apply() {
    if (!this._pending) return;
    this._nodes = Array.isArray(this._pending.nodes) ? this._pending.nodes.slice() : [];
    this._links = Array.isArray(this._pending.links) ? this._pending.links.slice() : [];
    this._pending = null;
    this._lastApply = performance.now();
    this._layout();
    this._a11y();
    this._draw(this._running ? performance.now() : 0);
  }

  onMotion() { this._sync(); }

  _sync() {
    const animate = Motion.level !== "off" && !this.hasAttribute("static") && this._visible;
    if (animate) this._start(); else { this._stop(); this._draw(0); }
  }
  _start() {
    this._stop();
    this._running = true;
    this._unsubFrame = Motion.onFrame((now) => this._draw(now), { fps: Motion.level === "full" ? 50 : 24 });
  }
  _stop() { this._unsubFrame?.(); this._unsubFrame = null; this._running = false; }

  _resize() {
    const w = this.clientWidth, h = this.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this._w = w; this._h = h; this._dpr = dpr;
    this._font = `500 10.5px ${getComputedStyle(this).getPropertyValue("--font-sans").trim() || "system-ui, sans-serif"}`;
    this._canvas.width = Math.round(w * dpr);
    this._canvas.height = Math.round(h * dpr);
    this._layout();
    this._draw(this._running ? performance.now() : 0);
  }

  _layout() {
    const w = this._w, h = this._h;
    if (!w) return;
    const cx = w / 2, cy = h / 2;
    this._R = Math.min(w * 0.19, h * 0.27);
    this._center = { x: cx, y: cy };
    const devs = this._nodes.filter((n) => n.kind !== "hub" && n.id !== "hub");
    const sorted = devs.slice().sort((a, b) => String(a.group ?? "").localeCompare(String(b.group ?? "")) || String(a.id).localeCompare(String(b.id)));
    const n = sorted.length || 1;
    const rx = w * 0.41, ry = h * 0.38;
    this._pos.clear();
    sorted.forEach((node, i) => {
      const a = -Math.PI / 2 + (i / n) * Math.PI * 2 + 0.35;
      const ring = i % 2 ? 0.8 : 1;
      const x = cx + Math.cos(a) * rx * ring;
      const y = cy + Math.sin(a) * ry * ring;
      const depth = (Math.sin(a) + 1) / 2; // 0 = far (top), 1 = near (bottom)
      this._pos.set(node.id, { x, y, depth, node });
    });
  }

  _a11y() {
    this._sr.innerHTML = "";
    for (const n of this._nodes) {
      const li = document.createElement("li");
      li.textContent = `${n.label || n.id} (${n.kind || "device"}): ${n.status || "ok"}`;
      this._sr.appendChild(li);
    }
    const bad = this._nodes.filter((n) => isWarn(n.status) || isDown(n.status)).length;
    this.setAttribute("aria-label", `Network map: ${this._nodes.length} devices${bad ? `, ${bad} need attention` : ", all healthy"}`);
  }

  _spr(color) {
    if (!this._sprites.has(color)) this._sprites.set(color, sprite(color));
    return this._sprites.get(color);
  }

  _nodeColor(n) {
    if (isDown(n.status)) return DIM;
    if (isWarn(n.status)) return WARN;
    return KIND_COLOR[n.kind] || "#67e8f9";
  }

  _endpoint(id) {
    if (id == null || id === "hub" || !this._pos.has(id)) return null;
    return this._pos.get(id);
  }

  _draw(now) {
    const ctx = this._ctx;
    if (!ctx || !this._w) return;
    const { x: cx, y: cy } = this._center;
    const R = this._R;
    const full = Motion.level === "full" && this._running;
    const ops = (document.documentElement.dataset.mode || document.body?.dataset.mode) === "operations";
    const t = now / 1000;
    ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
    ctx.clearRect(0, 0, this._w, this._h);

    // ---- outer orbit rings (3D-ish) ----
    ctx.save();
    ctx.strokeStyle = "rgba(129,140,248,0.16)";
    ctx.setLineDash([2, 6]);
    ctx.beginPath(); ctx.ellipse(cx, cy, this._w * 0.41, this._h * 0.38, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(cx, cy, this._w * 0.33, this._h * 0.3, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();

    // ---- globe glow ----
    const glowA = ops ? 0.12 : 0.32;
    let g = ctx.createRadialGradient(cx, cy, R * 0.6, cx, cy, R * 2.1);
    g.addColorStop(0, `rgba(56,189,248,${glowA})`);
    g.addColorStop(0.45, `rgba(124,58,237,${glowA * 0.5})`);
    g.addColorStop(1, "rgba(124,58,237,0)");
    ctx.fillStyle = g;
    ctx.fillRect(cx - R * 2.2, cy - R * 2.2, R * 4.4, R * 4.4);

    // ---- links (under nodes) ----
    for (const l of this._links) {
      const a = this._endpoint(l.source), b = this._endpoint(l.target);
      if (!a && !b) continue;
      const p1 = a || this._hubEdge(b), p2 = b || this._hubEdge(a);
      const st = l.status || "ok";
      const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2;
      // bend control point away from the centre for a soft arc
      const dx = mx - cx, dy = my - cy, dl = Math.hypot(dx, dy) || 1;
      const k = a && b ? 30 : 12;
      const c = { x: mx + (dx / dl) * k, y: my + (dy / dl) * k };
      l._geo = { p1, p2, c };
      ctx.save();
      ctx.lineCap = "round";
      if (isDown(st)) {
        ctx.strokeStyle = "rgba(120,128,170,0.18)"; ctx.setLineDash([3, 6]); ctx.lineWidth = 1;
      } else if (isWarn(st)) {
        const breathe = full ? 0.42 + 0.14 * Math.sin(t * 1.6) : 0.5;   // slow, soft — never flashing
        if (!ops) { ctx.strokeStyle = `rgba(251,191,36,${breathe * 0.35})`; ctx.lineWidth = 5; this._curve(p1, c, p2); }
        ctx.strokeStyle = `rgba(251,191,36,${breathe + 0.15})`; ctx.setLineDash([5, 5]); ctx.lineWidth = 1.4;
      } else {
        const lg = ctx.createLinearGradient(p1.x, p1.y, p2.x, p2.y);
        lg.addColorStop(0, "rgba(34,211,238,0.6)"); lg.addColorStop(1, "rgba(167,139,250,0.55)");
        if (!ops && Motion.level !== "low") { ctx.strokeStyle = "rgba(99,102,241,0.14)"; ctx.lineWidth = 5; this._curve(p1, c, p2); }
        ctx.strokeStyle = lg; ctx.lineWidth = 1.3;
      }
      this._curve(p1, c, p2);
      ctx.restore();
    }

    // ---- globe ----
    this._globe(ctx, cx, cy, R, t, ops);

    // ---- data pulses ----
    for (const l of this._links) {
      if (!l._geo || isDown(l.status)) continue;
      const warn = isWarn(l.status);
      const traffic = Math.max(0.15, Math.min(1, l.traffic ?? 0.5));
      const count = Motion.level === "full" && !ops ? Math.ceil(traffic * 3) : 1;
      const dur = (warn ? 4.2 : 2.8 - traffic) * 1000;
      const seed = (String(l.source) + String(l.target)).length * 0.137;
      for (let i = 0; i < count; i++) {
        const u = this._running ? ((now / dur + seed + i / count) % 1) : 0.5;
        const { p1, c, p2 } = l._geo;
        const x = (1 - u) ** 2 * p1.x + 2 * (1 - u) * u * c.x + u * u * p2.x;
        const y = (1 - u) ** 2 * p1.y + 2 * (1 - u) * u * c.y + u * u * p2.y;
        const s = warn ? 10 : 12 + traffic * 6;
        ctx.globalAlpha = warn ? 0.7 : 0.95;
        ctx.drawImage(this._spr(warn ? WARN : "#a5f3fc"), x - s / 2, y - s / 2, s, s);
        ctx.globalAlpha = 1;
      }
    }

    // ---- nodes ----
    const showLabels = this.getAttribute("labels") === "on" || (this.getAttribute("labels") !== "off" && this._w >= 380);
    ctx.font = this._font;
    ctx.textAlign = "center";
    const order = [...this._pos.values()].sort((p, q) => p.depth - q.depth);
    for (const p of order) {
      const n = p.node;
      const color = this._nodeColor(n);
      const size = 4.2 + p.depth * 2.2;
      const hov = this._hover && this._hover.id === n.id;
      const pulse = this._running && isWarn(n.status) ? 1 + 0.12 * Math.sin(t * 1.8) : 1;
      const halo = (hov ? 46 : 30 + p.depth * 8) * pulse * (ops ? 0.75 : 1);
      ctx.globalAlpha = isDown(n.status) ? 0.35 : ops ? 0.6 : 0.9;
      ctx.drawImage(this._spr(color), p.x - halo / 2, p.y - halo / 2, halo, halo);
      ctx.globalAlpha = 1;
      ctx.fillStyle = "#0a0f2e";
      ctx.beginPath(); ctx.arc(p.x, p.y, size + 1.6, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = color;
      ctx.beginPath(); ctx.arc(p.x, p.y, size, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.beginPath(); ctx.arc(p.x - size * 0.3, p.y - size * 0.3, size * 0.32, 0, Math.PI * 2); ctx.fill();
      if (showLabels) {
        ctx.fillStyle = isDown(n.status) ? "rgba(160,168,205,0.6)" : hov ? "#f1f4ff" : "rgba(188,197,234,0.85)";
        ctx.fillText(n.label || n.id, p.x, p.y + size + 13);
      }
    }
  }

  _curve(p1, c, p2) {
    const ctx = this._ctx;
    ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.quadraticCurveTo(c.x, c.y, p2.x, p2.y); ctx.stroke();
  }

  _hubEdge(p) {
    const { x: cx, y: cy } = this._center;
    const dx = p.x - cx, dy = p.y - cy, d = Math.hypot(dx, dy) || 1;
    return { x: cx + (dx / d) * this._R * 1.02, y: cy + (dy / d) * this._R * 1.02 };
  }

  _globe(ctx, cx, cy, R, t, ops) {
    const rot = this._running ? t * 0.18 : 0.6;
    // sphere body
    let g = ctx.createRadialGradient(cx - R * 0.38, cy - R * 0.42, R * 0.05, cx, cy, R);
    g.addColorStop(0, "#4f6bf0");
    g.addColorStop(0.35, "#2a2f93");
    g.addColorStop(0.75, "#141558");
    g.addColorStop(1, "#0b0c35");
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();

    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip();
    // latitude lines
    ctx.lineWidth = 0.8;
    const tilt = 0.32;
    for (let k = -2; k <= 2; k++) {
      const lat = (k * Math.PI) / 7;
      const ry = R * Math.cos(lat) * Math.sin(tilt);
      ctx.strokeStyle = "rgba(125,211,252,0.22)";
      ctx.beginPath(); ctx.ellipse(cx, cy + R * Math.sin(lat) * Math.cos(tilt), R * Math.cos(lat), Math.max(ry, 0.5), 0, 0, Math.PI * 2); ctx.stroke();
    }
    // meridians
    for (let k = 0; k < 6; k++) {
      const phi = rot + (k * Math.PI) / 6;
      const s = Math.sin(phi);
      const front = Math.cos(phi) > 0;
      ctx.strokeStyle = front ? "rgba(125,211,252,0.3)" : "rgba(125,211,252,0.1)";
      ctx.save(); ctx.translate(cx, cy); ctx.scale(Math.abs(s) < 0.02 ? 0.02 : s, 1);
      ctx.beginPath(); ctx.arc(0, 0, R, -Math.PI / 2, Math.PI / 2); ctx.restore(); ctx.stroke();
    }
    // data dots (front hemisphere only)
    const step = Motion.level === "full" && !ops ? 1 : 2;
    for (let i = 0; i < this._dots.length; i += step) {
      const d = this._dots[i];
      const lon = d.lon + rot;
      const z = Math.cos(d.lat) * Math.cos(lon);
      if (z <= 0.05) continue;
      const x = cx + R * Math.cos(d.lat) * Math.sin(lon);
      const y = cy - R * Math.sin(d.lat);
      ctx.fillStyle = `rgba(165,243,252,${(0.15 + z * 0.55).toFixed(2)})`;
      ctx.fillRect(x - 0.7, y - 0.7, 1.4, 1.4);
    }
    // terminator shade
    g = ctx.createRadialGradient(cx + R * 0.5, cy + R * 0.55, R * 0.2, cx + R * 0.3, cy + R * 0.3, R * 1.3);
    g.addColorStop(0, "rgba(3,4,18,0.55)"); g.addColorStop(1, "rgba(3,4,18,0)");
    ctx.fillStyle = g; ctx.fillRect(cx - R, cy - R, R * 2, R * 2);
    ctx.restore();

    // rim light
    ctx.lineWidth = 1.4;
    const rg = ctx.createLinearGradient(cx - R, cy - R, cx + R, cy + R);
    rg.addColorStop(0, "rgba(103,232,249,0.9)"); rg.addColorStop(0.5, "rgba(139,92,246,0.25)"); rg.addColorStop(1, "rgba(232,121,249,0.7)");
    ctx.strokeStyle = rg;
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.stroke();
    // equatorial ring
    ctx.save();
    ctx.strokeStyle = ops ? "rgba(129,140,248,0.3)" : "rgba(129,140,248,0.55)";
    ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.ellipse(cx, cy + R * 0.05, R * 1.45, R * 0.36, -0.12, Math.PI * 0.05, Math.PI * 0.95); ctx.stroke(); // front arc
    ctx.strokeStyle = "rgba(129,140,248,0.18)";
    ctx.beginPath(); ctx.ellipse(cx, cy + R * 0.05, R * 1.45, R * 0.36, -0.12, Math.PI * 1.05, Math.PI * 1.95); ctx.stroke();
    ctx.restore();
  }

  _pointer(e) {
    const r = this.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    let best = null, bd = 18;
    for (const p of this._pos.values()) {
      const d = Math.hypot(p.x - x, p.y - y);
      if (d < bd) { bd = d; best = p.node; }
    }
    this._setHover(best);
  }

  _key(e) {
    const list = [...this._pos.values()].map((p) => p.node);
    if (!list.length) return;
    if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(e.key)) {
      e.preventDefault();
      const i = this._hover ? list.findIndex((n) => n.id === this._hover.id) : -1;
      const dir = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
      this._setHover(list[(i + dir + list.length) % list.length]);
    } else if (e.key === "Escape") this._setHover(null);
    else if (e.key === "Enter" && this._hover) this._onClick();
  }

  _setHover(node) {
    if ((node && node.id) === (this._hover && this._hover.id)) return;
    this._hover = node;
    this.style.cursor = node ? "pointer" : "";
    if (node) {
      const p = this._pos.get(node.id);
      const st = node.status || "ok";
      const dc = isDown(st) ? DIM : isWarn(st) ? WARN : "#34d399";
      const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
      this._tip.innerHTML = `<b>${esc(node.label || node.id)}</b><div class="row"><i class="d" style="background:${dc}"></i>${esc(st)} · ${esc(node.kind || "device")}</div>${node.meta ? `<div class="row">${esc(node.meta)}</div>` : ""}`;
      this._tip.style.left = `${Math.max(80, Math.min(this._w - 80, p.x))}px`;
      this._tip.style.top = `${p.y}px`;
      this._tip.classList.add("show");
      this.dispatchEvent(new CustomEvent("buster-node-hover", { bubbles: true, detail: node }));
    } else this._tip.classList.remove("show");
    if (!this._running) this._draw(0);
  }
}

if (!customElements.get("buster-network")) customElements.define("buster-network", BusterNetwork);
export { BusterNetwork };
