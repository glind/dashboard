/*!
 * Dashboard theme layer (family + modern UI).
 *
 * Loaded as a classic script at the top of <head> in both dashboard templates, right after
 * the server-rendered window.__DASH_THEME__ block (src/config/theme.py).
 *
 *  - Cosmic is the only theme: <html data-theme="cosmic"> before first paint, in both UIs.
 *    Old per-browser picks of removed themes/skins (localStorage dashboard_skin = roger, dracula,
 *    alice, jedi...; dashboard_modern_theme = classic) are migrated to "cosmic" at load.
 *  - Loads the Buster design system runtime (ds/buster.js: <buster-space>,
 *    <buster-companion>, motion controller, seasonal decorations), adds the cosmic backdrop,
 *    the greeting hero and the companion, and lets the companion react to dashboard events.
 *  - Seasons (holiday variants of Cosmic): the server renders data-season(+variant) on <html>
 *    with data-season-lock; ds/seasons.js draws the decorations.
 *
 * Public API: window.DashTheme
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var cfg = window.__DASH_THEME__ || {};
  var ui = cfg.ui || root.getAttribute("data-ui") || (document.getElementById("skin-css") ? "family" : "modern");
  root.setAttribute("data-ui", ui);

  function read(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function store(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* storage blocked */ } }

  // ---- Cosmic is the only theme: migrate stored picks of removed themes/skins ----
  var THEME = "cosmic";
  if (read("dashboard_skin") !== THEME) store("dashboard_skin", THEME);
  if (read("dashboard_modern_theme") !== THEME) store("dashboard_modern_theme", THEME);
  if (cfg.requestedDensity) store("dashboard_density", cfg.requestedDensity);

  var cosmic = true;
  root.setAttribute("data-theme", THEME);

  var season = (cfg.season && cfg.season.season) || root.getAttribute("data-season") || "none";
  var variant = (cfg.season && cfg.season.variant) || root.getAttribute("data-season-variant") || "";

  function density() { return read("dashboard_density") === "operations" ? "operations" : "companion"; }
  {
    root.setAttribute("data-mode", density());
    root.classList.add("bds-themed");
    // Registers <buster-space>, <buster-companion>, <buster-icon>, motion + seasons (lazy fx).
    import("/static/ds/buster.js").catch(function (e) { console.warn("[theme] design system failed to load", e); });
  }

  // ------------------------------------------------------------------ helpers
  var SEASON_TEXT = {
    halloween: { title: "Happy Halloween", emoji: "🎃", line: "Spooky season is here" },
    thanksgiving: { title: "Happy Thanksgiving", emoji: "🍂", line: "Harvest season" },
    winter: { title: "Happy Holidays", emoji: "❄️", line: "Cozy winter days" },
    newyear: { title: "Happy New Year", emoji: "🎉", line: "A brand-new year" },
  };
  function seasonKey() { return season === "winter" && variant === "newyear" ? "newyear" : season; }
  function seasonInfo() { return SEASON_TEXT[seasonKey()] || null; }

  function h(tag, attrs, html) {
    var el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (html != null) el.innerHTML = html;
    return el;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function greeting(d) {
    var hr = (d || new Date()).getHours();
    return hr < 5 ? "Good night" : hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";
  }
  function today() {
    try { return new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }); }
    catch (e) { return new Date().toDateString(); }
  }

  // ------------------------------------------------------------ companion API
  var companionCfg = { name: "Buster", accent: "violet", hero_size: "md", sidebar_size: "sm" };
  function companions() { return Array.prototype.slice.call(document.querySelectorAll("buster-companion[data-dash]")); }
  function primary() { return document.querySelector("buster-companion[data-dash][data-primary]") || companions()[0] || null; }
  var restState = "idle";
  var pending = 0;
  var helpTimer = null;

  function setState(state) {
    companions().forEach(function (c) { try { c.state = state; } catch (e) { c.setAttribute("state", state); } });
  }
  function setRest(state) {
    restState = state;
    companions().forEach(function (c) { c.setAttribute("rest", state); });
    if (!pending) setState(state);
  }
  function say(text, ms) {
    var c = primary();
    if (c && typeof c.say === "function" && text) c.say(String(text).slice(0, 160), { duration: ms == null ? 4500 : ms });
  }
  function celebrate(text) {
    companions().forEach(function (c) { if (typeof c.celebrate === "function") c.celebrate(); else c.setAttribute("state", "success"); });
    if (text) say(text, 2800);
  }
  function startThinking() {
    pending += 1;
    clearTimeout(helpTimer);
    setState("thinking");
  }
  function stopThinking(ok, text) {
    pending = Math.max(0, pending - 1);
    if (pending) return;
    if (ok) {
      setState("success");
      if (text) say(text, 5000);
    } else {
      setState("needs-help");
      say("Hmm, that didn't work. Want to try again?", 3500);
      helpTimer = setTimeout(function () { if (!pending) setState(restState); }, 3800);
    }
  }

  // Companion reactions from dashboard traffic (cheap: no changes to the UIs' own code paths)
  function classify(url, method, body) {
    var path = String(url || "").replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    if (method === "POST" && /^\/api\/(ai\/chat|assistant\/chat|chat)\b/.test(path)) return "think";
    if (method === "POST" && path === "/api/voice/speak") return "speak";
    if (method === "POST" && path === "/api/voice/settings" && /wake_word_enabled/.test(body)) return "wake";
    if ((method === "PUT" || method === "PATCH" || method === "POST") && /^\/api\/tasks\/[^/]+(\/status|\/complete)?$/.test(path)) {
      if (/"(status)"\s*:\s*"(completed|done)"|"completed"\s*:\s*true/.test(body) || /\/complete$/.test(path)) return "task-done";
    }
    return null;
  }
  function parse(body) { try { return JSON.parse(body); } catch (e) { return {}; } }

  function wrapFetch() {
    if (!window.fetch || window.fetch.__dashTheme) return;
    var orig = window.fetch;
    var wrapped = function (input, init) {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      var method = String((init && init.method) || (input && input.method) || "GET").toUpperCase();
      var body = init && typeof init.body === "string" ? init.body : "";
      var kind = null;
      try { kind = classify(url, method, body); } catch (e) { kind = null; }
      if (kind === "think" || kind === "speak") startThinking();
      var p = orig.apply(this, arguments);
      if (!kind) return p;
      return p.then(function (res) {
        try {
          if (kind === "think") stopThinking(res.ok);
          else if (kind === "speak") stopThinking(res.ok, parse(body).text);
          else if (kind === "task-done" && res.ok) celebrate("Nice work! Task done ✨");
          else if (kind === "wake" && res.ok) setRest(parse(body).wake_word_enabled ? "listening" : "idle");
        } catch (e) { /* never break the app */ }
        return res;
      }, function (err) {
        if (kind === "think" || kind === "speak") stopThinking(false);
        throw err;
      });
    };
    wrapped.__dashTheme = true;
    window.fetch = wrapped;
  }

  // ------------------------------------------------------------- cosmic UI
  function companionEl(opts) {
    var el = document.createElement("buster-companion");
    el.setAttribute("data-dash", "");
    el.setAttribute("size", opts.size || "md");
    el.setAttribute("accent", companionCfg.accent || "violet");
    el.setAttribute("name", companionCfg.name || "Buster");
    el.setAttribute("rest", restState);
    if (opts.primary) el.setAttribute("data-primary", "");
    if (opts.message) el.setAttribute("message", opts.message);
    if (opts.noFollow) el.setAttribute("no-follow", "");
    if (opts.ground) el.setAttribute("ground", opts.ground);
    if (opts.bubble) el.setAttribute("bubble", opts.bubble);
    if (opts.hidden) el.setAttribute("aria-hidden", "true");
    return el;
  }

  function heroSub() {
    var info = seasonInfo();
    var bits = ["<span>" + esc(today()) + "</span>"];
    if (info) bits.push("<strong>" + esc(info.title) + "</strong> " + info.emoji);
    else bits.push("Everything's <strong>cozy</strong> on board.");
    return bits.join(" &middot; ");
  }

  function chip(label, icon, accent, onclick) {
    var b = h("button", { type: "button", class: "bds-chip bds-chip--lg", "data-accent": accent }, '<buster-icon name="' + icon + '"></buster-icon>' + esc(label));
    b.addEventListener("click", onclick);
    return b;
  }
  function go(section) { return function () { if (typeof window.showSection === "function") window.showSection(section); }; }
  function scrollToWidget(id) {
    return function () {
      var el = document.querySelector('[data-widget="' + id + '"]');
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    };
  }

  function buildHero(actions, message) {
    var hero = h("section", { class: "bds-hero dash-hero", id: "dash-hero", "aria-labelledby": "dash-greeting" });
    var text = h("div", { class: "bds-hero__text" });
    text.appendChild(h("h1", { class: "bds-hero__title", id: "dash-greeting" }, esc(greeting())));
    text.appendChild(h("p", { class: "bds-hero__sub", id: "dash-hero-sub" }, heroSub()));
    var act = h("div", { class: "bds-hero__actions" });
    actions.forEach(function (a) { act.appendChild(chip(a[0], a[1], a[2], a[3])); });
    text.appendChild(act);
    var stage = h("div", { class: "bds-hero__stage" });
    stage.appendChild(companionEl({ size: companionCfg.hero_size || "md", primary: true, message: message, bubble: "right" }));
    hero.appendChild(text);
    hero.appendChild(stage);
    setInterval(function () { var g = document.getElementById("dash-greeting"); if (g) g.textContent = greeting(); }, 5 * 60 * 1000);
    return hero;
  }

  function heroMessage() {
    var info = seasonInfo();
    var name = companionCfg.name || "Buster";
    if (info) return info.emoji + " " + info.title + "! I'm " + name + ".";
    return "Hey! 👋 I'm " + name + ". What are we doing today?";
  }

  function mountFamily() {
    // Sidebar: companion brand instead of the GIF avatar
    var avatar = document.getElementById("assistant-avatar");
    var wrap = avatar && avatar.closest(".group");
    if (wrap && !document.getElementById("dash-brand")) {
      var brand = h("div", { class: "bds-brand dash-brand", id: "dash-brand" });
      brand.appendChild(companionEl({ size: companionCfg.sidebar_size || "sm", noFollow: true, hidden: true }));
      brand.appendChild(h("div", null, '<b id="dash-brand-name">' + esc(companionCfg.name) + '</b><small id="dash-brand-tag">Always here for you</small>'));
      wrap.parentNode.insertBefore(brand, wrap);
    }
    // Overview: greeting hero
    var overview = document.getElementById("section-overview");
    if (overview && !document.getElementById("dash-hero")) {
      var ask = function () { if (typeof window.promptSpeak === "function") window.promptSpeak(); };
      overview.insertBefore(buildHero([
        ["Weather", "sun", "cyan", scrollToWidget("weather")],
        ["Comics", "sparkle", "orange", scrollToWidget("comics")],
        ["Tasks", "check", "green", go("tasks")],
        ["Calendar", "calendar", "blue", go("calendar")],
        ["Ask " + (companionCfg.name || "Buster"), "chat", "violet", ask],
      ], heroMessage()), overview.firstChild);
    }
    // Wake word already on? Show the listening state.
    fetch("/api/voice/settings").then(function (r) { return r.ok ? r.json() : {}; }).then(function (d) {
      if (d && d.voice && d.voice.wake_word_enabled) setRest("listening");
    }).catch(function () {});
  }

  function mountModern() {
    // Sidebar brand: small companion next to the title
    var logo = document.querySelector('aside img[alt="Buildly Logo"]');
    if (logo && !logo.dataset.dashSwapped) {
      logo.dataset.dashSwapped = "1";
      var holder = h("span", { class: "dash-logo-companion" });
      holder.appendChild(companionEl({ size: "xs", noFollow: true, hidden: true }));
      logo.parentNode.insertBefore(holder, logo);
    }
    var overview = document.querySelector("#section-overview > div") || document.getElementById("section-overview");
    if (overview && !document.getElementById("dash-hero")) {
      var title = overview.querySelector(":scope > h2");
      var hero = buildHero([
        ["Email", "mail", "pink", go("emails")],
        ["Calendar", "calendar", "blue", go("calendar")],
        ["Tasks", "check", "green", go("todos")],
        ["News", "list", "amber", go("news")],
        ["Ask AI", "chat", "violet", go("ai")],
      ], heroMessage());
      if (title) { title.classList.add("dash-replaced-title"); title.parentNode.insertBefore(hero, title); }
      else overview.insertBefore(hero, overview.firstChild);
    }
    // AI chat card: a companion that watches the conversation
    var chat = document.getElementById("ai-chat-messages");
    var card = chat && chat.parentElement;
    if (card && !card.querySelector("buster-companion")) {
      var head = card.querySelector("h3");
      if (head) {
        var row = h("div", { class: "dash-chat-head" });
        head.parentNode.insertBefore(row, head);
        row.appendChild(companionEl({ size: "xs", hidden: true }));
        row.appendChild(head);
      }
    }
  }

  function mountCosmic() {
    if (!document.querySelector("buster-space")) document.body.insertBefore(document.createElement("buster-space"), document.body.firstChild);
    if (ui === "family") mountFamily(); else mountModern();
    wrapFetch();
  }

  // ------------------------------------------------------- settings card
  var SEASON_LABELS = {
    auto: "Automatic (holiday calendar)", none: "Off", halloween: "🎃 Halloween",
    thanksgiving: "🍂 Thanksgiving", winter: "❄️ Winter holidays", newyear: "🎉 New Year",
  };
  function seg(name, options, current, onPick) {
    var wrap = h("div", { class: "dash-seg", role: "radiogroup", "aria-label": name });
    options.forEach(function (o) {
      var b = h("button", { type: "button", role: "radio", "aria-pressed": String(o[0] === current), "aria-checked": String(o[0] === current), "data-value": o[0] }, esc(o[1]));
      b.addEventListener("click", function () {
        wrap.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); x.setAttribute("aria-checked", String(x === b)); });
        onPick(o[0]);
      });
      wrap.appendChild(b);
    });
    return wrap;
  }
  function row(label, control, help) {
    var r = h("div", { class: "dash-theme-row", style: "margin-bottom:14px" });
    r.appendChild(h("label", { class: "block text-sm font-semibold", style: "display:block;margin-bottom:6px" }, esc(label)));
    r.appendChild(control);
    if (help) r.appendChild(h("div", { class: "dash-help" }, help));
    return r;
  }
  function selectEl(id, options, current) {
    var s = h("select", { id: id, class: "px-3 py-2 rounded text-sm bg-gray-800 border border-gray-600 text-gray-200", style: "min-width:240px" });
    options.forEach(function (o) {
      var opt = h("option", { value: o[0] }, esc(o[1]));
      if (o[0] === current) opt.selected = true;
      s.appendChild(opt);
    });
    return s;
  }

  /** Render the Theme & Holidays controls into `el` (both UIs). */
  function renderSettings(el, opts) {
    if (!el) return;
    opts = opts || {};
    el.innerHTML = "";
    el.classList.add("dash-theme-settings");
    var s = api.season;
    var choices = api.seasonChoices.map(function (c) { return [c, SEASON_LABELS[c] || c]; });
    var seasonSel = selectEl("dash-season-select", choices, s.choice || "auto");
    var nowLabel = s.season === "none" ? "no holiday right now" : (SEASON_LABELS[seasonKey()] || s.season);
    el.appendChild(row("Holiday theme", seasonSel, "In effect now: <b>" + esc(nowLabel) + "</b> (" + esc(s.source) + "). Holidays are seasonal variants of Cosmic; add <code>?season=winter</code> to the URL for a preview."));
    seasonSel.addEventListener("change", function () { api.setSeason(seasonSel.value); });
    var dens = seg("Density", [["companion", "Companion"], ["operations", "Operations"]], density(), api.setDensity);
    el.appendChild(row("Cosmic density", dens,
      "Companion is expressive (big greeting, glow, seasonal particles). Operations is calm and dense with minimal motion."));
  }

  // ------------------------------------------------------------------ API
  var api = {
    renderSettings: function (el, opts) { renderSettings(el, opts); },
    ui: ui,
    get cosmic() { return cosmic; },
    get season() { return { season: season, variant: variant, source: (cfg.season && cfg.season.source) || "server", choice: (cfg.season && cfg.season.choice) || "auto" }; },
    seasonChoices: cfg.seasonChoices || ["auto", "none", "halloween", "thanksgiving", "winter", "newyear"],
    density: density,
    /** Kept for older callers: Cosmic is always loaded, so a skin change never needs a reload. */
    needsReloadFor: function () { return false; },
    /** Family UI: called by applySkin() so the companion follows the skin's theme block. */
    onSkin: function (skin) {
      var c = skin && skin.theme && skin.theme.companion;
      if (c) Object.keys(c).forEach(function (k) { companionCfg[k] = c[k]; });
      companions().forEach(function (el) { el.setAttribute("accent", companionCfg.accent || "violet"); el.setAttribute("name", companionCfg.name || "Buster"); });
      var n = document.getElementById("dash-brand-name"); if (n) n.textContent = companionCfg.name || "Buster";
      var t = document.getElementById("dash-brand-tag"); if (t && skin && skin.tagline) t.textContent = skin.tagline;
    },
    /** Kept for older callers: Cosmic is the only theme. */
    setModernTheme: function () { store("dashboard_modern_theme", THEME); },
    /** Cosmic density: "companion" (expressive) | "operations" (calm, dense). Live. */
    setDensity: function (d) {
      var m = d === "operations" ? "operations" : "companion";
      store("dashboard_density", m);
      root.setAttribute("data-mode", m);
    },
    /** Save the per-user season choice on the server, then re-render. */
    setSeason: function (choice) {
      return fetch("/api/theme", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ season: choice }) })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && d.success) {
            var u = new URL(location.href);
            u.searchParams.delete("season");
            location.replace(u.toString());
          }
          return d;
        });
    },
    companion: primary,
    companions: companions,
    setState: setState,
    setRest: setRest,
    say: say,
    celebrate: celebrate,
    thinking: function (on) { if (on) startThinking(); else stopThinking(true); },
  };
  window.DashTheme = api;

  function onReady() { mountCosmic(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady, { once: true });
  else onReady();
})();
