/*!
 * Buster Design System — seasons.js
 * Seasonal theme layer shared by every product. Sets <html data-season="none|halloween|thanksgiving|winter"
 * data-season-variant="newyear"?> from date windows, with manual overrides. Seasonal decorations
 * (backdrop particles + companion accessories) are lazy-loaded from seasons-fx.js only when a season is active.
 *
 *   BusterSeasons.configure({ windows: [...], enabled: true })
 *   BusterSeasons.set("halloween" | "thanksgiving" | "winter" | "newyear" | "none" | "auto")   // persisted
 *   BusterSeasons.current      -> { season, variant, source }
 *   seasonFor(date, windows)   -> "halloween" | ... | "none"            (pure)
 *   resolveSeason(date, windows) -> { season, variant }                 (pure)
 *   ?season=winter  in the URL overrides everything (not persisted).
 *   Server-forced: <html data-season="winter" data-season-lock>  (ignores user/query overrides).
 *
 * Window format (identical in seasons.json and python/buster_seasons.py):
 *   { "season": "winter", "variant": "newyear"?, "start": "MM-DD", "end": "MM-DD" }
 *   Inclusive on both ends. If end < start the window wraps over New Year. First match wins.
 */

export const SEASONS = ["none", "halloween", "thanksgiving", "winter"];
export const DEFAULT_WINDOWS = [
  { season: "winter", variant: "newyear", start: "12-31", end: "01-01" },
  { season: "halloween", start: "10-01", end: "11-01" },
  { season: "thanksgiving", start: "11-02", end: "11-30" },
  { season: "winter", start: "12-01", end: "01-06" },
];

const STORE_KEY = "buster-ds:season";
const root = document.documentElement;

const md = (s) => {
  const [m, d] = String(s).split("-").map(Number);
  return m * 100 + d; // MMDD as an integer, e.g. 1031
};

/** Pure: which window (if any) contains `date`? Returns { season, variant } ("none" if no match). */
export function resolveSeason(date = new Date(), windows = DEFAULT_WINDOWS) {
  const d = date instanceof Date ? date : new Date(date);
  const today = (d.getMonth() + 1) * 100 + d.getDate();
  for (const w of windows || []) {
    const a = md(w.start), b = md(w.end);
    const hit = a <= b ? today >= a && today <= b : today >= a || today <= b; // wrap over New Year
    if (hit && SEASONS.includes(w.season)) return { season: w.season, variant: w.variant || "" };
  }
  return { season: "none", variant: "" };
}

/** Pure: season name for a date (variant ignored). */
export function seasonFor(date = new Date(), windows = DEFAULT_WINDOWS) {
  return resolveSeason(date, windows).season;
}

const cfg = { windows: DEFAULT_WINDOWS, enabled: true };
const serverSeason = root.dataset.season || null;
const serverVariant = root.dataset.seasonVariant || "";
const locked = root.hasAttribute("data-season-lock");
let current = { season: "none", variant: "", source: "default" };
let fxPromise = null;

function parseChoice(v) {
  if (!v) return null;
  if (v === "auto") return "auto";
  if (v === "newyear") return { season: "winter", variant: "newyear" };
  if (SEASONS.includes(v)) return { season: v, variant: "" };
  return null;
}

function compute() {
  if (locked && serverSeason) return { season: serverSeason, variant: serverVariant, source: "server-lock" };
  const q = parseChoice(new URLSearchParams(location.search).get("season"));
  if (q && q !== "auto") return { ...q, source: "query" };
  let stored = null;
  try { stored = parseChoice(localStorage.getItem(STORE_KEY)); } catch { /* storage blocked */ }
  if (stored && stored !== "auto") return { ...stored, source: "user" };
  if (!cfg.enabled) return { season: "none", variant: "", source: "disabled" };
  if (serverSeason) return { season: serverSeason, variant: serverVariant, source: "server" };
  return { ...resolveSeason(new Date(), cfg.windows), source: "calendar" };
}

function apply() {
  const next = compute();
  const changed = next.season !== current.season || next.variant !== current.variant;
  current = next;
  root.dataset.season = next.season;
  if (next.variant) root.dataset.seasonVariant = next.variant; else delete root.dataset.seasonVariant;
  if (next.season !== "none") loadFx();
  if (changed) document.dispatchEvent(new CustomEvent("buster:season", { detail: { ...current } }));
  return current;
}

/** Lazy-load decorations (backdrop particles + companion accessories). */
function loadFx() {
  if (!fxPromise) {
    fxPromise = import(new URL("./seasons-fx.js", import.meta.url).href)
      .then((m) => { m.install?.(api); document.dispatchEvent(new CustomEvent("buster:season-fx")); return m; })
      .catch((err) => { console.warn("[buster seasons] decorations unavailable", err); fxPromise = null; });
  }
  return fxPromise;
}

const api = {
  SEASONS, DEFAULT_WINDOWS, seasonFor, resolveSeason,
  get current() { return { ...current }; },
  get windows() { return cfg.windows.slice(); },
  /** Replace the calendar and/or disable automatic seasons. */
  configure({ windows, enabled } = {}) {
    if (Array.isArray(windows)) cfg.windows = windows;
    if (typeof enabled === "boolean") cfg.enabled = enabled;
    return apply();
  },
  /** Manual override, persisted per browser. "auto" returns to the calendar; "none" opts out. */
  set(choice) {
    try {
      if (!choice || choice === "auto") localStorage.removeItem(STORE_KEY);
      else localStorage.setItem(STORE_KEY, choice);
    } catch { /* ignore */ }
    return apply();
  },
  /** Companion accessory renderer — provided by seasons-fx.js once loaded. */
  accessory: null,
  load: loadFx,
};

if (!window.BusterSeasons) {
  window.BusterSeasons = api;
  // A server-rendered page can pass a calendar: <script type="application/json" id="buster-seasons">{"windows":[...]}</script>
  const inline = document.getElementById("buster-seasons");
  if (inline) { try { const j = JSON.parse(inline.textContent); if (j.windows) cfg.windows = j.windows; if (j.enabled === false) cfg.enabled = false; } catch (e) { console.warn("[buster seasons] bad JSON", e); } }
  apply();
  // re-check at midnight-ish (long-running dashboards)
  setInterval(() => apply(), 30 * 60 * 1000);
}

export const BusterSeasons = window.BusterSeasons;
export default BusterSeasons;
