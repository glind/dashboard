/*!
 * Buster Design System — companion.js
 *
 * The Buster avatar: a glossy white robot-bunny head with a black glass visor, glowing eyes,
 * tall bunny ears with a blue→violet→pink inner glow, glowing ear pods, floating above a
 * holographic hover pad (reference: buster-design/reference/buster-avatar-sheet.webp).
 *
 * <buster-companion state="idle|listening|thinking|discovering|success|needs-help|error|speaking|sleeping"
 *                   view="front|three-quarter|side|back"
 *                   size="lg|md|sm|xs" accent="cyan|blue|violet|green|amber|magenta|pink|coral"
 *                   name="Buster" message="Hey! 👋" bubble="right|left|top" ground="none" no-follow hold>
 *
 *   el.state = "thinking"            // attribute or property
 *   el.view = "side"                 // turnaround views (default front)
 *   el.say("Done!", { duration })    // speech bubble (duration ms, 0 = stay)
 *   el.celebrate()                   // success: 350ms pulse + sparkle, then back to idle
 *   el.react("wow"|"blink"|"nod"|"look"|"success"|"concern"|"ping", opts)
 *   el.level = 0..1                  // listening / speaking: audio-reactive glow + mouth
 *   el.attachStream(mediaStream) / el.attachAnalyser(node) / el.detachAudio()
 *   events: "buster-statechange" { state, previous }
 *
 * Expressions (from the reference sheet):
 *   idle / success → Happy (^ ^ arcs) · listening → tall rounded ovals · thinking → one slanted
 *   line + one small eye, ears askew · discovering / needs-help → Alert (wide "0" eyes + spark
 *   lines by the right ear) · error → worried (small eyes, slanted brows, drooped ears) ·
 *   speaking → soft ovals, mouth pulses with level · sleeping → closed arcs, drooped ears, dim.
 *
 * Motion spec (all gated by motion.js — static but complete when motion is off):
 *   gentle 4.2s bob above the pad + random blink + eyes follow pointer + ears sway independently
 *   (full motion only) · listening glow+waves from level · thinking orbiting particles 2.2s ·
 *   discovering wow + sparkle (brief) · success 350ms pulse + sparkle → idle ·
 *   needs-help/error soft amber/rose pulse, no shake · sleeping slow bob.
 */
import { Motion, bindMotion } from "./motion.js";
import { createLevelMeter } from "./waveform.js";

export const STATES = ["idle", "listening", "thinking", "discovering", "success", "needs-help", "error", "speaking", "sleeping"];
export const VIEWS = ["front", "three-quarter", "side", "back"];
const EXPRESSION = { idle: "happy", listening: "open", thinking: "thinking", discovering: "alert", success: "happy", "needs-help": "alert", error: "worried", speaking: "speak", sleeping: "sleep" };
const MOUTH = { idle: "dot", listening: "dot", thinking: "small", discovering: "o", success: "dot", "needs-help": "dot", error: "wavy", speaking: "talk", sleeping: "dot" };
const LABEL = { idle: "idle", listening: "listening", thinking: "thinking", discovering: "found something", success: "task completed", "needs-help": "needs your help", error: "ran into a problem", speaking: "speaking", sleeping: "sleeping" };
const TRANSIENT = { success: 1250, discovering: 1800 };
const AUDIO_STATES = new Set(["listening", "speaking"]);

export const ACCENTS = {
  cyan:    { acc: "#22d3ee", eye: "#7cf0ff", finA: "#38bdf8", finB: "#8b5cf6", rimA: "#67e8f9", rimB: "#a78bfa", tail: "#f0abfc" },
  blue:    { acc: "#60a5fa", eye: "#9cc8ff", finA: "#60a5fa", finB: "#4f46e5", rimA: "#93c5fd", rimB: "#818cf8", tail: "#c4b5fd" },
  violet:  { acc: "#a78bfa", eye: "#cbbcff", finA: "#a78bfa", finB: "#7c3aed", rimA: "#c4b5fd", rimB: "#e879f9", tail: "#f9a8d4" },
  green:   { acc: "#34d399", eye: "#7bf0c4", finA: "#34d399", finB: "#0891b2", rimA: "#6ee7b7", rimB: "#22d3ee", tail: "#a5f3fc" },
  amber:   { acc: "#fbbf24", eye: "#fcd56b", finA: "#fbbf24", finB: "#f97316", rimA: "#fde68a", rimB: "#fb923c", tail: "#fda4af" },
  magenta: { acc: "#e879f9", eye: "#f3c4fd", finA: "#e879f9", finB: "#9333ea", rimA: "#f5d0fe", rimB: "#a78bfa", tail: "#f9a8d4" },
  pink:    { acc: "#f472b6", eye: "#fbc4e1", finA: "#f472b6", finB: "#a855f7", rimA: "#fbcfe8", rimB: "#c084fc", tail: "#fecdd3" },
  coral:   { acc: "#ff7f6e", eye: "#ffc2b8", finA: "#fb923c", finB: "#f43f5e", rimA: "#fecaca", rimB: "#fb7185", tail: "#fde68a" },
};

/* ---- shared geometry (240×240 space; the native SwiftUI renderer uses the same numbers) ---- */
export const GEOMETRY = {
  head: "M120 78 C163 78 188 104 188 138 C188 172 161 194 120 194 C79 194 52 172 52 138 C52 104 77 78 120 78Z",
  visor: "M120 100 C153 100 173 115 174 139 C175 163 154 178 120 178 C86 178 65 163 66 139 C67 115 87 100 120 100Z",
  // ears are drawn upright in local space, base at (0,0), then placed + tilted
  earOuter: "M0 -90 C15 -90 21 -64 20 -40 C19 -16 12 0 0 0 C-12 0 -19 -16 -20 -40 C-21 -64 -15 -90 0 -90Z",
  earDark: "M0 -82 C11 -82 15.5 -62 15 -42 C14.5 -22 9 -8 0 -8 C-9 -8 -14.5 -22 -15 -42 C-15.5 -62 -11 -82 0 -82Z",
  earGlow: "M0 -77 C8.5 -77 12 -60 11.5 -43 C11 -27 7 -14 0 -14 C-7 -14 -11 -27 -11.5 -43 C-12 -60 -8.5 -77 0 -77Z",
  earL: { x: 95, y: 100, rot: -18 },
  earR: { x: 145, y: 100, rot: 18 },
  // seasonal accessories were authored for the old helmet (top at y≈48); move them onto the new crown
  accHat: "translate(0 27)",
  accBody: "translate(120 0) scale(1.32 1) translate(-120 0) translate(0 10)", // scarf: inside accHat, wrapped round the base of the head
};

const VIEW_LAYOUT = {
  // transforms for: face (visor + eyes), ear L, ear R, pod L, pod R (attribute strings)
  front: { face: "", earL: "", earR: "", podL: "", podR: "" },
  "three-quarter": {
    face: "translate(138 0) scale(.84 1) translate(-120 0)",
    earL: "translate(10 3)", earR: "translate(14 -1)",
    podL: "translate(60 140) scale(1.5 1.02) translate(-50 -140)", podR: "translate(187 140) scale(.4 .9) translate(-190 -140)",
  },
  side: { face: "", earL: "translate(18 -2) rotate(-6 97 100)", earR: "", podL: "", podR: "" },
  back: { face: "", earL: "", earR: "", podL: "", podR: "" },
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
function ear(p, side) {
  const g = GEOMETRY[side === "l" ? "earL" : "earR"];
  return `
    <g class="ear-place ear-${side}" transform="translate(${g.x} ${g.y}) rotate(${g.rot})">
      <g class="ear-tilt"><g class="ear-sway">
        <path class="ear-aura" d="${GEOMETRY.earOuter}" filter="url(#${p}bloom)"/>
        <path class="ear-outer" d="${GEOMETRY.earOuter}" fill="url(#${p}shell-ear)"/>
        <path class="ear-rim" d="${GEOMETRY.earOuter}" fill="none" stroke="url(#${p}rim)" stroke-width="1.6"/>
        <g class="ear-front">
          <path d="${GEOMETRY.earDark}" fill="#0a0e2a"/>
          <path class="ear-glow-soft" d="${GEOMETRY.earGlow}" fill="url(#${p}eglow)" filter="url(#${p}soft)"/>
          <path d="${GEOMETRY.earGlow}" fill="url(#${p}eglow)"/>
          <path d="M-5 -66 C-8 -54 -8 -40 -6 -28" fill="none" stroke="#fff" stroke-opacity=".45" stroke-width="2.2" stroke-linecap="round"/>
        </g>
        <path class="ear-back-hl" d="M-8 -74 C-13 -58 -13 -34 -8 -16" fill="none" stroke="#fff" stroke-opacity=".8" stroke-width="3" stroke-linecap="round"/>
      </g></g>
    </g>`;
}

function pod(p, side) {
  const cx = side === "l" ? 50 : 190;
  return `
    <g class="pod pod-${side}">
      <ellipse cx="${cx}" cy="140" rx="12.5" ry="25" fill="url(#${p}pod)"/>
      <ellipse cx="${cx}" cy="140" rx="9" ry="20.5" fill="#0b1030"/>
      <ellipse class="pod-ring-glow" cx="${cx}" cy="140" rx="6.8" ry="16.5" fill="none" stroke="url(#${p}podring)" stroke-width="5" filter="url(#${p}soft)"/>
      <ellipse cx="${cx}" cy="140" rx="6.8" ry="16.5" fill="none" stroke="url(#${p}podring)" stroke-width="2.6"/>
    </g>`;
}

function svgMarkup(p) {
  const spark = (x, y, s, d) => `<use class="sp" href="#${p}spark" x="${x - s / 2}" y="${y - s / 2}" width="${s}" height="${s}" style="--d:${d}ms"/>`;
  const G = GEOMETRY;
  return `
<svg class="svg" part="svg" viewBox="0 0 240 240" aria-hidden="true" focusable="false">
  <defs>
    <radialGradient id="${p}shell" cx="38%" cy="22%" r="88%">
      <stop offset="0" stop-color="#ffffff"/><stop offset=".38" stop-color="#eef1fb"/><stop offset=".7" stop-color="#c3cbe8"/><stop offset=".9" stop-color="#8d97c9"/><stop offset="1" stop-color="#6f78b4"/>
    </radialGradient>
    <linearGradient id="${p}shell-ear" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#ffffff"/><stop offset=".55" stop-color="#e4e8f7"/><stop offset="1" stop-color="#9aa3d4"/>
    </linearGradient>
    <linearGradient id="${p}rim" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" class="rim-a"/><stop offset=".5" stop-color="#c7d2fe" stop-opacity=".5"/><stop offset="1" class="rim-b"/>
    </linearGradient>
    <linearGradient id="${p}eglow" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" class="fin-a"/><stop offset=".55" class="fin-b"/><stop offset="1" class="tail"/>
    </linearGradient>
    <linearGradient id="${p}podring" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" class="tail"/><stop offset=".5" class="fin-b"/><stop offset="1" class="fin-a"/>
    </linearGradient>
    <linearGradient id="${p}pod" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f4f6ff"/><stop offset=".6" stop-color="#aeb6dc"/><stop offset="1" stop-color="#5b6399"/>
    </linearGradient>
    <radialGradient id="${p}visor" cx="50%" cy="18%" r="85%">
      <stop offset="0" stop-color="#1c2458"/><stop offset=".45" stop-color="#070a1c"/><stop offset="1" stop-color="#010207"/>
    </radialGradient>
    <radialGradient id="${p}disc" cx="50%" cy="50%" r="50%">
      <stop offset="0" class="ring-c" stop-opacity=".5"/><stop offset=".55" class="ring-c" stop-opacity=".14"/><stop offset="1" class="ring-c" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="${p}ring" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#8b5cf6"/><stop offset=".3" class="ring-c"/><stop offset=".7" class="ring-c"/><stop offset="1" stop-color="#e879f9"/>
    </linearGradient>
    <filter id="${p}glow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="${p}soft" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="3.2"/></filter>
    <filter id="${p}bloom" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
    <filter id="${p}blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.6"/></filter>
    <clipPath id="${p}visor-clip"><path d="${G.visor}"/></clipPath>
    <clipPath id="${p}head-clip"><path d="${G.head}"/></clipPath>
    <symbol id="${p}spark" viewBox="-10 -10 20 20"><path d="M0-10C1-3 3-1 10 0 3 1 1 3 0 10-1 3-3 1-10 0-3-1-1-3 0-10Z"/></symbol>
  </defs>

  <g class="ground">
    <ellipse class="disc-halo" cx="120" cy="214" rx="104" ry="22" fill="url(#${p}disc)"/>
    <ellipse class="disc-ring3" cx="120" cy="214" rx="82" ry="14.5" fill="none" stroke="url(#${p}ring)" stroke-width="1.2" stroke-dasharray="3 7" opacity=".6"/>
    <ellipse class="disc-ring-glow" cx="120" cy="214" rx="66" ry="11.5" fill="none" stroke="url(#${p}ring)" stroke-width="6" filter="url(#${p}soft)" opacity=".8"/>
    <ellipse class="disc-ring" cx="120" cy="214" rx="66" ry="11.5" fill="none" stroke="url(#${p}ring)" stroke-width="2.4"/>
    <ellipse class="disc-ring2" cx="120" cy="214" rx="44" ry="7" fill="none" stroke-opacity=".85" stroke-width="1.6"/>
    <ellipse class="disc-core" cx="120" cy="214" rx="26" ry="3.6" filter="url(#${p}blur)"/>
    <ellipse class="disc-shadow" cx="120" cy="210" rx="34" ry="4.5" fill="#01020a" opacity=".5" filter="url(#${p}blur)"/>
  </g>

  <g class="orbit orbit-back"></g>

  <g class="bot">
    <g class="bot-inner">
      <g class="aura" filter="url(#${p}bloom)">
        <path d="${G.head}"/>
      </g>
      <g class="waves" fill="none" stroke-linecap="round">
        <path d="M28 124 Q20 140 28 156"/><path d="M18 116 Q6 140 18 164"/>
        <path d="M212 124 Q220 140 212 156"/><path d="M222 116 Q234 140 222 164"/>
      </g>
      <g class="ears">${ear(p, "l")}${ear(p, "r")}</g>
      <g class="pods-back">${pod(p, "l")}${pod(p, "r")}</g>
      <g class="shell">
        <path class="head-rim-glow" d="${G.head}" fill="none" stroke-width="7" filter="url(#${p}soft)"/>
        <path class="head" d="${G.head}" fill="url(#${p}shell)"/>
        <g clip-path="url(#${p}head-clip)" class="seams" fill="none" stroke-linecap="round">
          <path d="M56 120 C74 92 166 92 184 120"/>
          <path class="seam-low" d="M70 184 C98 196 142 196 170 184"/>
          <path class="seam-back" d="M120 80 V194"/>
          <ellipse class="shade" cx="120" cy="186" rx="70" ry="22" fill="#5b63a5" stroke="none" opacity=".18" filter="url(#${p}soft)"/>
        </g>
        <path class="head-rim" d="${G.head}" fill="none" stroke="url(#${p}rim)" stroke-width="1.8"/>
        <ellipse class="gloss" cx="98" cy="90" rx="22" ry="6" transform="rotate(-14 98 90)" fill="#fff" opacity=".85" filter="url(#${p}blur)"/>
      </g>
      <g class="pods-front">${pod(p, "l")}${pod(p, "r")}</g>
      <g class="view-face">
        <g class="visor-frame">
          <path d="${G.visor}" fill="none" stroke="#9aa3cf" stroke-opacity=".55" stroke-width="5"/>
          <path class="visor" d="${G.visor}" fill="url(#${p}visor)"/>
          <path class="visor-edge" d="${G.visor}" fill="none" stroke-width="1.6" filter="url(#${p}glow)"/>
          <g clip-path="url(#${p}visor-clip)">
            <path class="sheen" d="M78 118 C92 104 148 102 164 116" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="5" stroke-linecap="round" filter="url(#${p}blur)"/>
            <ellipse cx="84" cy="122" rx="5" ry="2.4" transform="rotate(-35 84 122)" fill="#fff" opacity=".55"/>
          </g>
        </g>
        <g class="face">
          <g class="eyes" filter="url(#${p}glow)">
            <g class="ex ex-happy"><path d="M90 144 C90 127 110 127 110 144"/><path d="M130 144 C130 127 150 127 150 144"/></g>
            <g class="ex ex-open"><rect x="94" y="126" width="13" height="23" rx="6.5"/><rect x="133" y="126" width="13" height="23" rx="6.5"/><rect class="core" x="97.5" y="130" width="6" height="15" rx="3"/><rect class="core" x="136.5" y="130" width="6" height="15" rx="3"/></g>
            <g class="ex ex-thinking"><path d="M92 133 L106 142"/><rect x="135" y="130" width="10" height="16" rx="5"/><rect class="core" x="138" y="133.5" width="4" height="9" rx="2"/></g>
            <g class="ex ex-alert"><ellipse class="ring" cx="100" cy="138" rx="7.5" ry="11"/><ellipse class="ring" cx="140" cy="138" rx="7.5" ry="11"/></g>
            <g class="ex ex-worried"><ellipse cx="100" cy="140" rx="5.5" ry="7"/><ellipse cx="140" cy="140" rx="5.5" ry="7"/><path class="brow" d="M89 128 L107 123"/><path class="brow" d="M133 123 L151 128"/></g>
            <g class="ex ex-speak"><rect x="94.5" y="129" width="12" height="18" rx="6"/><rect x="133.5" y="129" width="12" height="18" rx="6"/><rect class="core" x="98" y="132.5" width="5" height="11" rx="2.5"/><rect class="core" x="137" y="132.5" width="5" height="11" rx="2.5"/></g>
            <g class="ex ex-sleep"><path d="M90 138 C93 146 107 146 110 138"/><path d="M130 138 C133 146 147 146 150 138"/></g>
          </g>
          <g class="mouths" filter="url(#${p}glow)">
            <path class="m m-dot" d="M116.5 155 Q120 154 123.5 155 Q122 159.5 120 159.5 Q118 159.5 116.5 155Z"/>
            <ellipse class="m m-small" cx="124" cy="157" rx="2.2" ry="1.8"/>
            <ellipse class="m m-o" cx="120" cy="158" rx="3.8" ry="4.6"/>
            <ellipse class="m m-talk" cx="120" cy="157" rx="4.2" ry="3"/>
            <path class="m m-wavy" d="M112 158 q4 -3.5 8 0 q4 3.5 8 0"/>
          </g>
        </g>
      </g>
      <g class="view-side">
        <path d="M166 104 C182 112 189 126 188.5 140 C188 157 181 170 166 180 C175 160 176 124 166 104Z" fill="url(#${p}visor)"/>
        <path d="M166 104 C182 112 189 126 188.5 140 C188 157 181 170 166 180" fill="none" class="visor-edge" stroke-width="1.4" filter="url(#${p}glow)"/>
        <circle cx="110" cy="140" r="27" fill="url(#${p}pod)"/>
        <circle cx="110" cy="140" r="21" fill="#0b1030"/>
        <circle cx="110" cy="140" r="15" fill="none" stroke="url(#${p}podring)" stroke-width="9" filter="url(#${p}soft)"/>
        <circle cx="110" cy="140" r="15" fill="none" stroke="url(#${p}podring)" stroke-width="4.4"/>
        <circle cx="110" cy="140" r="15" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="1.2"/>
      </g>
      <g class="view-back">
        <rect x="113" y="112" width="14" height="50" rx="7" fill="#0b1030"/>
        <rect x="116" y="116" width="8" height="42" rx="4" class="slot" filter="url(#${p}glow)"/>
      </g>
      <g class="spark-lines" fill="none" stroke-linecap="round" filter="url(#${p}glow)">
        <path d="M186 46 L180 58"/><path d="M198 54 L188 63"/><path d="M204 68 L192 71"/>
      </g>
      <g class="acc-anchor"><g class="acc"></g></g>
    </g>
  </g>

  <g class="orbit orbit-front"></g>
  <g class="sparkles">
    ${spark(40, 80, 16, 0)}${spark(204, 66, 20, 90)}${spark(212, 150, 12, 180)}${spark(28, 158, 13, 140)}${spark(150, 26, 11, 220)}${spark(62, 22, 9, 300)}
  </g>
</svg>`;
}

const STYLE = `
:host {
  --bc-size: 280px;
  display: inline-block; position: relative; width: var(--bc-size); aspect-ratio: 1 / 1;
  vertical-align: middle; -webkit-tap-highlight-color: transparent;
  --level: 0; --lx: 0; --ly: 0;
  --bc-aura: #6d5cff; --bc-aura-o: .55; --bc-ring: var(--bc-acc);
  --ear-l: 0deg; --ear-r: 0deg;
}
:host([size="md"]) { --bc-size: 168px; }
:host([size="sm"]) { --bc-size: 76px; }
:host([size="xs"]) { --bc-size: 40px; }
.svg { width: 100%; height: 100%; display: block; overflow: visible; --eye: var(--bc-eye-s, var(--bc-eye-season, var(--bc-eye))); }

.rim-a { stop-color: var(--bc-rim-a); } .rim-b { stop-color: var(--bc-rim-b); }
.fin-a { stop-color: var(--bc-fin-a); } .fin-b { stop-color: var(--bc-fin-b); } .tail { stop-color: var(--bc-tail); }
.ring-c { stop-color: var(--bc-ring); }

.aura { fill: var(--bc-aura); opacity: calc(var(--bc-aura-o) * var(--glow-strength, 1) + .08); transition: opacity .4s, fill .4s; transform-box: fill-box; transform-origin: center; }
.ear-aura { fill: var(--bc-aura); opacity: calc(var(--bc-aura-o) * var(--glow-strength, 1) + .08); transition: opacity .4s, fill .4s; }
.head-rim-glow { stroke: var(--bc-rim-b); opacity: calc(.85 * var(--glow-strength, 1)); }
.seams path { stroke: #8f99c8; stroke-opacity: .5; stroke-width: 1.3; }
.visor-edge { stroke: var(--bc-acc); stroke-opacity: .85; }
.ear-glow-soft { opacity: calc(.75 * var(--glow-strength, 1)); }
.pod-ring-glow { opacity: calc(.9 * var(--glow-strength, 1)); }
.disc-ring2 { stroke: var(--bc-ring); }
.disc-core { fill: var(--bc-ring); opacity: calc(.35 + var(--level) * .5); }
.waves path { stroke: var(--eye); stroke-width: 2.4; opacity: 0; transition: opacity .25s; }
.slot { fill: var(--eye); }
.spark-lines path { stroke: var(--eye); stroke-width: 3.4; opacity: 0; transition: opacity .2s; }

.ex { opacity: 0; transition: opacity .16s ease; }
.ex path { fill: none; stroke: var(--eye); stroke-width: 6.4; stroke-linecap: round; stroke-linejoin: round; }
.ex rect, .ex ellipse { fill: var(--eye); stroke: none; }
.ex .core { fill: #fff; opacity: .78; }
.ex .ring { fill: none; stroke: var(--eye); stroke-width: 4.6; }
.ex .brow { stroke-width: 3.6; opacity: .9; }
.m { fill: var(--eye); stroke: none; opacity: 0; transition: opacity .16s ease; }
.m-wavy { fill: none; stroke: var(--eye); stroke-width: 3; stroke-linecap: round; }
.m-talk { transform-box: fill-box; transform-origin: center; transform: scale(calc(.8 + var(--level) * .5), calc(.55 + var(--level) * 1.7)); }
:host([data-expr="happy"]) .ex-happy, :host([data-expr="open"]) .ex-open, :host([data-expr="thinking"]) .ex-thinking,
:host([data-expr="alert"]) .ex-alert, :host([data-expr="worried"]) .ex-worried, :host([data-expr="speak"]) .ex-speak, :host([data-expr="sleep"]) .ex-sleep,
:host([data-mouth="dot"]) .m-dot, :host([data-mouth="small"]) .m-small, :host([data-mouth="o"]) .m-o,
:host([data-mouth="talk"]) .m-talk, :host([data-mouth="wavy"]) .m-wavy { opacity: 1; }
:host([data-expr="alert"]) .spark-lines path { opacity: 1; }

.face { transform: translate(calc(var(--lx) * 1px), calc(var(--ly) * 1px)); transition: transform .45s cubic-bezier(.2,.8,.2,1); }
.eyes { transform-box: fill-box; transform-origin: 50% 50%; transition: transform 70ms ease-in; }
:host([blink]) .eyes { transform: scaleY(.08); }
:host([data-expr="speak"]) .ex-speak { transform-box: fill-box; transform-origin: center; transform: scaleY(calc(.92 + var(--level) * .14)); }

/* ears: placement is an SVG attribute; state tilt + sway are CSS rotations about the ear base */
.ear-tilt, .ear-sway { transform-box: view-box; transform-origin: 0 0; }
.ear-l .ear-tilt { transform: rotate(var(--ear-l)); transition: transform .5s cubic-bezier(.34,1.3,.64,1); }
.ear-r .ear-tilt { transform: rotate(var(--ear-r)); transition: transform .5s cubic-bezier(.34,1.3,.64,1); }
.ear-back-hl { display: none; }

.sp { fill: #fff; opacity: 0; transform-box: fill-box; transform-origin: center; filter: drop-shadow(0 0 3px var(--eye)); }
.sp:nth-child(2n) { fill: var(--eye); }
.sp:nth-child(3n) { fill: #f5d0fe; }

.orbit circle { fill: var(--eye); }
.orbit .trail { fill: none; stroke: var(--eye); stroke-opacity: .16; stroke-width: 1; }

/* ---- turnaround views ---- */
.view-side, .view-back { display: none; }
:host([view="side"]) .view-face, :host([view="back"]) .view-face { display: none; }
:host([view="side"]) .view-side, :host([view="back"]) .view-back { display: inline; }
:host([view="side"]) .pods-front, :host([view="side"]) .pods-back, :host([view="side"]) .ear-r { display: none; }
:host([view="side"]) .ear-l .ear-front { opacity: .9; }
:host([view="back"]) .ear-front { display: none; }
:host([view="back"]) .ear-back-hl { display: inline; }
:host([view="back"]) .seams .seam-low { display: none; }
:host(:not([view="back"])) .seams .seam-back { display: none; }
.pods-back { display: none; }
:host([view="three-quarter"]) .pod-r { display: none; }
:host([view="three-quarter"]) .pods-back .pod-r { display: inline; }
:host([view="three-quarter"]) .pods-back { display: inline; }
:host([view="three-quarter"]) .pods-back .pod-l { display: none; }
:host([view="side"]) .spark-lines, :host([view="back"]) .spark-lines { display: none; }

/* ---- state colour/intensity/ears ---- */
:host([state="listening"]) { --bc-aura-o: calc(.45 + var(--level) * .5); --ear-l: 9deg; --ear-r: -9deg; }
:host([state="listening"]) .waves path { opacity: calc(.18 + var(--level) * .9); }
:host([state="listening"]) .waves path:nth-child(2n) { opacity: calc(var(--level) * .7); }
:host([state="speaking"]) { --bc-aura-o: calc(.45 + var(--level) * .4); --ear-l: 4deg; --ear-r: -4deg; }
:host([state="thinking"]) { --bc-aura: #8b5cf6; --bc-aura-o: .6; --ear-l: 5deg; --ear-r: 24deg; }
:host([state="discovering"]) { --bc-aura: #e879f9; --bc-aura-o: .62; --ear-l: 12deg; --ear-r: -12deg; }
:host([state="success"]) { --bc-aura: #34d399; --bc-aura-o: .6; --bc-ring: #34d399; }
:host([state="needs-help"]) { --bc-aura: #fbbf24; --bc-aura-o: .5; --bc-ring: #fbbf24; --ear-l: 10deg; --ear-r: -10deg; }
:host([state="error"]) { --bc-aura: #fb7185; --bc-aura-o: .5; --bc-ring: #fb7185; --bc-eye-s: #ffb4bd; --ear-l: -26deg; --ear-r: 26deg; }
:host([state="sleeping"]) { --bc-aura-o: .22; --ear-l: -34deg; --ear-r: 34deg; }
:host([state="sleeping"]) .eyes, :host([state="sleeping"]) .mouths { opacity: .7; }
:host([state="listening"]) .disc-ring, :host([state="speaking"]) .disc-ring { transform: scale(calc(1 + var(--level) * .07)); }
.disc-ring, .disc-ring2, .disc-ring3 { transform-box: fill-box; transform-origin: center; transition: transform .12s linear; }

/* ---- compact sizes: head + ears only ---- */
:host([size="sm"]) .ground, :host([size="xs"]) .ground, :host([ground="none"]) .ground { display: none; }
:host([size="xs"]) .sheen, :host([size="xs"]) .waves, :host([size="xs"]) .sparkles, :host([size="xs"]) .seams,
:host([size="xs"]) .spark-lines, :host([size="xs"]) .ear-front path:last-child { display: none; }
:host([size="xs"]) .ex path { stroke-width: 8.5; }
:host([size="xs"]) .ex .ring { stroke-width: 6.5; }
:host([size="xs"]) .m { transform-box: fill-box; transform-origin: center; scale: 1.5; }
:host([size="sm"]) .ex path { stroke-width: 7.4; }

/* ---- motion (only when motion != off) ---- */
@keyframes bc-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }
@keyframes bc-float-sm { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
@keyframes bc-shadow { 0%, 100% { transform: scale(1); opacity: .5; } 50% { transform: scale(.82); opacity: .3; } }
@keyframes bc-breathe { 0%, 100% { opacity: calc(var(--bc-aura-o) * var(--glow-strength, 1)); } 50% { opacity: calc(var(--bc-aura-o) * var(--glow-strength, 1) + .18); } }
@keyframes bc-softpulse { 0%, 100% { opacity: calc(.2 + .12 * var(--glow-strength, 1)); } 50% { opacity: calc(.5 + .3 * var(--glow-strength, 1)); } }
@keyframes bc-pulse { 0% { transform: scale(1); } 45% { transform: scale(1.075); } 100% { transform: scale(1); } }
@keyframes bc-flash { 0% { stroke-width: 2.4; } 40% { stroke-width: 5; } 100% { stroke-width: 2.4; } }
@keyframes bc-sparkle { 0% { opacity: 0; transform: scale(0) rotate(0deg); } 35% { opacity: 1; transform: scale(1.1) rotate(30deg); } 100% { opacity: 0; transform: scale(.3) rotate(80deg); } }
@keyframes bc-spin { to { stroke-dashoffset: -80; } }
@keyframes bc-nod { 0%, 100% { transform: rotate(0); } 35% { transform: rotate(-5deg); } 70% { transform: rotate(3deg); } }
@keyframes bc-sway-l { 0%, 100% { transform: rotate(0deg); } 30% { transform: rotate(-3deg); } 62% { transform: rotate(2deg); } }
@keyframes bc-sway-r { 0%, 100% { transform: rotate(0deg); } 40% { transform: rotate(3.5deg); } 75% { transform: rotate(-1.5deg); } }
@keyframes bc-twitch { 0%, 88%, 100% { transform: rotate(0deg); } 92% { transform: rotate(-7deg); } 96% { transform: rotate(3deg); } }
@keyframes bc-spark { 0%, 100% { opacity: .35; } 50% { opacity: 1; } }

.bot { transform-box: view-box; transform-origin: 120px 140px; }
.bot-inner { transform-box: view-box; transform-origin: 120px 140px; }
.disc-shadow { transform-box: fill-box; transform-origin: center; }

:host(:not([motion="off"])) .bot { animation: bc-float var(--cycle-float, 4.2s) cubic-bezier(.45,0,.55,1) infinite; }
:host([state="sleeping"]:not([motion="off"])) .bot { animation-duration: 7s; }
:host([size="sm"]:not([motion="off"])) .bot { animation-name: bc-float-sm; }
:host([size="xs"]) .bot { animation: none; }
:host(:not([motion="off"])) .disc-shadow { animation: bc-shadow var(--cycle-float, 4.2s) cubic-bezier(.45,0,.55,1) infinite; }
:host([motion="full"]) .disc-ring3 { animation: bc-spin 6s linear infinite; }
:host([motion="full"]:not([size="xs"])) .ear-l .ear-sway { animation: bc-sway-l 5.3s ease-in-out infinite; }
:host([motion="full"]:not([size="xs"])) .ear-r .ear-sway { animation: bc-sway-r 4.1s ease-in-out infinite; }
:host([motion="full"][state="listening"]) .ear-r .ear-sway { animation: bc-twitch 3.2s ease-in-out infinite; }
:host([motion="full"][state="idle"]) .aura, :host([motion="full"][state="idle"]) .ear-aura { animation: bc-breathe var(--cycle-float, 4.2s) ease-in-out infinite; }
:host(:not([motion="off"])[data-expr="alert"]) .spark-lines path { animation: bc-spark 1.1s ease-in-out infinite; }
:host(:not([motion="off"])[state="needs-help"]) .aura,
:host(:not([motion="off"])[state="error"]) .aura, :host(:not([motion="off"])[state="needs-help"]) .ear-aura, :host(:not([motion="off"])[state="error"]) .ear-aura { animation: bc-softpulse var(--cycle-pulse, 2.6s) ease-in-out infinite; }
:host(:not([motion="off"])[pulse]) .bot-inner { animation: bc-pulse var(--dur-success, 350ms) cubic-bezier(.34,1.45,.64,1); }
:host(:not([motion="off"])[pulse]) .disc-ring { animation: bc-flash 600ms ease-out; }
:host(:not([motion="off"])[sparkle]) .sp { animation: bc-sparkle 900ms cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d); }
:host(:not([motion="off"])[nod]) .bot-inner { animation: bc-nod 420ms ease-in-out; }
:host([motion="low"]) .disc-ring3 { animation: none; }
:host([paused]) * { animation-play-state: paused !important; }
:host([motion="off"]) .face, :host([motion="off"]) .eyes, :host([motion="off"]) .ear-tilt { transition: none; }

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

/* ---- seasonal accessories (markup from seasons-fx.js, re-anchored onto the bunny crown) ---- */
.acc { pointer-events: none; }
:host([size="xs"]) .acc-body, :host([data-ops]) .acc-extra { display: none; }
:host([view="back"]) .acc-body { display: none; }
`;

class BusterCompanion extends HTMLElement {
  static get observedAttributes() { return ["state", "view", "size", "accent", "name", "message", "level", "season"]; }

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
    this._applyView();
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
    else if (name === "view") this._applyView();
    else if (name === "name") this._applyLabel();
    else if (name === "message") newV ? this.say(newV, { duration: 0 }) : this.hideBubble();
    else if (name === "level") this.level = Number(newV);
    else if (name === "season") this._applySeason();
  }

  /* ---------- public API ---------- */
  get state() { const s = this.getAttribute("state"); return STATES.includes(s) ? s : "idle"; }
  set state(v) { this.setAttribute("state", STATES.includes(v) ? v : "idle"); }

  get view() { const v = this.getAttribute("view"); return VIEWS.includes(v) ? v : "front"; }
  set view(v) { VIEWS.includes(v) && v !== "front" ? this.setAttribute("view", v) : this.removeAttribute("view"); }

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
    s.setProperty("--bc-tail", a.tail);
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
    // accessories are authored for the 240×240 space of the old helmet: re-anchor onto the bunny crown
    this._acc.setAttribute("transform", GEOMETRY.accHat);
    this._acc.querySelectorAll(".acc-body").forEach((el) => {
      el.setAttribute("transform", `${GEOMETRY.accBody} ${el.getAttribute("transform") || ""}`.trim());
    });
    const accent = this.getAttribute("accent");
    if (res?.eye && (!accent || accent === "cyan")) this.style.setProperty("--bc-eye-season", res.eye);
    else this.style.removeProperty("--bc-eye-season");
  }

  _applySize() {
    const compact = ["sm", "xs"].includes(this.getAttribute("size"));
    this._svg.setAttribute("viewBox", compact ? "24 6 192 192" : "0 0 240 240");
  }

  _applyView() {
    const L = VIEW_LAYOUT[this.view];
    const root = this.shadowRoot;
    root.querySelector(".view-face").setAttribute("transform", L.face);
    for (const side of ["l", "r"]) {
      const g = GEOMETRY[side === "l" ? "earL" : "earR"];
      const extra = side === "l" ? L.earL : L.earR;
      root.querySelector(`.ear-${side}`).setAttribute("transform", `${extra} translate(${g.x} ${g.y}) rotate(${g.rot})`.trim());
      root.querySelectorAll(`.pod-${side}`).forEach((el) => el.setAttribute("transform", side === "l" ? L.podL : L.podR));
    }
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
    if (AUDIO_STATES.has(st) && lvl !== "off") this._startSynth(); else this._stopSynth();
    if (AUDIO_STATES.has(st) && lvl === "off" && !this._externalAt) this.style.setProperty("--level", "0.45");
  }

  _startOrbit(lvl) {
    const n = lvl === "full" ? 4 : 3;
    if (!this._particles || this._particles.length !== n) {
      this._orbitBack.textContent = ""; this._orbitFront.textContent = "";
      const ns = "http://www.w3.org/2000/svg";
      const trail = document.createElementNS(ns, "ellipse");
      trail.setAttribute("class", "trail");
      trail.setAttribute("cx", "120"); trail.setAttribute("cy", "136");
      trail.setAttribute("rx", "96"); trail.setAttribute("ry", "30");
      trail.setAttribute("transform", "rotate(-12 120 136)");
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
      const x = 120 + x0 * cos - y0 * sin, y = 136 + x0 * sin + y0 * cos;
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
    if (st === "thinking" || st === "needs-help" || st === "error" || st === "sleeping") return;
    const r = this.getBoundingClientRect();
    if (!r.width || r.bottom < 0 || r.top > innerHeight) return;
    const dx = pointer.x - (r.left + r.width / 2);
    const dy = pointer.y - (r.top + r.height * 0.58);
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
      if (Motion.active && !["thinking", "sleep"].includes(this.dataset.expr)) {
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
