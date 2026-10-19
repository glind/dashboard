/*!
 * Buster Design System — buster.js (entry point)
 *   <script type="module" src="/static/ds/buster.js"></script>
 * Registers every custom element and exposes window.BusterDS for inline handlers (hx-on, SSE).
 */
import { Motion } from "./motion.js";
import { icon, icons } from "./icons.js";
import "./background.js";
import { STATES, VIEWS, ACCENTS } from "./companion.js";
import "./waveform.js";
import "./network-universe.js";
import { smoothPath } from "./area-chart.js";
import { BusterSeasons, seasonFor, resolveSeason } from "./seasons.js";
import { toast, setMode, getMode, openPanel, closePanel, togglePanel } from "./shell.js";

/** Find a companion: BusterDS.companion() → first <buster-companion>, or by selector. */
function companion(sel) {
  return typeof sel === "string" ? document.querySelector(sel) : sel || document.querySelector("buster-companion[data-primary], buster-companion");
}

/**
 * Apply a server event to the UI. Accepts the JSON your SSE/HTMX trigger sends:
 *   { state: "thinking", say: "On it…", celebrate: true, toast: { title, tone }, target: "#buster" }
 */
function apply(evt = {}) {
  const c = companion(evt.target);
  if (c) {
    if (evt.state) c.state = evt.state;
    if (evt.say) c.say(evt.say, { duration: evt.duration ?? 4500 });
    if (evt.celebrate) c.celebrate();
    if (evt.react) c.react(evt.react);
    if (typeof evt.level === "number") c.level = evt.level;
  }
  if (evt.toast) toast(evt.toast);
  if (evt.mode) setMode(evt.mode);
  if (evt.season) BusterSeasons.set(evt.season);
}

const BusterDS = { Motion, icon, icons, toast, setMode, getMode, openPanel, closePanel, togglePanel, companion, apply, STATES, VIEWS, ACCENTS, smoothPath, seasons: BusterSeasons, seasonFor, resolveSeason, version: "0.1.0" };
window.BusterDS = BusterDS;

// HTMX integration: a response header `HX-Trigger: {"buster": {"state": "success", "say": "Done!"}}`
document.addEventListener("buster", (e) => apply(e.detail || {}));

export { BusterDS };
export default BusterDS;
