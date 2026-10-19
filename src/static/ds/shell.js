/*!
 * Buster Design System — shell.js
 * Small, framework-free behaviours for server-rendered pages (safe with HTMX swaps):
 *   setMode("companion"|"operations"), toast({...}), openPanel/closePanel/togglePanel,
 *   segmented-control keyboard + selection, sidebar drawer toggle, ⌘K / Ctrl+K search focus.
 * Everything is delegated on document, so swapped-in markup just works.
 */
import { icon } from "./icons.js";

const root = document.documentElement;
const MODE_KEY = "buster-ds:mode";

/* ---------------- mode ---------------- */
export function getMode() { return root.dataset.mode === "operations" ? "operations" : "companion"; }
export function setMode(mode, { persist = true } = {}) {
  const m = mode === "operations" ? "operations" : "companion";
  root.dataset.mode = m;
  if (persist) { try { localStorage.setItem(MODE_KEY, m); } catch { /* ignore */ } }
  document.dispatchEvent(new CustomEvent("buster:mode", { detail: { mode: m } }));
  document.querySelectorAll("[data-bds-mode-toggle]").forEach((b) => b.setAttribute("aria-pressed", String(m === "operations")));
  return m;
}
/** Restore a saved mode unless the server already set data-mode explicitly. */
export function restoreMode() {
  if (root.hasAttribute("data-mode") && !root.hasAttribute("data-mode-auto")) return getMode();
  try { const m = localStorage.getItem(MODE_KEY); if (m) return setMode(m, { persist: false }); } catch { /* ignore */ }
  return getMode();
}

/* ---------------- toasts ---------------- */
function toastRegion() {
  let r = document.querySelector(".bds-toast-region");
  if (!r) {
    r = document.createElement("div");
    r.className = "bds-toast-region";
    r.setAttribute("role", "region");
    r.setAttribute("aria-label", "Notifications");
    document.body.appendChild(r);
  }
  return r;
}

/**
 * toast({ title, body, tone: "ok"|"info"|"warn"|"error", icon, duration, action: { label, onClick } })
 * Returns { close() }.
 */
export function toast(opts = {}) {
  const { title = "", body = "", tone = "info", duration = 5000, action } = typeof opts === "string" ? { title: opts } : opts;
  const ico = opts.icon || { ok: "check", info: "info", warn: "alert", error: "alert" }[tone] || "info";
  const el = document.createElement("div");
  el.className = `bds-toast bds-toast--${tone}`;
  el.setAttribute("role", tone === "error" || tone === "warn" ? "alert" : "status");
  el.innerHTML = `<span class="bds-toast__icon">${icon(ico, { size: 16 })}</span>
    <div class="bds-toast__text"><div class="bds-toast__title"></div><div class="bds-toast__body"></div></div>
    <button class="bds-iconbtn bds-iconbtn--sm" type="button" aria-label="Dismiss">${icon("close", { size: 14 })}</button>`;
  el.querySelector(".bds-toast__title").textContent = title;
  const b = el.querySelector(".bds-toast__body");
  if (body) b.textContent = body; else b.remove();
  if (action) {
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "bds-btn bds-btn--ghost bds-btn--sm"; btn.textContent = action.label;
    btn.addEventListener("click", () => { action.onClick?.(); close(); });
    el.querySelector(".bds-toast__text").appendChild(btn);
  }
  let timer;
  const close = () => {
    clearTimeout(timer);
    el.classList.add("is-leaving");
    const done = () => el.remove();
    el.addEventListener("animationend", done, { once: true });
    setTimeout(done, 400);
  };
  el.querySelector("button[aria-label='Dismiss']").addEventListener("click", close);
  el.addEventListener("mouseenter", () => clearTimeout(timer));
  el.addEventListener("mouseleave", () => { if (duration) timer = setTimeout(close, duration); });
  toastRegion().appendChild(el);
  if (duration) timer = setTimeout(close, duration);
  return { el, close };
}

/* ---------------- panels (220–280ms spring) ---------------- */
export function openPanel(panel) {
  const p = typeof panel === "string" ? document.querySelector(panel) : panel;
  if (!p) return;
  p._returnFocus = document.activeElement;
  p.hidden = false;
  requestAnimationFrame(() => {
    p.dataset.state = "open";
    p.querySelector("[autofocus], button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")?.focus({ preventScroll: true });
  });
}
export function closePanel(panel) {
  const p = typeof panel === "string" ? document.querySelector(panel) : panel;
  if (!p || p.dataset.state !== "open") return;
  p.dataset.state = "closed";
  const fin = () => { if (p.dataset.state === "closed") p.hidden = true; };
  p.addEventListener("transitionend", fin, { once: true });
  setTimeout(fin, 400);
  p._returnFocus?.focus?.({ preventScroll: true });
}
export function togglePanel(panel) {
  const p = typeof panel === "string" ? document.querySelector(panel) : panel;
  if (p) (p.dataset.state === "open" ? closePanel : openPanel)(p);
}

/* ---------------- delegated behaviours ---------------- */
function segSelect(btn) {
  const seg = btn.closest(".bds-seg");
  if (!seg) return;
  seg.querySelectorAll("[role='radio']").forEach((b) => {
    const on = b === btn;
    b.setAttribute("aria-checked", String(on));
    b.tabIndex = on ? 0 : -1;
  });
  seg.dispatchEvent(new CustomEvent("bds-change", { bubbles: true, detail: { value: btn.value || btn.dataset.value || btn.textContent.trim() } }));
}

function init() {
  document.addEventListener("click", (e) => {
    const t = e.target.closest?.("[data-bds-toggle], [data-bds-open], [data-bds-close], [data-bds-mode-toggle], .bds-seg [role='radio']");
    if (!t) return;
    if (t.matches(".bds-seg [role='radio']")) return segSelect(t);
    if (t.hasAttribute("data-bds-mode-toggle")) return setMode(getMode() === "operations" ? "companion" : "operations");
    if (t.dataset.bdsToggle === "sidebar") {
      const app = t.closest(".bds-app") || document.querySelector(".bds-app");
      const open = !app.hasAttribute("data-sidebar-open");
      app.toggleAttribute("data-sidebar-open", open);
      t.setAttribute("aria-expanded", String(open));
      return;
    }
    if (t.dataset.bdsOpen) return openPanel(t.dataset.bdsOpen);
    if (t.dataset.bdsClose !== undefined) return closePanel(t.dataset.bdsClose || t.closest(".bds-panel"));
    if (t.dataset.bdsToggle) return togglePanel(t.dataset.bdsToggle);
  });

  document.addEventListener("keydown", (e) => {
    // ⌘K / Ctrl+K focuses the first search field
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      const s = document.querySelector("[data-bds-search], .bds-search input");
      if (s) { e.preventDefault(); s.focus(); s.select?.(); }
    }
    if (e.key === "Escape") {
      const open = [...document.querySelectorAll(".bds-panel[data-state='open']")].pop();
      if (open) closePanel(open);
      const app = document.querySelector(".bds-app[data-sidebar-open]");
      if (app) app.removeAttribute("data-sidebar-open");
    }
    // arrow keys inside segmented controls (roving tabindex)
    const r = e.target.closest?.(".bds-seg [role='radio']");
    if (r && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) {
      const items = [...r.closest(".bds-seg").querySelectorAll("[role='radio']:not([disabled])")];
      let i = items.indexOf(r);
      if (e.key === "Home") i = 0; else if (e.key === "End") i = items.length - 1;
      else i = (i + (e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 1) + items.length) % items.length;
      e.preventDefault();
      items[i].focus();
      segSelect(items[i]);
    }
  });

  // initialise roving tabindex for segmented controls (and after HTMX swaps)
  const initSegs = (scope = document) => scope.querySelectorAll(".bds-seg").forEach((seg) => {
    const items = [...seg.querySelectorAll("[role='radio']")];
    const cur = items.find((b) => b.getAttribute("aria-checked") === "true") || items[0];
    items.forEach((b) => { b.tabIndex = b === cur ? 0 : -1; });
  });
  initSegs();
  document.addEventListener("htmx:afterSwap", (e) => initSegs(e.target));
  restoreMode();
}

if (!window.__busterShell) {
  window.__busterShell = true;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
}
