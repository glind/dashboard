/*!
 * Buster Design System — waveform.js
 * <buster-waveform bars="28" active level="0.4" accent="cyan">
 *   Voice "listening" waveform. Drive with:
 *     el.level = 0..1                       (e.g. from your own VAD / server events)
 *     el.attachStream(mediaStream)          (mic; creates an AnalyserNode)
 *     el.attachAnalyser(analyserNode)
 *   With no level source and `active`, it breathes gently. Static (but complete) when motion is off.
 *
 * Also exports createLevelMeter(source, onLevel) used by <buster-companion>.
 */
import { Motion, bindMotion } from "./motion.js";

/** RMS level meter on an AnalyserNode or MediaStream. Calls onLevel(0..1) ~30×/s. */
export function createLevelMeter(source, onLevel) {
  let ctx = null;
  let analyser = source;
  if (typeof MediaStream !== "undefined" && source instanceof MediaStream) {
    const AC = window.AudioContext || window.webkitAudioContext;
    ctx = new AC();
    const src = ctx.createMediaStreamSource(source);
    analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    src.connect(analyser);
  }
  const buf = new Uint8Array(analyser.fftSize);
  let smooth = 0;
  const unsub = Motion.onFrame(() => {
    analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
    const lvl = Math.min(1, Math.sqrt(sum / buf.length) * 4.5);
    smooth = smooth * 0.65 + lvl * 0.35;
    onLevel(smooth);
  }, { fps: 30 });
  return { analyser, stop() { unsub(); ctx?.close?.(); } };
}

const ACCENT_STOPS = {
  cyan: ["#22d3ee", "#8b5cf6", "#e879f9"],
  violet: ["#a78bfa", "#8b5cf6", "#e879f9"],
  green: ["#34d399", "#22d3ee", "#38bdf8"],
  amber: ["#fbbf24", "#fb923c", "#f472b6"],
  blue: ["#60a5fa", "#6366f1", "#a78bfa"],
};

function mix(a, b, t) {
  const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16);
  const ch = (s) => Math.round(((pa >> s) & 255) * (1 - t) + ((pb >> s) & 255) * t);
  return `rgb(${ch(16)},${ch(8)},${ch(0)})`;
}

const tpl = document.createElement("template");
tpl.innerHTML = `<style>
:host { display: inline-flex; align-items: center; justify-content: center; gap: var(--wf-gap, 3px); height: var(--wf-height, 28px); min-width: 60px; contain: layout paint; }
.b { width: var(--wf-bar, 3px); height: 100%; border-radius: 3px; transform-origin: 50% 50%; transform: scaleY(.18); transition: transform 90ms linear; box-shadow: 0 0 calc(8px * var(--glow-strength, 1)) currentColor; background: currentColor; }
:host([motion="off"]) .b { transition: none; }
</style>`;

class BusterWaveform extends HTMLElement {
  static get observedAttributes() { return ["bars", "level", "accent", "active"]; }

  constructor() {
    super();
    this.attachShadow({ mode: "open" }).appendChild(tpl.content.cloneNode(true));
    this._level = null;
    this._lastExternal = 0;
    this._bars = [];
  }

  connectedCallback() {
    this.setAttribute("role", "img");
    if (!this.hasAttribute("aria-label")) this.setAttribute("aria-label", "Voice level");
    this._build();
    this._unsubMotion = bindMotion(this);
  }

  disconnectedCallback() {
    this._unsubMotion?.();
    this._stopLoop();
    this._meter?.stop();
  }

  attributeChangedCallback(n, _o, v) {
    if (n === "level") { this.level = Number(v); return; }
    if (this.isConnected && (n === "bars" || n === "accent")) this._build();
    if (n === "active" && this.isConnected) this.onMotion({ level: Motion.level });
  }

  get level() { return this._level ?? 0; }
  set level(v) {
    this._level = Math.max(0, Math.min(1, Number(v) || 0));
    this._lastExternal = performance.now();
    if (Motion.level === "off") this._render(0);
  }

  attachStream(stream) { this._meter?.stop(); this._meter = createLevelMeter(stream, (l) => { this.level = l; }); return this._meter; }
  attachAnalyser(an) { return this.attachStream(an); }
  detachAudio() { this._meter?.stop(); this._meter = null; }

  _build() {
    const n = Math.max(6, Math.min(64, Number(this.getAttribute("bars")) || 28));
    const stops = ACCENT_STOPS[this.getAttribute("accent")] || ACCENT_STOPS.cyan;
    this.shadowRoot.querySelectorAll(".b").forEach((b) => b.remove());
    this._bars = Array.from({ length: n }, (_, i) => {
      const t = i / (n - 1);
      const b = document.createElement("i");
      b.className = "b";
      b.style.color = t < 0.5 ? mix(stops[0], stops[1], t * 2) : mix(stops[1], stops[2], (t - 0.5) * 2);
      this.shadowRoot.appendChild(b);
      return b;
    });
    this._render(0);
  }

  onMotion({ level }) {
    const animate = level !== "off" && this.hasAttribute("active");
    if (animate) this._startLoop(level === "low" ? 20 : 45);
    else { this._stopLoop(); this._render(0); }
  }

  _startLoop(fps) {
    this._stopLoop();
    this._unsubFrame = Motion.onFrame((now) => this._render(now), { fps });
  }
  _stopLoop() { this._unsubFrame?.(); this._unsubFrame = null; }

  _render(now) {
    const n = this._bars.length;
    if (!n) return;
    const t = now / 1000;
    const external = this._level !== null && performance.now() - this._lastExternal < 1500;
    const lvl = external ? this._level : this.hasAttribute("active") && now ? 0.32 + 0.12 * Math.sin(t * 1.7) : 0.42;
    for (let i = 0; i < n; i++) {
      const x = i / (n - 1);
      const env = Math.pow(Math.sin(Math.PI * x), 0.9);                       // taper at the ends
      const wave = now
        ? 0.55 + 0.45 * Math.sin(t * 6.5 + i * 0.55) * Math.sin(t * 2.3 + i * 0.21)
        : 0.6 + 0.4 * Math.sin(i * 0.9) * Math.cos(i * 0.37);                  // static pleasing shape
      const h = Math.max(0.14, Math.min(1, env * (0.2 + lvl * 1.25) * wave + 0.08));
      this._bars[i].style.transform = `scaleY(${h.toFixed(3)})`;
    }
  }
}

if (!customElements.get("buster-waveform")) customElements.define("buster-waveform", BusterWaveform);
export { BusterWaveform };
