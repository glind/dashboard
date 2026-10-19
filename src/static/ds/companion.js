/*!
 * Buster Design System — companion.js
 *
 * <buster-companion state="idle|listening|thinking|discovering|success|needs-help|error"
 *                   size="lg|md|sm|xs" accent="cyan|blue|violet|green|amber|magenta|pink|coral"
 *                   name="Buster" message="Hey! 👋" bubble="right|left|top" ground="none" hold>
 *
 *   el.state = "thinking"            // attribute or property
 *   el.say("Done!", { duration })    // speech bubble (duration ms, 0 = stay)
 *   el.celebrate()                   // success: 350ms pulse + sparkle, then back to idle
 *   el.react("wow"|"blink"|"nod"|"look"|"success"|"concern", opts)
 *   el.level = 0..1                  // listening: audio-reactive glow
 *   el.attachStream(mediaStream) / el.attachAnalyser(node) / el.detachAudio()
 *   events: "buster-statechange" { state, previous }
 *
 * <buster-agent name="Monitor" status="working|communicating|waiting-approval|done|idle"
 *               accent="green" progress="0..100">optional status text</buster-agent>
 *
 * Motion spec (all gated by motion.js — static but complete when motion is off):
 *   idle 4.2s float + random blink + eyes follow pointer · listening glow+waves from level ·
 *   thinking orbiting particles 2.2s + focused eyes · discovering wow + sparkle (brief) ·
 *   success 350ms pulse + sparkle → idle · needs-help/error soft amber/rose pulse, worried eyes, no shake.
 */
import { Motion, bindMotion } from "./motion.js";
import { createLevelMeter } from "./waveform.js";

export const STATES = ["idle", "listening", "thinking", "discovering", "success", "needs-help", "error"];
const EXPRESSION = { idle: "happy", listening: "open", thinking: "focused", discovering: "wow", success: "happy", "needs-help": "worried", error: "worried" };
const MOUTH = { idle: "smile", listening: "soft", thinking: "flat", discovering: "o", success: "smile", "needs-help": "wavy", error: "wavy" };
const LABEL = { idle: "idle", listening: "listening", thinking: "thinking", discovering: "found something", success: "task completed", "needs-help": "needs your help", error: "ran into a problem" };
const TRANSIENT = { success: 1250, discovering: 1800 };

export const ACCENTS = {
  cyan:    { acc: "#22d3ee", eye: "#7cf0ff", finA: "#38bdf8", finB: "#8b5cf6", rimA: "#67e8f9", rimB: "#a78bfa" },
  blue:    { acc: "#60a5fa", eye: "#9cc8ff", finA: "#60a5fa", finB: "#4f46e5", rimA: "#93c5fd", rimB: "#818cf8" },
  violet:  { acc: "#a78bfa", eye: "#cbbcff", finA: "#a78bfa", finB: "#7c3aed", rimA: "#c4b5fd", rimB: "#e879f9" },
  green:   { acc: "#34d399", eye: "#7bf0c4", finA: "#34d399", finB: "#0891b2", rimA: "#6ee7b7", rimB: "#22d3ee" },
  amber:   { acc: "#fbbf24", eye: "#fcd56b", finA: "#fbbf24", finB: "#f97316", rimA: "#fde68a", rimB: "#fb923c" },
  magenta: { acc: "#e879f9", eye: "#f3c4fd", finA: "#e879f9", finB: "#9333ea", rimA: "#f5d0fe", rimB: "#a78bfa" },
  pink:    { acc: "#f472b6", eye: "#fbc4e1", finA: "#f472b6", finB: "#a855f7", rimA: "#fbcfe8", rimB: "#c084fc" },
  coral:   { acc: "#ff7f6e", eye: "#ffc2b8", finA: "#fb923c", finB: "#f43f5e", rimA: "#fecaca", rimB: "#fb7185" },
};

let uid = 0;

/* ---------------- shared pointer tracking (eyes follow) ---------------- */
const pointer = { x: 0, y: 0, t: 0 };
const lookers = new Set();
let lookRaf = 0;
window.addEventListener("pointermove", (e) => {
  pointer.x = e.clientX; pointer.y = e.clientY; pointer.t = performance.now();
  if (!lookRaf && lookers.size && Motion.active) {
    lookRaf = requestAnimationFrame(() => { lookRaf = 0; lookers.forEach((c) => c._followPointer()); });
  }
}, { passive: true });

/* ---------------- seasonal accessories (shared observer) ---------------- */
const companions = new Set();
const refreshSeason = () => companions.forEach((c) => c._applySeason());
new MutationObserver(refreshSeason).observe(document.documentElement, { attributes: true, attributeFilter: ["data-season", "data-season-variant", "data-mode"] });
document.addEventListener("buster:season-fx", refreshSeason);
document.addEventListener("buster:mode", refreshSeason);

/* ---------------- template ---------------- */
function svgMarkup(p) {
  const finL = "M68 96 C54 86 40 68 30 42 C47 50 63 59 78 70 Z";
  const finR = "M172 96 C186 86 200 68 210 42 C193 50 177 59 162 70 Z";
  const spark = (x, y, s, d) => `<use class="sp" href="#${p}spark" x="${x - s / 2}" y="${y - s / 2}" width="${s}" height="${s}" style="--d:${d}ms"/>`;
  return `
<svg class="svg" part="svg" viewBox="0 0 240 240" aria-hidden="true" focusable="false">
  <defs>
    <radialGradient id="${p}head" cx="36%" cy="24%" r="85%">
      <stop offset="0" stop-color="#3d4ea6"/><stop offset=".34" stop-color="#1b2466"/><stop offset=".72" stop-color="#0d1340"/><stop offset="1" stop-color="#070b26"/>
    </radialGradient>
    <linearGradient id="${p}rim" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" class="rim-a"/><stop offset=".45" stop-color="#6366f1" stop-opacity=".12"/><stop offset=".7" stop-color="#6366f1" stop-opacity=".1"/><stop offset="1" class="rim-b"/>
    </linearGradient>
    <linearGradient id="${p}fin" x1="0" y1="1" x2=".35" y2="0">
      <stop offset="0" class="fin-a"/><stop offset="1" class="fin-b"/>
    </linearGradient>
    <linearGradient id="${p}visor" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0c1236"/><stop offset=".55" stop-color="#03050f"/><stop offset="1" stop-color="#05081a"/>
    </linearGradient>
    <radialGradient id="${p}disc" cx="50%" cy="50%" r="50%">
      <stop offset="0" class="ring-c" stop-opacity=".55"/><stop offset=".55" class="ring-c" stop-opacity=".16"/><stop offset="1" class="ring-c" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="${p}beam" x1="0" y1="1" x2="0" y2="0">
      <stop offset="0" class="ring-c" stop-opacity=".26"/><stop offset="1" class="ring-c" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="${p}ring" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" class="ring-c"/><stop offset=".5" stop-color="#8b5cf6"/><stop offset="1" class="ring-c"/>
    </linearGradient>
    <filter id="${p}glow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="${p}soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
    <filter id="${p}blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.8"/></filter>
    <symbol id="${p}spark" viewBox="-10 -10 20 20"><path d="M0-10C1-3 3-1 10 0 3 1 1 3 0 10-1 3-3 1-10 0-3-1-1-3 0-10Z"/></symbol>
  </defs>

  <g class="ground">
    <ellipse class="disc-halo" cx="120" cy="207" rx="108" ry="26" fill="url(#${p}disc)"/>
    <path class="beam" d="M58 205 L90 128 L150 128 L182 205 Z" fill="url(#${p}beam)"/>
    <ellipse cx="120" cy="205" rx="76" ry="14.5" fill="rgba(34,211,238,.07)"/>
    <ellipse class="disc-ring3" cx="120" cy="207" rx="96" ry="20" fill="none" stroke="url(#${p}ring)" stroke-width="1" stroke-dasharray="2 6" opacity=".55"/>
    <ellipse class="disc-ring" cx="120" cy="205" rx="76" ry="14.5" fill="none" stroke="url(#${p}ring)" stroke-width="2.4" filter="url(#${p}glow)"/>
    <ellipse class="disc-ring2" cx="120" cy="205" rx="50" ry="8.5" fill="none" stroke="#a78bfa" stroke-opacity=".7" stroke-width="1.3"/>
    <ellipse class="disc-shadow" cx="120" cy="203" rx="30" ry="4.5" fill="#01020a" opacity=".55" filter="url(#${p}blur)"/>
  </g>

  <g class="orbit orbit-back"></g>

  <g class="bot">
    <g class="bot-inner">
      <ellipse class="aura" cx="120" cy="104" rx="80" ry="66" filter="url(#${p}soft)"/>
      <g class="waves" fill="none" stroke-linecap="round">
        <path d="M44 88 Q34 104 44 120"/><path d="M33 80 Q19 104 33 128"/>
        <path d="M196 88 Q206 104 196 120"/><path d="M207 80 Q221 104 207 128"/>
      </g>
      <g class="body">
        <rect x="108" y="146" width="24" height="12" rx="5" fill="#0a0f2f"/>
        <path d="M90 174 C90 161 101 155 120 155 C139 155 150 161 150 174 C150 186 139 193 120 193 C101 193 90 186 90 174Z" fill="url(#${p}head)" stroke="url(#${p}rim)" stroke-width="1.4"/>
        <rect class="chest" x="110" y="168" width="20" height="6" rx="3" filter="url(#${p}glow)"/>
      </g>
      <g class="fins">
        <path class="fin-glow" d="${finL}" filter="url(#${p}soft)"/><path class="fin-glow" d="${finR}" filter="url(#${p}soft)"/>
        <path d="${finL}" fill="url(#${p}fin)"/><path d="${finR}" fill="url(#${p}fin)"/>
        <path class="fin-edge" d="M30 42 C47 50 63 59 78 70"/><path class="fin-edge" d="M210 42 C193 50 177 59 162 70"/>
      </g>
      <rect class="head" x="58" y="48" width="124" height="104" rx="48" fill="url(#${p}head)"/>
      <rect x="58" y="48" width="124" height="104" rx="48" fill="none" stroke="url(#${p}rim)" stroke-width="2.2"/>
      <rect class="pod" x="51" y="86" width="11" height="34" rx="5.5" fill="url(#${p}fin)"/>
      <rect class="pod" x="178" y="86" width="11" height="34" rx="5.5" fill="url(#${p}fin)"/>
      <ellipse class="gloss" cx="98" cy="61" rx="27" ry="7" transform="rotate(-13 98 61)" fill="#fff" opacity=".2" filter="url(#${p}blur)"/>
      <circle class="gloss" cx="77" cy="71" r="2.4" fill="#fff" opacity=".55"/>
      <rect class="visor" x="70" y="72" width="100" height="64" rx="30" fill="url(#${p}visor)"/>
      <path class="sheen" d="M86 79 C104 75 134 75 152 80" fill="none" stroke="#fff" stroke-opacity=".13" stroke-width="2" stroke-linecap="round"/>
      <g class="face">
        <g class="cheeks" filter="url(#${p}blur)"><ellipse cx="88" cy="121" rx="8" ry="4.2"/><ellipse cx="152" cy="121" rx="8" ry="4.2"/></g>
        <g class="eyes" filter="url(#${p}glow)">
          <g class="ex ex-happy"><path d="M89 108 Q100 92 111 108"/><path d="M129 108 Q140 92 151 108"/></g>
          <g class="ex ex-open"><ellipse cx="100" cy="103" rx="7.5" ry="9.5"/><ellipse cx="140" cy="103" rx="7.5" ry="9.5"/><circle class="hl" cx="102.5" cy="99.5" r="2.4"/><circle class="hl" cx="142.5" cy="99.5" r="2.4"/></g>
          <g class="ex ex-wow"><ellipse cx="100" cy="102" rx="9.5" ry="11.5"/><ellipse cx="140" cy="102" rx="9.5" ry="11.5"/><circle class="hl" cx="103.5" cy="97.5" r="3.2"/><circle class="hl" cx="143.5" cy="97.5" r="3.2"/><circle class="hl" cx="97" cy="106" r="1.4"/><circle class="hl" cx="137" cy="106" r="1.4"/></g>
          <g class="ex ex-focused"><ellipse cx="100" cy="104" rx="8.5" ry="5.6"/><ellipse cx="140" cy="104" rx="8.5" ry="5.6"/><circle class="hl" cx="103" cy="102.4" r="1.7"/><circle class="hl" cx="143" cy="102.4" r="1.7"/></g>
          <g class="ex ex-worried"><ellipse cx="100" cy="106" rx="6.5" ry="7.5"/><ellipse cx="140" cy="106" rx="6.5" ry="7.5"/><circle class="hl" cx="102" cy="103.5" r="1.8"/><circle class="hl" cx="142" cy="103.5" r="1.8"/><path class="brow" d="M88 96 L108 91"/><path class="brow" d="M132 91 L152 96"/></g>
        </g>
        <g class="mouths" filter="url(#${p}glow)">
          <path class="m m-smile" d="M111 121 Q120 129.5 129 121"/>
          <path class="m m-soft" d="M113 123 Q120 127 127 123"/>
          <ellipse class="m m-o" cx="120" cy="124.5" rx="4" ry="4.8"/>
          <path class="m m-flat" d="M114 124 Q120 125.5 126 124"/>
          <path class="m m-wavy" d="M110 125 q5 -4 10 0 q5 4 10 0"/>
        </g>
      </g>
      <g class="acc"></g>
    </g>
  </g>

  <g class="orbit orbit-front"></g>
  <g class="sparkles">
    ${spark(46, 58, 16, 0)}${spark(196, 50, 20, 90)}${spark(208, 128, 12, 180)}${spark(34, 138, 13, 140)}${spark(150, 24, 11, 220)}${spark(78, 22, 9, 300)}
  </g>
</svg>`;
}

const STYLE = `
:host {
  --bc-size: 280px;
  display: inline-block; position: relative; width: var(--bc-size); aspect-ratio: 1 / 1;
  vertical-align: middle; -webkit-tap-highlight-color: transparent;
  --level: 0; --lx: 0; --ly: 0;
  --bc-aura: var(--bc-acc); --bc-aura-o: .32; --bc-ring: var(--bc-acc);
}
:host([size="md"]) { --bc-size: 168px; }
:host([size="sm"]) { --bc-size: 76px; }
:host([size="xs"]) { --bc-size: 40px; }
.svg { width: 100%; height: 100%; display: block; overflow: visible; --eye: var(--bc-eye-s, var(--bc-eye-season, var(--bc-eye))); }

.rim-a { stop-color: var(--bc-rim-a); } .rim-b { stop-color: var(--bc-rim-b); }
.fin-a { stop-color: var(--bc-fin-a); } .fin-b { stop-color: var(--bc-fin-b); }
.ring-c { stop-color: var(--bc-ring); }

.aura { fill: var(--bc-aura); opacity: calc(var(--bc-aura-o) * var(--glow-strength, 1) + .06); transition: opacity .4s, fill .4s; transform-box: fill-box; transform-origin: center; }
.fin-glow { fill: var(--bc-fin-a); opacity: calc(.55 * var(--glow-strength, 1)); }
.fin-edge { fill: none; stroke: var(--bc-rim-a); stroke-width: 1.3; stroke-linecap: round; opacity: .9; }
.visor { stroke: var(--bc-acc); stroke-opacity: .22; stroke-width: 1.2; }
.cheeks ellipse { fill: #f472b6; opacity: .38; transition: opacity .3s; }
.chest { fill: var(--eye); opacity: calc(.55 + var(--level) * .45); }
.waves path { stroke: var(--eye); stroke-width: 2.4; opacity: 0; transition: opacity .25s; }

.ex { opacity: 0; transition: opacity .16s ease; }
.ex path { fill: none; stroke: var(--eye); stroke-width: 5.6; stroke-linecap: round; stroke-linejoin: round; }
.ex ellipse, .ex .fill { fill: var(--eye); stroke: none; }
.ex .hl { fill: #fff; opacity: .9; }
.ex .brow { stroke-width: 3.4; opacity: .9; }
.m { fill: none; stroke: var(--eye); stroke-width: 3.2; stroke-linecap: round; opacity: 0; transition: opacity .16s ease; }
ellipse.m { fill: var(--eye); stroke: none; }
:host([data-expr="happy"]) .ex-happy, :host([data-expr="open"]) .ex-open, :host([data-expr="wow"]) .ex-wow,
:host([data-expr="focused"]) .ex-focused, :host([data-expr="worried"]) .ex-worried,
:host([data-mouth="smile"]) .m-smile, :host([data-mouth="soft"]) .m-soft, :host([data-mouth="o"]) .m-o,
:host([data-mouth="flat"]) .m-flat, :host([data-mouth="wavy"]) .m-wavy { opacity: 1; }

.face { transform: translate(calc(var(--lx) * 1px), calc(var(--ly) * 1px)); transition: transform .45s cubic-bezier(.2,.8,.2,1); }
.eyes { transform-box: fill-box; transform-origin: 50% 50%; transition: transform 70ms ease-in; }
:host([blink]) .eyes { transform: scaleY(.08); }

.sp { fill: #fff; opacity: 0; transform-box: fill-box; transform-origin: center; filter: drop-shadow(0 0 3px var(--eye)); }
.sp:nth-child(2n) { fill: var(--eye); }
.sp:nth-child(3n) { fill: #f5d0fe; }

.orbit circle { fill: var(--eye); }
.orbit .trail { fill: none; stroke: var(--eye); stroke-opacity: .16; stroke-width: 1; }

/* ---- state colour/intensity ---- */
:host([state="listening"]) { --bc-aura-o: calc(.3 + var(--level) * .55); }
:host([state="listening"]) .waves path { opacity: calc(.18 + var(--level) * .9); }
:host([state="listening"]) .waves path:nth-child(2n) { opacity: calc(var(--level) * .7); }
:host([state="thinking"]) { --bc-aura: #8b5cf6; --bc-aura-o: .4; }
:host([state="discovering"]) { --bc-aura: #e879f9; --bc-aura-o: .48; }
:host([state="success"]) { --bc-aura: #34d399; --bc-aura-o: .5; --bc-ring: #34d399; }
:host([state="needs-help"]) { --bc-aura: #fbbf24; --bc-aura-o: .42; --bc-ring: #fbbf24; }
:host([state="error"]) { --bc-aura: #fb7185; --bc-aura-o: .42; --bc-ring: #fb7185; --bc-eye-s: #ffb4bd; }
:host([state="needs-help"]) .cheeks ellipse, :host([state="error"]) .cheeks ellipse { opacity: .12; }
:host([state="discovering"]) .cheeks ellipse, :host([state="success"]) .cheeks ellipse { opacity: .6; }
:host([state="listening"]) .disc-ring { transform: scale(calc(1 + var(--level) * .07)); }
.disc-ring, .disc-ring2, .disc-ring3 { transform-box: fill-box; transform-origin: center; transition: transform .12s linear; }

/* ---- compact sizes: head only ---- */
:host([size="sm"]) .ground, :host([size="xs"]) .ground, :host([ground="none"]) .ground,
:host([size="sm"]) .body, :host([size="xs"]) .body { display: none; }
:host([size="xs"]) .sheen, :host([size="xs"]) .waves, :host([size="xs"]) .sparkles { display: none; }
:host([size="xs"]) .ex path { stroke-width: 7; }
:host([size="xs"]) .m { stroke-width: 4.2; }

/* ---- motion (only when motion != off) ---- */
@keyframes bc-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }
@keyframes bc-float-sm { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
@keyframes bc-shadow { 0%, 100% { transform: scale(1); opacity: .55; } 50% { transform: scale(.82); opacity: .32; } }
@keyframes bc-breathe { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.04); } }
@keyframes bc-softpulse { 0%, 100% { opacity: calc(.16 + .1 * var(--glow-strength, 1)); transform: scale(.98); } 50% { opacity: calc(.4 + .3 * var(--glow-strength, 1)); transform: scale(1.05); } }
@keyframes bc-pulse { 0% { transform: scale(1); } 45% { transform: scale(1.075); } 100% { transform: scale(1); } }
@keyframes bc-flash { 0% { stroke-width: 2.4; opacity: 1; } 40% { stroke-width: 5; opacity: 1; } 100% { stroke-width: 2.4; opacity: 1; } }
@keyframes bc-sparkle { 0% { opacity: 0; transform: scale(0) rotate(0deg); } 35% { opacity: 1; transform: scale(1.1) rotate(30deg); } 100% { opacity: 0; transform: scale(.3) rotate(80deg); } }
@keyframes bc-spin { to { stroke-dashoffset: -64; } }
@keyframes bc-nod { 0%, 100% { transform: rotate(0); } 35% { transform: rotate(-5deg); } 70% { transform: rotate(3deg); } }

.bot { transform-box: view-box; transform-origin: 120px 110px; }
.bot-inner { transform-box: view-box; transform-origin: 120px 112px; }
.disc-shadow { transform-box: fill-box; transform-origin: center; }

:host(:not([motion="off"])) .bot { animation: bc-float var(--cycle-float, 4.2s) cubic-bezier(.45,0,.55,1) infinite; }
:host([size="sm"]:not([motion="off"])) .bot { animation-name: bc-float-sm; }
:host([size="xs"]) .bot { animation: none; }
:host(:not([motion="off"])) .disc-shadow { animation: bc-shadow var(--cycle-float, 4.2s) cubic-bezier(.45,0,.55,1) infinite; }
:host([motion="full"]) .disc-ring3 { animation: bc-spin 6s linear infinite; }
:host([motion="full"][state="idle"]) .aura { animation: bc-breathe var(--cycle-float, 4.2s) ease-in-out infinite; }
:host(:not([motion="off"])[state="needs-help"]) .aura,
:host(:not([motion="off"])[state="error"]) .aura { animation: bc-softpulse var(--cycle-pulse, 2.6s) ease-in-out infinite; }
:host(:not([motion="off"])[pulse]) .bot-inner { animation: bc-pulse var(--dur-success, 350ms) cubic-bezier(.34,1.45,.64,1); }
:host(:not([motion="off"])[pulse]) .disc-ring { animation: bc-flash 600ms ease-out; }
:host(:not([motion="off"])[sparkle]) .sp { animation: bc-sparkle 900ms cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d); }
:host(:not([motion="off"])[nod]) .bot-inner { animation: bc-nod 420ms ease-in-out; }
:host([motion="low"]) .disc-ring3 { animation: none; }
:host([paused]) * { animation-play-state: paused !important; }
:host([motion="off"]) .face, :host([motion="off"]) .eyes { transition: none; }

/* ---- speech bubble ---- */
.bubble {
  position: absolute; left: var(--bubble-left, 76%); top: 0; z-index: 2;
  min-width: 160px; max-width: min(var(--bubble-max, 230px), 70vw); width: max-content;
  padding: 12px 16px; border-radius: 18px 18px 18px 6px;
  font: 500 var(--fs-md, 15px)/1.4 var(--font-sans, -apple-system, system-ui, sans-serif);
  color: var(--text-primary, #f1f4ff);
  background: linear-gradient(160deg, rgba(36, 44, 104, .72), rgba(18, 22, 60, .72));
  -webkit-backdrop-filter: blur(14px) saturate(140%); backdrop-filter: blur(14px) saturate(140%);
  box-shadow: 0 16px 40px -14px rgba(0,0,0,.7), 0 0 calc(28px * var(--glow-strength, 1)) -8px rgba(139, 92, 246, .55);
  opacity: 0; transform: translateY(6px) scale(.9); transform-origin: 0 100%;
  transition: opacity 200ms ease, transform var(--dur-panel, 260ms) cubic-bezier(.34,1.45,.64,1);
  pointer-events: none; text-wrap: pretty;
}
.bubble::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1px; pointer-events: none;
  background: var(--gradient-border-strong, linear-gradient(140deg, #38bdf8, #8b5cf6, #e879f9));
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); -webkit-mask-composite: xor;
  mask: linear-gradient(#000 0 0) content-box exclude, linear-gradient(#000 0 0);
  opacity: .85;
}
.bubble.show { opacity: 1; transform: none; pointer-events: auto; }
:host([bubble="left"]) .bubble { left: auto; right: 80%; border-radius: 18px 18px 6px 18px; transform-origin: 100% 100%; }
:host([bubble="top"]) .bubble { left: 50%; top: auto; bottom: 96%; border-radius: 18px; transform: translate(-50%, 6px) scale(.9); transform-origin: 50% 100%; }
:host([bubble="top"]) .bubble.show { transform: translate(-50%, 0); }
:host([size="sm"]) .bubble, :host([size="xs"]) .bubble { font-size: 13px; min-width: 140px; padding: 9px 12px; }
.halo { position: absolute; inset: 0; pointer-events: none; }

/* ---- seasonal accessories (markup from seasons-fx.js) ---- */
.acc { pointer-events: none; }
:host([size="sm"]) .acc-body, :host([size="xs"]) .acc-body, :host([data-ops]) .acc-extra { display: none; }
`;

class BusterCompanion extends HTMLElement {
  static get observedAttributes() { return ["state", "size", "accent", "name", "message", "level", "season"]; }

  constructor() {
    super();
    this._p = `bc${++uid}-`;
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${STYLE}</style>${svgMarkup(this._p)}<div class="bubble" part="bubble" role="status" aria-live="polite"></div><div class="halo"><slot name="halo"></slot></div>`;
    this._svg = root.querySelector("svg");
    this._acc = root.querySelector(".acc");
    this._bubble = root.querySelector(".bubble");
    this._orbitBack = root.querySelector(".orbit-back");
    this._orbitFront = root.querySelector(".orbit-front");
    this._timers = new Set();
    this._level = 0;
    this._externalAt = 0;
  }

  connectedCallback() {
    if (!this.hasAttribute("state")) this.setAttribute("state", "idle");
    this.setAttribute("role", "img");
    this._applyAccent();
    this._applySize();
    this._applyState(this.state, null);
    this._unsubMotion = bindMotion(this);
    lookers.add(this);
    companions.add(this);
    this._applySeason();
    if (this.hasAttribute("message")) this.say(this.getAttribute("message"), { duration: 0 });
    this._scheduleBlink();
  }

  disconnectedCallback() {
    this._unsubMotion?.();
    lookers.delete(this);
    companions.delete(this);
    this._stopOrbit();
    this._stopSynth();
    this._meter?.stop();
    this._timers.forEach(clearTimeout);
    this._timers.clear();
  }

  attributeChangedCallback(name, oldV, newV) {
    if (!this.isConnected) return;
    if (name === "state" && oldV !== newV) this._applyState(newV, oldV);
    else if (name === "accent") this._applyAccent();
    else if (name === "size") this._applySize();
    else if (name === "name") this._applyLabel();
    else if (name === "message") newV ? this.say(newV, { duration: 0 }) : this.hideBubble();
    else if (name === "level") this.level = Number(newV);
    else if (name === "season") this._applySeason();
  }

  /* ---------- public API ---------- */
  get state() { const s = this.getAttribute("state"); return STATES.includes(s) ? s : "idle"; }
  set state(v) { this.setAttribute("state", STATES.includes(v) ? v : "idle"); }

  get level() { return this._level; }
  set level(v) {
    this._level = Math.max(0, Math.min(1, Number(v) || 0));
    this._externalAt = performance.now();
    this.style.setProperty("--level", this._level.toFixed(3));
  }

  say(text, { duration = 4500 } = {}) {
    this._clear("bubble");
    if (!text) { this.hideBubble(); return this; }
    this._bubble.textContent = text;
    // next frame so the spring transition runs
    requestAnimationFrame(() => this._bubble.classList.add("show"));
    if (duration > 0) this._later("bubble", () => this.hideBubble(), duration);
    return this;
  }

  hideBubble() { this._bubble.classList.remove("show"); return this; }

  celebrate() { this.state = "success"; return this; }

  react(kind, opts = {}) {
    switch (kind) {
      case "wow": case "discover": this.state = "discovering"; break;
      case "success": case "celebrate": this.celebrate(); break;
      case "blink": this._blink(); break;
      case "nod": this._flag("nod", 440); break;
      case "concern": this.state = "needs-help"; break;
      case "look": this._setLook(Number(opts.x) || 0, Number(opts.y) || 0); break;
      case "ping": this._flag("pulse", 400); break;
      default: break;
    }
    return this;
  }

  attachStream(stream) { this._meter?.stop(); this._meter = createLevelMeter(stream, (l) => { this.level = l; }); return this._meter; }
  attachAnalyser(node) { return this.attachStream(node); }
  detachAudio() { this._meter?.stop(); this._meter = null; }

  /* ---------- internals ---------- */
  onMotion({ level }) {
    if (level === "off") this._setLook(0, 0);
    this._syncLoops();
  }

  _applyAccent() {
    const a = ACCENTS[this.getAttribute("accent")] || ACCENTS.cyan;
    const s = this.style;
    s.setProperty("--bc-acc", a.acc); s.setProperty("--bc-eye", a.eye);
    s.setProperty("--bc-fin-a", a.finA); s.setProperty("--bc-fin-b", a.finB);
    s.setProperty("--bc-rim-a", a.rimA); s.setProperty("--bc-rim-b", a.rimB);
  }

  /** Seasonal accessory layer. `season="none"` on the element opts this instance out. */
  _applySeason() {
    const html = document.documentElement;
    const own = this.getAttribute("season");
    const season = own || html.dataset.season || "none";
    const variant = own ? "" : html.dataset.seasonVariant || "";
    const ops = html.dataset.mode === "operations";
    this.toggleAttribute("data-ops", ops);
    const render = window.BusterSeasons?.accessory;
    const key = `${season}|${variant}|${ops}|${!!render}`;
    if (key === this._seasonKey) return;
    this._seasonKey = key;
    let res = null;
    if (season !== "none" && render) res = render(season, variant, { ops, p: this._p, size: this.getAttribute("size") || "lg" });
    else if (season !== "none") window.BusterSeasons?.load?.();
    this._acc.innerHTML = res?.svg || "";
    const accent = this.getAttribute("accent");
    if (res?.eye && (!accent || accent === "cyan")) this.style.setProperty("--bc-eye-season", res.eye);
    else this.style.removeProperty("--bc-eye-season");
  }

  _applySize() {
    const compact = ["sm", "xs"].includes(this.getAttribute("size"));
    this._svg.setAttribute("viewBox", compact ? "28 12 184 184" : "0 0 240 240");
  }

  _applyLabel() {
    const name = this.getAttribute("name") || "Buster";
    this.setAttribute("aria-label", `${name}, ${LABEL[this.state]}`);
  }

  _applyState(state, previous) {
    state = STATES.includes(state) ? state : "idle";
    this.dataset.expr = EXPRESSION[state];
    this.dataset.mouth = MOUTH[state];
    this._applyLabel();
    this._clear("transient");
    if (state === "success") { this._flag("pulse", 420); this._flag("sparkle", 1000); }
    if (state === "discovering") this._flag("sparkle", 1000);
    if (TRANSIENT[state] && !this.hasAttribute("hold")) {
      const back = state === "discovering" && previous && !TRANSIENT[previous] ? previous : (this.getAttribute("rest") || "idle");
      this._later("transient", () => { if (this.state === state) this.state = back; }, TRANSIENT[state]);
    }
    if (state === "thinking") this._setLook(3.5, -3);
    else if (state === "needs-help" || state === "error") this._setLook(0, 1.5);
    else this._setLook(0, 0);
    this._syncLoops();
    if (previous !== null && previous !== state) {
      this.dispatchEvent(new CustomEvent("buster-statechange", { bubbles: true, composed: true, detail: { state, previous } }));
    }
  }

  _syncLoops() {
    const lvl = Motion.level;
    const st = this.state;
    // thinking: orbiting particles (JS for true depth ordering); static ring of particles when off
    if (st === "thinking") this._startOrbit(lvl); else this._stopOrbit();
    // listening: synthetic breathing level when nobody feeds a real level
    if (st === "listening" && lvl !== "off") this._startSynth(); else this._stopSynth();
    if (st === "listening" && lvl === "off" && !this._externalAt) this.style.setProperty("--level", "0.45");
  }

  _startOrbit(lvl) {
    const n = lvl === "full" ? 4 : 3;
    if (!this._particles || this._particles.length !== n) {
      this._orbitBack.textContent = ""; this._orbitFront.textContent = "";
      const ns = "http://www.w3.org/2000/svg";
      const trail = document.createElementNS(ns, "ellipse");
      trail.setAttribute("class", "trail");
      trail.setAttribute("cx", "120"); trail.setAttribute("cy", "104");
      trail.setAttribute("rx", "96"); trail.setAttribute("ry", "30");
      trail.setAttribute("transform", "rotate(-12 120 104)");
      this._orbitBack.appendChild(trail);
      this._particles = Array.from({ length: n }, (_, i) => {
        const c = document.createElementNS(ns, "circle");
        c.setAttribute("filter", `url(#${this._p}glow)`);
        this._orbitBack.appendChild(c);
        return { el: c, off: (i / n) * Math.PI * 2, size: i === 0 ? 4.6 : 3.2 - i * 0.3, front: false };
      });
    }
    this._placeOrbit(0.6);
    this._stopOrbitLoop();
    if (lvl !== "off") {
      const T = 2200;
      this._orbitUnsub = Motion.onFrame((now) => this._placeOrbit((now / T) * Math.PI * 2), { fps: lvl === "full" ? 60 : 24 });
    }
  }

  _placeOrbit(theta) {
    const tilt = (-12 * Math.PI) / 180, cos = Math.cos(tilt), sin = Math.sin(tilt);
    for (const pt of this._particles || []) {
      const a = theta + pt.off;
      const x0 = 96 * Math.cos(a), y0 = 30 * Math.sin(a);
      const x = 120 + x0 * cos - y0 * sin, y = 104 + x0 * sin + y0 * cos;
      const depth = Math.sin(a); // >0: in front of the head
      pt.el.setAttribute("cx", x.toFixed(1)); pt.el.setAttribute("cy", y.toFixed(1));
      pt.el.setAttribute("r", (pt.size * (0.72 + 0.28 * (depth + 1) / 2 * 1.4)).toFixed(2));
      pt.el.setAttribute("opacity", (0.45 + 0.55 * (depth + 1) / 2).toFixed(2));
      const front = depth > 0;
      if (front !== pt.front) { pt.front = front; (front ? this._orbitFront : this._orbitBack).appendChild(pt.el); }
    }
  }

  _stopOrbitLoop() { this._orbitUnsub?.(); this._orbitUnsub = null; }
  _stopOrbit() {
    this._stopOrbitLoop();
    if (this._particles) { this._orbitBack.textContent = ""; this._orbitFront.textContent = ""; this._particles = null; }
  }

  _startSynth() {
    if (this._synthUnsub) return;
    this._synthUnsub = Motion.onFrame((now) => {
      if (performance.now() - this._externalAt < 800) return; // real level present
      const v = 0.3 + 0.16 * Math.sin(now / 420) + 0.08 * Math.sin(now / 170);
      this.style.setProperty("--level", v.toFixed(3));
    }, { fps: 30 });
  }
  _stopSynth() { this._synthUnsub?.(); this._synthUnsub = null; }

  _followPointer() {
    if (this.hasAttribute("no-follow") || Motion.level === "off") return;
    const st = this.state;
    if (st === "thinking" || st === "needs-help" || st === "error") return;
    const r = this.getBoundingClientRect();
    if (!r.width || r.bottom < 0 || r.top > innerHeight) return;
    const dx = pointer.x - (r.left + r.width / 2);
    const dy = pointer.y - (r.top + r.height * 0.42);
    this._setLook(dx / (Math.abs(dx) + 240), dy / (Math.abs(dy) + 240));
  }

  _setLook(nx, ny) {
    // accepts normalized -1..1 or explicit pixel offsets (|v| > 1)
    const x = Math.abs(nx) > 1 ? nx : nx * 6;
    const y = Math.abs(ny) > 1 ? ny : ny * 4;
    this.style.setProperty("--lx", x.toFixed(2));
    this.style.setProperty("--ly", y.toFixed(2));
  }

  _scheduleBlink() {
    const wait = 2600 + Math.random() * 4200;
    this._later("blink", () => {
      if (Motion.active && this.dataset.expr !== "focused") {
        this._blink();
        if (Math.random() < 0.25) this._later("blink2", () => this._blink(), 260); // double blink
        // wander the gaze if the pointer has been still for a while
        if (performance.now() - pointer.t > 5000 && this.state === "idle" && Motion.level === "full") {
          this._setLook((Math.random() - 0.5) * 1.2, (Math.random() - 0.5) * 0.8);
        }
      }
      this._scheduleBlink();
    }, wait);
  }

  _blink() { this._flag("blink", 150); }

  _flag(attr, ms) {
    this.removeAttribute(attr);
    // force restart of CSS animation
    void this.offsetWidth;
    this.setAttribute(attr, "");
    this._later(`flag-${attr}`, () => this.removeAttribute(attr), ms);
  }

  _later(key, fn, ms) {
    this._clear(key);
    const id = setTimeout(() => { this._timers.delete(id); this[`_t_${key}`] = null; fn(); }, ms);
    this[`_t_${key}`] = id;
    this._timers.add(id);
  }
  _clear(key) {
    const id = this[`_t_${key}`];
    if (id) { clearTimeout(id); this._timers.delete(id); this[`_t_${key}`] = null; }
  }
}

/* ======================================================================
   <buster-agent> — mini companion with progress halo + status label
   ====================================================================== */
const AGENT_STATUS = {
  working: { label: "Working…", dot: "var(--status-ok, #34d399)", face: "thinking" },
  communicating: { label: "Communicating", dot: "var(--status-info, #60a5fa)", face: "listening" },
  "waiting-approval": { label: "Waiting for approval", dot: "var(--status-warn, #fbbf24)", face: "needs-help" },
  done: { label: "Done", dot: "var(--status-ok, #34d399)", face: "idle" },
  idle: { label: "Idle", dot: "var(--status-idle, #6b7499)", face: "idle" },
};

const AGENT_STYLE = `
:host { display: flex; align-items: center; gap: 12px; min-width: 0; font-family: var(--font-sans, system-ui, sans-serif); color: var(--text-primary, #f1f4ff); }
:host([compact]) .txt { display: none; }
.av { position: relative; width: 46px; height: 46px; flex: none; display: grid; place-items: center; border-radius: 50%;
  background: radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--ba-acc) 22%, transparent), transparent 70%); }
.av buster-companion { --bc-size: 36px; width: 36px; }
svg.halo { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.track { fill: none; stroke: rgba(148, 163, 255, .14); stroke-width: 2.4; }
.arc { fill: none; stroke: var(--ba-acc); stroke-width: 2.6; stroke-linecap: round; transform-origin: 23px 23px; transform: rotate(-90deg);
  filter: drop-shadow(0 0 calc(4px * var(--glow-strength, 1)) var(--ba-acc)); transition: stroke-dasharray .5s cubic-bezier(.2,.8,.2,1); }
.ripple { fill: none; stroke: var(--ba-acc); stroke-width: 1.5; opacity: 0; transform-origin: 23px 23px; }
.badge { position: absolute; right: -2px; bottom: -2px; width: 16px; height: 16px; border-radius: 50%; display: none; place-items: center;
  background: var(--status-ok, #34d399); color: #052e1f; box-shadow: 0 0 0 2px var(--c-bg-2, #0b1030); }
.badge svg { width: 10px; height: 10px; }
.txt { min-width: 0; display: grid; gap: 2px; }
.name { font-size: var(--fs-base, 14px); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; letter-spacing: -.005em; }
.status { display: flex; align-items: center; gap: 6px; font-size: var(--fs-sm, 12.5px); color: var(--text-muted, #919cc8); min-width: 0; }
.status span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dot { width: 7px; height: 7px; border-radius: 50%; flex: none; background: var(--ba-dot); box-shadow: 0 0 calc(8px * var(--glow-strength, 1)) var(--ba-dot); }
:host([status="done"]) .badge { display: grid; }
:host([status="done"]) .arc { stroke: var(--status-ok, #34d399); }
:host([status="waiting-approval"]) .arc { stroke: var(--status-warn, #fbbf24); stroke-dasharray: 3 5 !important; }
:host([status="idle"]) .arc { opacity: 0; }
@keyframes ba-spin { to { transform: rotate(270deg); } }
@keyframes ba-ripple { 0% { opacity: .7; transform: scale(.9); } 100% { opacity: 0; transform: scale(1.3); } }
@keyframes ba-soft { 0%, 100% { opacity: .55; } 50% { opacity: 1; } }
@keyframes ba-dot { 0%, 100% { box-shadow: 0 0 0 0 var(--ba-dot); } 50% { box-shadow: 0 0 0 4px transparent, 0 0 10px var(--ba-dot); } }
:host(:not([motion="off"])[status="working"]:not([progress])) .arc { animation: ba-spin 1.6s linear infinite; }
:host(:not([motion="off"])[status="communicating"]) .ripple { animation: ba-ripple 1.8s ease-out infinite; }
:host(:not([motion="off"])[status="waiting-approval"]) .arc { animation: ba-soft var(--cycle-pulse, 2.6s) ease-in-out infinite; }
:host(:not([motion="off"])[status="working"]) .dot { animation: ba-dot 1.8s ease-in-out infinite; }
:host([paused]) * { animation-play-state: paused !important; }
`;

class BusterAgent extends HTMLElement {
  static get observedAttributes() { return ["name", "status", "accent", "progress"]; }

  constructor() {
    super();
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${AGENT_STYLE}</style>
      <div class="av" part="avatar">
        <svg class="halo" viewBox="0 0 46 46" aria-hidden="true"><circle class="track" cx="23" cy="23" r="21.5"/><circle class="ripple" cx="23" cy="23" r="21.5"/><circle class="arc" cx="23" cy="23" r="21.5"/></svg>
        <buster-companion size="xs" no-follow></buster-companion>
        <span class="badge" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.2 4.2L19 7"/></svg></span>
      </div>
      <div class="txt"><div class="name" part="name"></div><div class="status" part="status"><i class="dot"></i><span><slot></slot></span></div></div>`;
    this._comp = root.querySelector("buster-companion");
    this._arc = root.querySelector(".arc");
    this._name = root.querySelector(".name");
    this._slot = root.querySelector("slot");
  }

  connectedCallback() {
    if (!this.hasAttribute("status")) this.setAttribute("status", "idle");
    this.setAttribute("role", "group");
    this._unsubMotion = bindMotion(this);
    this._render();
  }
  disconnectedCallback() { this._unsubMotion?.(); }
  attributeChangedCallback() { if (this.isConnected) this._render(); }

  get status() { return this.getAttribute("status") || "idle"; }
  set status(v) { this.setAttribute("status", v); }
  get progress() { return Number(this.getAttribute("progress")); }
  set progress(v) { v == null ? this.removeAttribute("progress") : this.setAttribute("progress", String(v)); }

  _render() {
    const st = AGENT_STATUS[this.status] ? this.status : "idle";
    const info = AGENT_STATUS[st];
    const accent = this.getAttribute("accent") || "cyan";
    const a = ACCENTS[accent] || ACCENTS.cyan;
    const name = this.getAttribute("name") || "Agent";
    this.style.setProperty("--ba-acc", a.acc);
    this.style.setProperty("--ba-dot", info.dot);
    this._comp.setAttribute("accent", accent);
    this._comp.setAttribute("name", name);
    if (this._comp.getAttribute("state") !== info.face) this._comp.setAttribute("state", info.face);
    this._name.textContent = name;
    this._slot.textContent = info.label; // fallback content when no light-DOM text is given
    const C = 2 * Math.PI * 21.5;
    let frac;
    if (st === "done") frac = 1;
    else if (this.hasAttribute("progress")) frac = Math.max(0, Math.min(100, this.progress || 0)) / 100;
    else if (st === "working") frac = 0.28;
    else frac = st === "idle" ? 0 : 1;
    this._arc.style.strokeDasharray = `${(C * frac).toFixed(1)} ${C.toFixed(1)}`;
    const text = (this.textContent.trim() || info.label);
    this.setAttribute("aria-label", `${name}: ${text}${this.hasAttribute("progress") && st === "working" ? `, ${Math.round(this.progress)}%` : ""}`);
  }
}

if (!customElements.get("buster-companion")) customElements.define("buster-companion", BusterCompanion);
if (!customElements.get("buster-agent")) customElements.define("buster-agent", BusterAgent);

export { BusterCompanion, BusterAgent };
