/*!
 * Buster Design System — motion.js
 * One shared adaptive-motion controller consulted by every animated component.
 *
 *   level: "full" | "low" | "off"     (exposed as <html data-motion="...">)
 *   paused: true while the tab is hidden (exposed as <html data-motion-paused>)
 *
 * Inputs (most restrictive wins):
 *   - prefers-reduced-motion: reduce          -> off
 *   - user override  Motion.set("full"|"low"|"off"|"auto")  (persisted per browser)
 *   - operations mode  (<html|body data-mode="operations">) -> low
 *   - on battery (navigator.getBattery, discharging)          -> low
 *   - measured frame rate drops (rAF timing)                  -> low, then off
 *
 * Event: document dispatches "buster:motion" { detail: { level, paused, reason } }.
 * Shared ticker: Motion.onFrame(fn, { fps }) -> unsubscribe. Runs only while
 * level !== "off" and the page is visible. fn(now, dt).
 */

const LEVELS = ["off", "low", "full"];
const STORE_KEY = "buster-ds:motion";
const root = document.documentElement;

const rank = (l) => LEVELS.indexOf(l);
const minLevel = (...ls) => ls.reduce((a, b) => (rank(b) < rank(a) ? b : a), "full");

const state = {
  override: "auto",
  reduced: false,
  ops: false,
  battery: false,
  perf: "full",       // degraded by the frame-rate sampler
  level: "full",
  paused: false,
  reason: "default",
};

const listeners = new Set();
const frameSubs = new Set();
let rafId = 0;
let lastNow = 0;

// ---- frame-rate sampler --------------------------------------------------
const sampler = { start: 0, frames: 0, slowWindows: 0, skip: 2 };
const SAMPLE_MS = 2000;

function sample(now) {
  if (!sampler.start) { sampler.start = now; sampler.frames = 0; return; }
  sampler.frames++;
  const elapsed = now - sampler.start;
  if (elapsed < SAMPLE_MS) return;
  const fps = (sampler.frames * 1000) / elapsed;
  sampler.start = now; sampler.frames = 0;
  if (sampler.skip > 0) { sampler.skip--; return; } // ignore warm-up windows
  const threshold = state.perf === "full" ? 40 : 22;
  if (fps < threshold) sampler.slowWindows++;
  else sampler.slowWindows = 0;
  if (sampler.slowWindows >= 2) {
    sampler.slowWindows = 0;
    state.perf = state.perf === "full" ? "low" : "off";
    recompute(`low frame rate (${fps.toFixed(0)} fps)`);
  }
}

// ---- shared ticker -------------------------------------------------------
function tick(now) {
  rafId = 0;
  if (!running()) return;
  const dt = lastNow ? Math.min(now - lastNow, 100) : 16;
  lastNow = now;
  sample(now);
  for (const sub of frameSubs) {
    if (sub.interval && now - sub.last < sub.interval) continue;
    const sdt = sub.last ? now - sub.last : dt;
    sub.last = now;
    try { sub.fn(now, sdt); } catch (err) { console.error("[buster motion]", err); }
  }
  rafId = requestAnimationFrame(tick);
}

function running() {
  return frameSubs.size > 0 && state.level !== "off" && !state.paused;
}

function ensureLoop() {
  if (running()) {
    if (!rafId) { lastNow = 0; sampler.start = 0; rafId = requestAnimationFrame(tick); }
  } else if (rafId) {
    cancelAnimationFrame(rafId); rafId = 0;
  }
}

// ---- level computation ---------------------------------------------------
function recompute(reason) {
  let level;
  let why = reason || state.reason;
  if (state.reduced) { level = "off"; why = "prefers-reduced-motion"; }
  else if (state.override !== "auto") { level = state.override; why = "user override"; }
  else {
    level = minLevel(
      "full",
      state.ops ? "low" : "full",
      state.battery ? "low" : "full",
      state.perf
    );
    if (level !== "full" && !reason) {
      why = state.ops ? "operations mode" : state.battery ? "on battery" : "performance";
    }
  }
  const paused = document.hidden;
  const changed = level !== state.level || paused !== state.paused;
  state.level = level; state.paused = paused; state.reason = why;
  root.dataset.motion = level;
  if (paused) root.dataset.motionPaused = ""; else delete root.dataset.motionPaused;
  ensureLoop();
  if (changed) {
    const detail = { level, paused, reason: why };
    for (const fn of listeners) { try { fn(detail); } catch (e) { console.error(e); } }
    document.dispatchEvent(new CustomEvent("buster:motion", { detail }));
  }
}

function readMode() {
  const m = root.dataset.mode || document.body?.dataset.mode || "companion";
  return m === "operations";
}

// ---- init ----------------------------------------------------------------
function init() {
  try { state.override = localStorage.getItem(STORE_KEY) || "auto"; } catch { /* storage blocked */ }
  if (!["auto", ...LEVELS].includes(state.override)) state.override = "auto";

  const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  if (mq) {
    state.reduced = mq.matches;
    mq.addEventListener?.("change", (e) => { state.reduced = e.matches; recompute(); });
  }

  state.ops = readMode();
  const mo = new MutationObserver(() => {
    const ops = readMode();
    if (ops !== state.ops) {
      state.ops = ops;
      // Re-arm the perf sampler when the user returns to companion mode.
      if (!ops) { state.perf = "full"; sampler.skip = 2; }
      recompute();
    }
  });
  mo.observe(root, { attributes: true, attributeFilter: ["data-mode"] });
  const watchBody = () => document.body && mo.observe(document.body, { attributes: true, attributeFilter: ["data-mode"] });
  if (document.body) watchBody(); else document.addEventListener("DOMContentLoaded", () => { watchBody(); state.ops = readMode(); recompute(); }, { once: true });

  document.addEventListener("visibilitychange", () => recompute());

  if (navigator.getBattery) {
    navigator.getBattery().then((b) => {
      const upd = () => { state.battery = !b.charging; recompute(); };
      b.addEventListener("chargingchange", upd);
      upd();
    }).catch(() => {});
  }
  recompute("initial");
}

export const Motion = {
  get level() { return state.level; },
  get paused() { return state.paused; },
  get reason() { return state.reason; },
  get override() { return state.override; },
  /** true when decorative motion should run right now */
  get active() { return state.level !== "off" && !state.paused; },

  /** Force a level ("full" | "low" | "off") or "auto". Persisted per browser. */
  set(level) {
    state.override = ["auto", ...LEVELS].includes(level) ? level : "auto";
    try { localStorage.setItem(STORE_KEY, state.override); } catch { /* ignore */ }
    if (state.override === "auto") { state.perf = "full"; sampler.skip = 2; sampler.slowWindows = 0; }
    recompute("user override");
  },

  /** Subscribe to level/paused changes. Called immediately. Returns unsubscribe. */
  subscribe(fn) {
    listeners.add(fn);
    fn({ level: state.level, paused: state.paused, reason: state.reason });
    return () => listeners.delete(fn);
  },

  /** Shared rAF ticker. opts.fps throttles this subscriber. Returns unsubscribe. */
  onFrame(fn, opts = {}) {
    const sub = { fn, last: 0, interval: opts.fps ? 1000 / opts.fps : 0 };
    frameSubs.add(sub);
    ensureLoop();
    return () => { frameSubs.delete(sub); ensureLoop(); };
  },

  /** Utility: pick a value per level, e.g. Motion.pick({ full: 120, low: 40, off: 0 }) */
  pick(map) { return map[state.level] ?? map.full; },
};

/**
 * Mixin helper for custom elements: reflects motion level onto the host as
 * attributes `motion="full|low|off"` and `paused`, and calls host.onMotion(detail).
 */
export function bindMotion(host) {
  return Motion.subscribe((d) => {
    host.setAttribute("motion", d.level);
    host.toggleAttribute("paused", d.paused);
    host.onMotion?.(d);
  });
}

if (!window.BusterMotion) {
  init();
  window.BusterMotion = Motion;
}

export default Motion;
