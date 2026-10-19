/*!
 * Buster Design System — seasons-fx.js  (lazy-loaded by seasons.js when a season is active)
 *  1. Companion accessories (SVG layers for <buster-companion> / <buster-agent>)
 *  2. Backdrop particles inside <buster-space>: halloween bats + fog, thanksgiving leaves,
 *     winter snow + twinkle lights, new-year confetti.
 * Everything is governed by motion.js: full = all effects, low = fewer particles at 24 fps,
 * off/reduced = one static frame. Operations mode: no particles at all (accessory = hat only).
 */
import { Motion } from "./motion.js";

/* =====================================================================
   1. Accessories — drawn in the companion's 240×240 coordinate space
   ===================================================================== */
function accessory(season, variant, { ops, p }) {
  const id = (n) => `${p}s-${n}`;
  if (season === "winter" && variant === "newyear") {
    return {
      svg: `<defs><linearGradient id="${id("ny")}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fde047"/><stop offset=".55" stop-color="#f472b6"/><stop offset="1" stop-color="#a855f7"/></linearGradient></defs>
        <g class="acc-hat" transform="rotate(8 121 54)">
          <path d="M101 55 L121 4 L141 55 Z" fill="url(#${id("ny")})" stroke="rgba(255,255,255,.35)" stroke-width="1"/>
          <path d="M108 38 L134 38 M113 24 L129 24" stroke="rgba(255,255,255,.55)" stroke-width="2.4" stroke-linecap="round"/>
          <circle cx="114" cy="47" r="2" fill="#fff" opacity=".85"/><circle cx="128" cy="31" r="1.8" fill="#fff" opacity=".85"/><circle cx="125" cy="47" r="1.6" fill="#22d3ee"/>
          <ellipse cx="121" cy="55" rx="22" ry="4.2" fill="#f0abfc"/>
          <circle cx="121" cy="4" r="6" fill="#fde047"/><path d="M121 -6 V-1 M113 -2 L117 1 M129 -2 L125 1" stroke="#fde047" stroke-width="1.8" stroke-linecap="round"/>
        </g>
        <g class="acc-extra">
          <rect x="44" y="34" width="6" height="3" rx="1" fill="#fde047" transform="rotate(30 47 35)"/>
          <rect x="190" y="22" width="6" height="3" rx="1" fill="#f472b6" transform="rotate(-25 193 23)"/>
          <rect x="202" y="78" width="5" height="3" rx="1" fill="#22d3ee" transform="rotate(50 204 79)"/>
          <rect x="36" y="92" width="5" height="3" rx="1" fill="#a3e635" transform="rotate(-40 38 93)"/>
          <circle cx="170" cy="14" r="2" fill="#fde047"/><circle cx="66" cy="20" r="1.8" fill="#c084fc"/>
        </g>`,
    };
  }
  if (season === "halloween") {
    return {
      eye: "#fdba74", // pumpkin-glow eyes
      svg: `<defs><linearGradient id="${id("hw")}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4c1d95"/><stop offset="1" stop-color="#1a0b2e"/></linearGradient></defs>
        <g class="acc-hat">
          <ellipse cx="120" cy="55" rx="56" ry="9.5" fill="#1a0b2e" stroke="#a855f7" stroke-opacity=".7" stroke-width="1.2"/>
          <path d="M94 55 C101 40 107 27 113 16 C118 7 130 2 144 8 C134 10 129 16 129 24 C130 35 137 45 147 55 Z" fill="url(#${id("hw")})" stroke="#a855f7" stroke-opacity=".55" stroke-width="1"/>
          <path d="M98 47 C113 50.5 129 50.5 143.5 47 L145.5 53.5 C129 57 112 57 96 53.5 Z" fill="#f97316"/>
          <rect x="114" y="46.5" width="11" height="8.5" rx="1.6" fill="none" stroke="#fde047" stroke-width="1.7"/>
          <path d="M114 22 C118 18 123 17 127 18" stroke="rgba(255,255,255,.18)" stroke-width="2" fill="none" stroke-linecap="round"/>
        </g>
        <g class="acc-extra"><path d="M187 104 l3 -6 3 6 -3 -2z M37 98 l3 -6 3 6 -3 -2z" fill="#a3e635" opacity=".85"/></g>`,
    };
  }
  if (season === "thanksgiving") {
    return {
      svg: `<defs><linearGradient id="${id("tg")}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6b4423"/><stop offset="1" stop-color="#2a170a"/></linearGradient></defs>
        <g class="acc-hat">
          <ellipse cx="120" cy="55" rx="52" ry="9" fill="#2a170a" stroke="#b45309" stroke-opacity=".75" stroke-width="1.2"/>
          <path d="M95 55 L100 17 Q120 11 140 17 L145 55 Z" fill="url(#${id("tg")})" stroke="#b45309" stroke-opacity=".5" stroke-width="1"/>
          <path d="M97.4 43 L142.6 43 L143.8 52.5 L96.2 52.5 Z" fill="#140b04"/>
          <rect x="113" y="41.5" width="14" height="12" rx="1.6" fill="none" stroke="#fbbf24" stroke-width="2.2"/>
          <path d="M104 21 Q112 18 120 18" stroke="rgba(255,255,255,.15)" stroke-width="2" fill="none" stroke-linecap="round"/>
        </g>
        <g class="acc-extra" transform="translate(152 44) rotate(38)">
          <path d="M0 -11 C3 -8 7 -7 8 -3 C6 -2 6 0 8 2 C5 3 3 5 2 9 L0 13 L-2 9 C-3 5 -5 3 -8 2 C-6 0 -6 -2 -8 -3 C-7 -7 -3 -8 0 -11Z" fill="#f97316" stroke="#c2410c" stroke-width=".8"/>
          <path d="M0 -8 V13" stroke="#9a3412" stroke-width="1"/>
        </g>`,
    };
  }
  if (season === "winter") {
    return {
      svg: `<defs><linearGradient id="${id("sw")}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f87171"/><stop offset=".6" stop-color="#dc2626"/><stop offset="1" stop-color="#991b1b"/></linearGradient></defs>
        <g class="acc-body acc-extra">
          <path d="M92 148 Q120 160 148 148 L149 159 Q120 172 91 159 Z" fill="#dc2626"/>
          <path d="M92 152.5 Q120 164.5 148.5 152.5" stroke="#22c55e" stroke-width="2.4" fill="none"/>
          <path d="M127 160 L131 187 L143 185 L138 157 Z" fill="#dc2626"/>
          <path d="M129.5 175 L141.5 173.5" stroke="#22c55e" stroke-width="2.4"/>
          <path d="M131 187 l1 4 M135 186.5 l1 4 M139 186 l1 4 M142.5 185.5 l1 4" stroke="#fecaca" stroke-width="1.6" stroke-linecap="round"/>
        </g>
        <g class="acc-hat">
          <path d="M80 55 C78 31 100 12 127 12 C152 12 173 22 187 40 L179 47 C170 36 158 32 153 40 C150 45 154 51 160 55 Z" fill="url(#${id("sw")})"/>
          <path d="M104 22 C112 17 122 15 130 16" stroke="rgba(255,255,255,.25)" stroke-width="2.4" fill="none" stroke-linecap="round"/>
          <rect x="73" y="47" width="95" height="15" rx="7.5" fill="#f1f5f9"/>
          <path d="M80 51 h80" stroke="#cbd5e1" stroke-width="1.4" stroke-dasharray="1 4" stroke-linecap="round"/>
          <circle cx="184" cy="46" r="8.5" fill="#f8fafc"/><circle cx="181.5" cy="43.5" r="3" fill="#fff"/>
        </g>`,
    };
  }
  return null;
}

/* =====================================================================
   2. Backdrop particles
   ===================================================================== */
const DPR_CAP = 1.5;
let canvas = null, ctx = null, W = 0, H = 0, dpr = 1;
let parts = [], kind = "", unsub = null, lastT = 0;

function rng(seed) { let s = seed; return () => ((s = (s * 16807) % 2147483647) / 2147483647); }

function currentKind() {
  const h = document.documentElement;
  if (h.dataset.mode === "operations") return "";
  const s = h.dataset.season;
  if (s === "winter" && h.dataset.seasonVariant === "newyear") return "newyear";
  return s === "halloween" || s === "thanksgiving" || s === "winter" ? s : "";
}

function ensureCanvas() {
  const space = document.querySelector("buster-space");
  if (!space) return false;
  if (!canvas || !canvas.isConnected) {
    canvas = document.createElement("canvas");
    canvas.className = "bds-season-fx";
    space.appendChild(canvas);
    ctx = canvas.getContext("2d");
  }
  return true;
}

function resize() {
  if (!canvas) return;
  dpr = Math.min(window.devicePixelRatio || 1, DPR_CAP);
  W = window.innerWidth; H = window.innerHeight;
  canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
}

function seed() {
  const r = rng(4242);
  const low = Motion.level !== "full";
  const area = (W * H) / (1536 * 1024);
  const n = (full, lo) => Math.max(3, Math.round((low ? lo : full) * Math.min(1.4, Math.max(0.35, area))));
  parts = [];
  if (kind === "winter" || kind === "newyear") {
    for (let i = 0, c = n(kind === "newyear" ? 70 : 140, 50); i < c; i++) {
      const z = r();
      parts.push({ t: "snow", x: r() * W, y: r() * H, r: 0.6 + z * 2.2, vy: 14 + z * 34, ph: r() * 6.28, a: 0.35 + z * 0.55 });
    }
  }
  if (kind === "winter") {
    const bulbs = Math.round(W / 64);
    const cols = ["#ef4444", "#22c55e", "#fbbf24", "#38bdf8"];
    for (let i = 0; i <= bulbs; i++) parts.push({ t: "bulb", i, n: bulbs, c: cols[i % 4], ph: r() * 6.28, sp: 0.8 + r() * 1.6 });
  }
  if (kind === "newyear") {
    const cols = ["#fde047", "#f472b6", "#22d3ee", "#a78bfa", "#ffffff", "#a3e635"];
    for (let i = 0, c = n(70, 28); i < c; i++) parts.push({ t: "conf", x: r() * W, y: r() * H, vy: 30 + r() * 40, rot: r() * 6.28, vr: (r() - 0.5) * 6, w: 4 + r() * 4, h: 2 + r() * 3, c: cols[i % cols.length], ph: r() * 6.28 });
  }
  if (kind === "thanksgiving") {
    const cols = ["#f59e0b", "#ea580c", "#b45309", "#facc15", "#dc2626"];
    for (let i = 0, c = n(22, 10); i < c; i++) parts.push({ t: "leaf", x: r() * W, y: r() * H, vy: 18 + r() * 26, rot: r() * 6.28, vr: (r() - 0.5) * 1.6, s: 7 + r() * 9, c: cols[i % cols.length], ph: r() * 6.28, sw: 18 + r() * 30 });
  }
  if (kind === "halloween") {
    for (let i = 0, c = n(6, 3); i < c; i++) parts.push({ t: "bat", x: r() * W, y: H * (0.08 + r() * 0.5), vx: (r() > 0.5 ? 1 : -1) * (16 + r() * 22), s: 9 + r() * 10, ph: r() * 6.28 });
    if (!low) for (let i = 0; i < 3; i++) parts.push({ t: "fog", x: W * (i / 3), y: H * (0.8 + r() * 0.15), rx: W * (0.35 + r() * 0.2), vx: 6 + r() * 6, ph: r() * 6.28 });
  }
}

function drawLeaf(p) {
  ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.scale(p.s / 10, p.s / 10);
  ctx.globalAlpha = 0.8;
  ctx.fillStyle = p.c;
  ctx.beginPath();
  ctx.moveTo(0, -10); ctx.bezierCurveTo(3, -7, 7, -6, 8, -2); ctx.bezierCurveTo(6, -1, 6, 1, 8, 2);
  ctx.bezierCurveTo(5, 3, 3, 5, 1, 9); ctx.lineTo(0, 12); ctx.lineTo(-1, 9);
  ctx.bezierCurveTo(-3, 5, -5, 3, -8, 2); ctx.bezierCurveTo(-6, 1, -6, -1, -8, -2); ctx.bezierCurveTo(-7, -6, -3, -7, 0, -10);
  ctx.fill();
  ctx.strokeStyle = "rgba(60,20,4,.55)"; ctx.lineWidth = 0.9;
  ctx.beginPath(); ctx.moveTo(0, -7); ctx.lineTo(0, 12); ctx.stroke();
  ctx.restore();
}

function drawBat(p, t) {
  const flap = Math.sin(t * 9 + p.ph);
  const s = p.s;
  ctx.save(); ctx.translate(p.x, p.y + Math.sin(t * 1.3 + p.ph) * 6); ctx.scale(p.vx < 0 ? -1 : 1, 1);
  ctx.fillStyle = "#1b0d2e"; ctx.strokeStyle = "rgba(249,115,22,.45)"; ctx.lineWidth = 0.8;
  const wy = -s * 0.5 * flap;
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.quadraticCurveTo(-s * 0.5, wy - s * 0.3, -s * 1.3, wy);
  ctx.quadraticCurveTo(-s * 1.0, wy * 0.4 + s * 0.15, -s * 0.85, s * 0.25);
  ctx.quadraticCurveTo(-s * 0.5, s * 0.05, -s * 0.35, s * 0.35);
  ctx.quadraticCurveTo(-s * 0.2, s * 0.15, 0, s * 0.3);
  ctx.quadraticCurveTo(s * 0.2, s * 0.15, s * 0.35, s * 0.35);
  ctx.quadraticCurveTo(s * 0.5, s * 0.05, s * 0.85, s * 0.25);
  ctx.quadraticCurveTo(s * 1.0, wy * 0.4 + s * 0.15, s * 1.3, wy);
  ctx.quadraticCurveTo(s * 0.5, wy - s * 0.3, 0, 0);
  ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(0, s * 0.12, s * 0.2, s * 0.28, 0, 0, 6.29); ctx.fill();
  ctx.restore();
}

function frame(now, dt) {
  if (!ctx) return;
  const t = now / 1000;
  const step = Math.min(dt || 0, 80) / 1000;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  for (const p of parts) {
    switch (p.t) {
      case "snow": {
        p.y += p.vy * step; p.x += Math.sin(t * 0.8 + p.ph) * 12 * step;
        if (p.y > H + 4) { p.y = -4; p.x = Math.random() * W; }
        ctx.globalAlpha = p.a; ctx.fillStyle = "#f8fafc";
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.29); ctx.fill();
        break;
      }
      case "conf": {
        p.y += p.vy * step; p.rot += p.vr * step; p.x += Math.sin(t + p.ph) * 20 * step;
        if (p.y > H + 6) { p.y = -6; p.x = Math.random() * W; }
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.globalAlpha = 0.85; ctx.fillStyle = p.c;
        ctx.fillRect(-p.w / 2, -p.h / 2 * Math.abs(Math.cos(t * 3 + p.ph)) - 0.5, p.w, p.h * Math.abs(Math.cos(t * 3 + p.ph)) + 1);
        ctx.restore();
        break;
      }
      case "leaf": {
        p.y += p.vy * step; p.rot += p.vr * step; p.x += Math.sin(t * 0.9 + p.ph) * p.sw * step;
        if (p.y > H + 16) { p.y = -16; p.x = Math.random() * W; }
        drawLeaf(p);
        break;
      }
      case "bat": {
        p.x += p.vx * step;
        if (p.x > W + 40) p.x = -40; if (p.x < -40) p.x = W + 40;
        ctx.globalAlpha = 0.9; drawBat(p, t);
        break;
      }
      case "fog": {
        p.x += p.vx * step; if (p.x - p.rx > W) p.x = -p.rx;
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.rx);
        g.addColorStop(0, "rgba(167,139,250,0.10)"); g.addColorStop(0.5, "rgba(148,130,190,0.05)"); g.addColorStop(1, "rgba(148,130,190,0)");
        ctx.globalAlpha = 1; ctx.fillStyle = g;
        ctx.save(); ctx.translate(p.x, p.y); ctx.scale(1, 0.32); ctx.translate(-p.x, -p.y);
        ctx.fillRect(p.x - p.rx, p.y - p.rx, p.rx * 2, p.rx * 2); ctx.restore();
        break;
      }
      case "bulb": {
        // two gentle swags of lights along the very top edge
        const u = p.i / p.n, x = u * W;
        const local = (u * 3) % 1;
        const y = 3 + 14 * (1 - (2 * local - 1) ** 2);
        if (p.i === 0) { // the wire, drawn once
          ctx.globalAlpha = 0.45; ctx.strokeStyle = "#1e293b"; ctx.lineWidth = 1.2; ctx.beginPath();
          for (let k = 0; k <= 90; k++) { const uu = k / 90, ll = (uu * 3) % 1; const yy = 3 + 14 * (1 - (2 * ll - 1) ** 2); k ? ctx.lineTo(uu * W, yy) : ctx.moveTo(0, yy); }
          ctx.stroke();
        }
        const tw = now ? 0.55 + 0.45 * Math.sin(t * p.sp + p.ph) : 0.9;
        const g = ctx.createRadialGradient(x, y + 4, 0, x, y + 4, 12);
        g.addColorStop(0, p.c); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.globalAlpha = 0.5 * tw; ctx.fillStyle = g; ctx.fillRect(x - 12, y - 8, 24, 24);
        ctx.globalAlpha = 0.6 + 0.4 * tw; ctx.fillStyle = p.c;
        ctx.beginPath(); ctx.ellipse(x, y + 4, 2.6, 3.6, 0, 0, 6.29); ctx.fill();
        break;
      }
      default: break;
    }
  }
  ctx.globalAlpha = 1;
}

function sync() {
  const next = currentKind();
  unsub?.(); unsub = null;
  if (!next || !ensureCanvas()) { kind = ""; if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height); return; }
  resize();
  kind = next;
  seed();
  frame(0, 0); // static frame — complete when motion is off
  if (Motion.level !== "off") unsub = Motion.onFrame(frame, { fps: Motion.level === "full" ? 40 : 24 });
}

let installed = false;
export function install(api) {
  api.accessory = accessory;
  if (installed) return;
  installed = true;
  Motion.subscribe(() => sync());
  new MutationObserver(sync).observe(document.documentElement, { attributes: true, attributeFilter: ["data-season", "data-season-variant", "data-mode"] });
  let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(sync, 200); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", sync, { once: true });
}

export { accessory };
