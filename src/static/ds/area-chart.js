/*!
 * Buster Design System — area-chart.js
 *
 * <buster-area-chart height="150" max="100" unit="%" labels='["12:00","12:15",...]'>
 *   chart.series = [{ name: "CPU", color: "#22d3ee", values: [..] }, { name: "Memory", color: "#a78bfa", values: [..] }]
 *   Smooth (monotone) neon area chart in SVG. Hover / ←→ keys show a crosshair readout.
 *   Series may also be given as JSON in a `series` attribute (handy from Jinja: series='{{ data|tojson }}').
 *
 * <buster-sparkline values="3,5,4,8,6" color="#34d399" height="22" fill></buster-sparkline>
 */

const NS = "http://www.w3.org/2000/svg";
let uid = 0;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/** Monotone cubic (Fritsch–Carlson) path through points — smooth with no overshoot. */
export function smoothPath(pts) {
  const n = pts.length;
  if (n === 0) return "";
  if (n === 1) return `M${pts[0][0]},${pts[0][1]}`;
  const dx = [], dy = [], m = [], t = [];
  for (let i = 0; i < n - 1; i++) { dx[i] = pts[i + 1][0] - pts[i][0]; dy[i] = pts[i + 1][1] - pts[i][1]; m[i] = dy[i] / (dx[i] || 1); }
  t[0] = m[0]; t[n - 1] = m[n - 2];
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (3 * (dx[i - 1] + dx[i])) / ((2 * dx[i] + dx[i - 1]) / m[i - 1] + (dx[i] + 2 * dx[i - 1]) / m[i]);
  let d = `M${pts[0][0].toFixed(2)},${pts[0][1].toFixed(2)}`;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], h = dx[i] / 3;
    d += `C${(x0 + h).toFixed(2)},${(y0 + t[i] * h).toFixed(2)} ${(x1 - h).toFixed(2)},${(y1 - t[i + 1] * h).toFixed(2)} ${x1.toFixed(2)},${y1.toFixed(2)}`;
  }
  return d;
}

const DEFAULT_COLORS = ["#22d3ee", "#a78bfa", "#f472b6", "#34d399"];

const CHART_STYLE = `
:host { display: block; position: relative; height: var(--chart-height, 150px); font-family: var(--font-sans, system-ui, sans-serif); outline: none; }
svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.grid line { stroke: var(--border-subtle, rgba(148,163,255,.12)); stroke-dasharray: 2 4; }
.axis text { fill: var(--text-muted, #919cc8); font-size: 10.5px; }
.line { fill: none; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }
.glow { fill: none; stroke-width: 6; opacity: calc(.35 * var(--chart-glow, 1)); }
.cross { stroke: var(--border-strong, rgba(148,163,255,.32)); stroke-width: 1; opacity: 0; }
.dot { opacity: 0; stroke: #0b1030; stroke-width: 2; }
:host([data-hover]) .cross, :host([data-hover]) .dot { opacity: 1; }
.tip { position: absolute; top: 0; pointer-events: none; padding: 7px 9px; border-radius: 10px; font-size: 12px; line-height: 1.45;
  color: var(--text-primary, #f1f4ff); background: rgba(10, 14, 40, .92); border: 1px solid var(--border-strong, rgba(148,163,255,.3));
  white-space: nowrap; opacity: 0; transform: translateX(-50%); transition: opacity .12s ease; }
:host([data-hover]) .tip { opacity: 1; }
.tip .k { color: var(--text-muted, #919cc8); }
.tip i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 6px; }
:host(:focus-visible) { box-shadow: var(--focus-ring, 0 0 0 2px #67e8f9); border-radius: 10px; }
`;

class BusterAreaChart extends HTMLElement {
  static get observedAttributes() { return ["series", "labels", "max", "min", "unit", "height"]; }

  constructor() {
    super();
    this._id = `ac${++uid}`;
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${CHART_STYLE}</style><svg part="svg" aria-hidden="true"></svg><div class="tip" part="tooltip"></div>`;
    this._svg = root.querySelector("svg");
    this._tip = root.querySelector(".tip");
    this._series = [];
    this._labels = [];
    this._idx = -1;
  }

  connectedCallback() {
    this.tabIndex = this.tabIndex >= 0 ? this.tabIndex : 0;
    this.setAttribute("role", "img");
    if (this.hasAttribute("height")) this.style.setProperty("--chart-height", `${parseInt(this.getAttribute("height"), 10)}px`);
    this._ro = new ResizeObserver(() => this._render());
    this._ro.observe(this);
    this.addEventListener("pointermove", (e) => this._hoverAt(e));
    this.addEventListener("pointerleave", () => this._setIdx(-1));
    this.addEventListener("blur", () => this._setIdx(-1));
    this.addEventListener("keydown", (e) => {
      const len = this._len();
      if (!len) return;
      if (e.key === "ArrowRight") { e.preventDefault(); this._setIdx(Math.min(len - 1, this._idx + 1)); }
      if (e.key === "ArrowLeft") { e.preventDefault(); this._setIdx(Math.max(0, (this._idx < 0 ? len : this._idx) - 1)); }
      if (e.key === "Escape") this._setIdx(-1);
    });
    this._render();
  }
  disconnectedCallback() { this._ro?.disconnect(); }

  attributeChangedCallback(n, _o, v) {
    try {
      if (n === "series" && v) this._series = JSON.parse(v);
      if (n === "labels" && v) this._labels = JSON.parse(v);
    } catch (err) { console.warn(`[buster-area-chart] invalid ${n} JSON`, err); }
    if (n === "height" && v) this.style.setProperty("--chart-height", `${parseInt(v, 10)}px`);
    if (this.isConnected) this._render();
  }

  get series() { return this._series; }
  set series(v) { this._series = Array.isArray(v) ? v : []; this._render(); }
  get labels() { return this._labels; }
  set labels(v) { this._labels = Array.isArray(v) ? v : []; this._render(); }

  _len() { return Math.max(0, ...this._series.map((s) => (s.values || []).length)); }

  _render() {
    const w = this.clientWidth, h = this.clientHeight;
    if (!w || !h) return;
    const pad = { l: 30, r: 6, t: 8, b: this._labels.length ? 20 : 6 };
    const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
    const all = this._series.flatMap((s) => s.values || []);
    const max = this.hasAttribute("max") ? Number(this.getAttribute("max")) : Math.max(1, ...all) * 1.1;
    const min = this.hasAttribute("min") ? Number(this.getAttribute("min")) : 0;
    const unit = this.getAttribute("unit") || "";
    const len = this._len();
    const X = (i) => pad.l + (len <= 1 ? iw / 2 : (i / (len - 1)) * iw);
    const Y = (v) => pad.t + ih - ((v - min) / (max - min || 1)) * ih;
    this._geo = { X, Y, pad, iw, ih, len, unit };
    this._svg.setAttribute("viewBox", `0 0 ${w} ${h}`);

    let defs = "", body = "";
    const ticks = 4;
    let grid = `<g class="grid">`, axis = `<g class="axis">`;
    for (let k = 0; k <= ticks; k++) {
      const v = min + ((max - min) * k) / ticks;
      const y = Y(v).toFixed(1);
      grid += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${y}" y2="${y}"/>`;
      axis += `<text x="${pad.l - 8}" y="${y}" text-anchor="end" dominant-baseline="middle">${Math.round(v)}${esc(unit)}</text>`;
    }
    if (this._labels.length) {
      const every = Math.ceil(this._labels.length / Math.max(2, Math.floor(iw / 60)));
      this._labels.forEach((lb, i) => {
        if (i % every === 0 || i === this._labels.length - 1) {
          axis += `<text x="${X(i).toFixed(1)}" y="${h - 4}" text-anchor="${i === 0 ? "start" : i === this._labels.length - 1 ? "end" : "middle"}">${esc(lb)}</text>`;
        }
      });
    }
    grid += "</g>"; axis += "</g>";

    this._series.forEach((s, si) => {
      const color = s.color || DEFAULT_COLORS[si % DEFAULT_COLORS.length];
      const pts = (s.values || []).map((v, i) => [X(i), Y(Math.max(min, Math.min(max, v)))]);
      if (!pts.length) return;
      const line = smoothPath(pts);
      const area = `${line}L${pts[pts.length - 1][0].toFixed(2)},${(pad.t + ih).toFixed(2)}L${pts[0][0].toFixed(2)},${(pad.t + ih).toFixed(2)}Z`;
      const gid = `${this._id}g${si}`, fid = `${this._id}f${si}`;
      defs += `<linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity="${si === 0 ? 0.42 : 0.3}"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient>`;
      defs += `<filter id="${fid}" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="3"/></filter>`;
      body += `<path d="${area}" fill="url(#${gid})"/>`;
      body += `<path class="glow" d="${line}" stroke="${color}" filter="url(#${fid})"/>`;
      body += `<path class="line" d="${line}" stroke="${color}"/>`;
      body += `<circle class="dot" data-s="${si}" r="4" fill="${color}"/>`;
    });
    this._svg.innerHTML = `<defs>${defs}</defs>${grid}${body}<line class="cross" x1="0" x2="0" y1="${pad.t}" y2="${pad.t + ih}"/>${axis}`;
    this._dots = [...this._svg.querySelectorAll(".dot")];
    this._cross = this._svg.querySelector(".cross");

    const summary = this._series.map((s) => {
      const v = s.values || [];
      return `${s.name || "series"} latest ${v[v.length - 1] ?? "–"}${unit}, peak ${v.length ? Math.max(...v) : "–"}${unit}`;
    }).join("; ");
    this.setAttribute("aria-label", this.getAttribute("label") ? `${this.getAttribute("label")}: ${summary}` : summary);
    if (this._idx >= 0) this._setIdx(Math.min(this._idx, len - 1), true);
  }

  _hoverAt(e) {
    if (!this._geo || !this._geo.len) return;
    const r = this.getBoundingClientRect();
    const { pad, iw, len } = this._geo;
    const u = (e.clientX - r.left - pad.l) / iw;
    this._setIdx(Math.max(0, Math.min(len - 1, Math.round(u * (len - 1)))));
  }

  _setIdx(i, force) {
    if (i === this._idx && !force) return;
    this._idx = i;
    if (i < 0 || !this._geo) { this.removeAttribute("data-hover"); return; }
    const { X, Y, unit } = this._geo;
    const x = X(i);
    this._cross.setAttribute("x1", x); this._cross.setAttribute("x2", x);
    let html = this._labels[i] != null ? `<div class="k">${esc(this._labels[i])}</div>` : "";
    this._series.forEach((s, si) => {
      const v = (s.values || [])[i];
      const dot = this._dots[si];
      if (dot && v != null) { dot.setAttribute("cx", x); dot.setAttribute("cy", Y(v)); }
      const color = s.color || DEFAULT_COLORS[si % DEFAULT_COLORS.length];
      html += `<div><i style="background:${color}"></i>${esc(s.name || "")} <b>${v ?? "–"}${esc(unit)}</b></div>`;
    });
    this._tip.innerHTML = html;
    this._tip.style.left = `${Math.max(50, Math.min(this.clientWidth - 50, x))}px`;
    this.setAttribute("data-hover", "");
  }
}

/* ---------------- sparkline ---------------- */
class BusterSparkline extends HTMLElement {
  static get observedAttributes() { return ["values", "color", "height", "fill"]; }
  constructor() { super(); this._id = `sp${++uid}`; this.attachShadow({ mode: "open" }); }
  connectedCallback() { this._render(); }
  attributeChangedCallback() { if (this.isConnected) this._render(); }
  get values() { return this._values || (this.getAttribute("values") || "").split(",").map(Number).filter((n) => !Number.isNaN(n)); }
  set values(v) { this._values = Array.isArray(v) ? v.map(Number) : null; this._render(); }
  _render() {
    const vals = this.values;
    const h = Number(this.getAttribute("height")) || 22, w = 80;
    const color = this.getAttribute("color") || "#22d3ee";
    if (vals.length < 2) { this.shadowRoot.innerHTML = ""; return; }
    const mn = Math.min(...vals), mx = Math.max(...vals), span = mx - mn || 1;
    const pts = vals.map((v, i) => [2 + (i / (vals.length - 1)) * (w - 6), 2 + (h - 4) - ((v - mn) / span) * (h - 4)]);
    const line = smoothPath(pts);
    const last = pts[pts.length - 1];
    const fill = this.hasAttribute("fill") ? `<path d="${line}L${last[0]},${h}L${pts[0][0]},${h}Z" fill="url(#${this._id})"/>` : "";
    this.shadowRoot.innerHTML = `<style>:host{display:inline-block;width:var(--spark-width,80px);height:${h}px;vertical-align:middle}svg{width:100%;height:100%;overflow:visible}</style>
      <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="${this._id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      ${fill}<path d="${line}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" vector-effect="non-scaling-stroke" style="filter:drop-shadow(0 0 calc(3px * var(--chart-glow,1)) ${color})"/>
      <circle cx="${last[0]}" cy="${last[1]}" r="2" fill="${color}"/></svg>`;
    this.setAttribute("role", "img");
    if (!this.hasAttribute("aria-label")) this.setAttribute("aria-label", `Trend, latest ${vals[vals.length - 1]}`);
  }
}

if (!customElements.get("buster-area-chart")) customElements.define("buster-area-chart", BusterAreaChart);
if (!customElements.get("buster-sparkline")) customElements.define("buster-sparkline", BusterSparkline);
export { BusterAreaChart, BusterSparkline };
