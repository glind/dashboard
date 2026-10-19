/*!
 * Buster Design System — background.js
 * <buster-space density="1"> — canvas starfield layered over the pure-CSS nebula + planet
 * (see background.css). Twinkles gently at ~12 fps in full motion; static otherwise.
 * Operations mode: fewer, dimmer stars, never animated.
 */
import { Motion } from "./motion.js";

const DPR_CAP = 1.5;

class BusterSpace extends HTMLElement {
  connectedCallback() {
    if (this._canvas) return;
    this.setAttribute("aria-hidden", "true");
    this._canvas = document.createElement("canvas");
    this.appendChild(this._canvas);
    this._ctx = this._canvas.getContext("2d");
    this._stars = [];
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(this);
    this._unsubMotion = Motion.subscribe(() => this._sync());
    this._resize();
  }

  disconnectedCallback() {
    this._ro?.disconnect();
    this._unsubMotion?.();
    this._stopTwinkle();
    this._canvas?.remove();
    this._canvas = null;
  }

  get _ops() {
    const r = document.documentElement.dataset.mode || document.body?.dataset.mode;
    return r === "operations";
  }

  _resize() {
    const w = this.clientWidth || window.innerWidth;
    const h = this.clientHeight || window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, DPR_CAP);
    this._w = w; this._h = h; this._dpr = dpr;
    this._canvas.width = Math.round(w * dpr);
    this._canvas.height = Math.round(h * dpr);
    this._seed();
    this._draw(0);
  }

  _seed() {
    const density = Number(this.getAttribute("density")) || 1;
    const count = Math.round(((this._w * this._h) / 2600) * density);
    let s = 1337;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    const tints = ["255,255,255", "205,225,255", "225,210,255", "190,240,255"];
    this._stars = Array.from({ length: count }, (_, i) => {
      const big = rnd() > 0.965;
      return {
        x: rnd() * this._w,
        y: rnd() * this._h,
        r: big ? 1.1 + rnd() * 0.9 : 0.35 + rnd() * 0.75,
        a: big ? 0.7 + rnd() * 0.3 : 0.25 + rnd() * 0.55,
        tint: tints[(rnd() * tints.length) | 0],
        tw: rnd() > 0.82 ? 0.6 + rnd() * 1.8 : 0, // twinkle speed (0 = steady)
        ph: rnd() * Math.PI * 2,
        big,
        keep: i % 2 === 0, // subset kept in operations mode
      };
    });
  }

  _draw(t) {
    const ctx = this._ctx;
    if (!ctx) return;
    const ops = this._ops;
    const animate = t > 0;
    ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
    ctx.clearRect(0, 0, this._w, this._h);
    for (const st of this._stars) {
      if (ops && !st.keep) continue;
      let a = st.a * (ops ? 0.6 : 1);
      if (animate && st.tw) a *= 0.55 + 0.45 * Math.sin(st.ph + (t / 1000) * st.tw);
      if (st.big && !ops) {
        const g = ctx.createRadialGradient(st.x, st.y, 0, st.x, st.y, st.r * 4);
        g.addColorStop(0, `rgba(${st.tint},${a})`);
        g.addColorStop(0.3, `rgba(${st.tint},${a * 0.35})`);
        g.addColorStop(1, `rgba(${st.tint},0)`);
        ctx.fillStyle = g;
        ctx.fillRect(st.x - st.r * 4, st.y - st.r * 4, st.r * 8, st.r * 8);
      }
      ctx.fillStyle = `rgba(${st.tint},${a})`;
      ctx.beginPath();
      ctx.arc(st.x, st.y, st.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  _sync() {
    const twinkle = Motion.level === "full" && !this._ops;
    if (twinkle) this._startTwinkle();
    else { this._stopTwinkle(); this._draw(0); }
  }

  _startTwinkle() {
    if (this._unsubFrame) return;
    this._unsubFrame = Motion.onFrame((now) => this._draw(now), { fps: 12 });
  }

  _stopTwinkle() {
    this._unsubFrame?.();
    this._unsubFrame = null;
  }
}

if (!customElements.get("buster-space")) customElements.define("buster-space", BusterSpace);

// Re-render when mode flips (stars thin out in operations mode).
const modeObserver = new MutationObserver(() => {
  document.querySelectorAll("buster-space").forEach((el) => el._sync?.());
});
const watchMode = (el) => modeObserver.observe(el, { attributes: true, attributeFilter: ["data-mode"] });
watchMode(document.documentElement);
if (document.body) watchMode(document.body);
else document.addEventListener("DOMContentLoaded", () => watchMode(document.body), { once: true });

export { BusterSpace };
