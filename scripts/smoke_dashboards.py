#!/usr/bin/env python3
"""Read-only smoke test for Personal Dashboard instances (laptop + family dashboards on hoth).

For every section of the UI it hits the page + API endpoints the section uses (GET only)
and reports status code, response time and the *shape* of the JSON (type, item counts,
success/error flags). With ``--browser`` it also loads the page in headless Google Chrome
(scratch profile, no downloads), opens every section and records front-end JS errors and
failed requests.

PRIVACY: only status / shape / counts / error *types* are recorded — never content
(no subjects, titles, names). Error strings are truncated and e-mail addresses redacted.

Usage::

    python scripts/smoke_dashboards.py http://greg.hoth.home http://parker.hoth.home \
        http://ramona.hoth.home http://sarah.hoth.home http://127.0.0.1:8008 --browser
    python scripts/smoke_dashboards.py http://greg.hoth.home --json /tmp/smoke.json
    python scripts/smoke_dashboards.py http://127.0.0.1:8008 --ui modern -v

Exit code: 0 when every *required* check passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

FAMILY, MODERN, BOTH = "family", "modern", ("family", "modern")

# section -> (UIs that show it, [(path, required?)])
# required=False: optional integrations (OAuth/API keys) — reported but not failing.
# An optional third element limits a check to some UIs.
SECTIONS: Dict[str, Dict[str, Any]] = {
    "core": {"ui": BOTH, "checks": [("/", True), ("/api/health", True), ("/health", False),
                                    ("/api/config", True), ("/api/theme", True),
                                    ("/static/ds/VERSION.txt", True), ("/static/ds/buster.js", True),
                                    ("/static/ds/companion.js", True),
                                    ("/static/theme/dash-theme.js", True),
                                    ("/static/theme/dash-theme.css", True)]},
    "weather": {"ui": BOTH, "checks": [("/api/weather", True), ("/api/weather/search?q=Portland", False),
                                        ("/api/weather/ambient", False)]},
    "calendar": {"ui": BOTH, "checks": [("/api/calendar", True), ("/api/calendar/family", False)]},
    "tasks": {"ui": BOTH, "checks": [("/api/tasks", True), ("/api/task-sync/providers/status", False)]},
    "news": {"ui": BOTH, "checks": [("/api/news", True), ("/api/news-sources", False)]},
    "comics": {"ui": (FAMILY,), "checks": [("/api/settings/comics", True), ("/api/comics/feeds", False),
                                           ("/api/comics/garfield/daily", True),
                                           ("/api/comics/calvin/daily", True),
                                           ("/api/comics/peanuts/daily", True),
                                           ("/api/comics/bloomcounty/daily", False),
                                           ("/api/comics/garfield/history?limit=30", True),
                                           ("/api/comics/calvin/history?limit=30", True),
                                           ("/api/comics/favorites", True)]},
    "jokes_quote": {"ui": BOTH, "checks": [("/api/joke", True), ("/api/quote", True, (FAMILY,))]},
    "calm_tips": {"ui": (FAMILY,), "checks": [("/api/feeds/anxiety", True)]},
    "music": {"ui": BOTH, "checks": [("/api/music/stations", True), ("/api/music/station/nullrecords", False),
                                      ("/api/music/favorites", True), ("/api/music", False)]},
    "ebay": {"ui": (FAMILY,), "checks": [("/api/ebay/auctions?category=retro_tech", False)]},
    "homeassistant": {"ui": (FAMILY,), "checks": [("/api/roger_home", False)]},
    "voice": {"ui": BOTH, "checks": [("/api/voice/settings", True, (FAMILY,)), ("/api/settings/voice", False)]},
    "settings": {"ui": BOTH, "checks": [("/api/settings/avatar", True, (FAMILY,)), ("/api/settings/ai", False),
                                         ("/api/auth/google/status", True), ("/api/user/profile", True),
                                         ("/api/skins", False), ("/api/skins/active", False)]},
    "email": {"ui": (MODERN,), "checks": [("/api/email", True), ("/api/email/labels/list", False)]},
    "github": {"ui": (MODERN,), "checks": [("/api/github", False)]},
    "notes": {"ui": (MODERN,), "checks": [("/api/notes", False), ("/api/settings/notes", False)]},
    "ai_assistant": {"ui": BOTH, "checks": [("/assistant", True), ("/api/ai/providers", False),
                                             ("/api/ai/assistants", False), ("/api/ollama/status", False)]},
    "assistant_api_v1": {"ui": BOTH, "checks": [("/api/v1/assistant/health", True)]},
    "vanity": {"ui": (MODERN,), "checks": [("/api/vanity-alerts", False)]},
    "servers": {"ui": (MODERN,), "checks": [("/api/servers", False), ("/api/dashboards", False)]},
    "diagnostics": {"ui": (MODERN,), "checks": [("/api/diagnostics/events", False)]},
    "liked": {"ui": (MODERN,), "checks": [("/api/liked-items", False), ("/api/suggested-todos", False)]},
}

# Sections each UI opens with showSection(...) in the browser pass.
UI_SECTIONS = {
    FAMILY: ["overview", "weather", "news", "tasks", "calendar", "homeassistant", "settings"],
    MODERN: ["overview", "weather", "calendar", "emails", "todos", "news", "music", "github", "notes",
             "ai", "comms", "liked", "vanity", "servers", "providers", "diagnostics", "settings"],
}

_EMAIL = re.compile(r"[\w.%+-]+@[\w.-]+\.[a-z]{2,}", re.I)
_PATHLIKE = re.compile(r"(/Users|/home|/app)/\S+")
_ERROR_KEYS = ("error", "detail", "message")
_LIST_HINTS = ("events", "emails", "tasks", "articles", "items", "news", "results", "comics", "history",
               "favorites", "stations", "tracks", "data", "forecast", "tips", "skins", "auctions",
               "notes", "repos", "issues", "alerts", "providers", "assistants", "dashboards", "servers")


def scrub(text: Any, n: int = 120) -> str:
    s = _PATHLIKE.sub("<path>", _EMAIL.sub("<email>", str(text)))
    return s[:n]


def shape(data: Any) -> Dict[str, Any]:
    """Structure only: type, counts, success/error flags. Never values."""
    if isinstance(data, list):
        return {"type": "list", "count": len(data)}
    if not isinstance(data, dict):
        return {"type": type(data).__name__}
    out: Dict[str, Any] = {"type": "dict", "keys": len(data)}
    if "success" in data:
        out["success"] = data["success"]
    if isinstance(data.get("sample"), bool):
        out["sample"] = data["sample"]
    if "ok" in data and isinstance(data["ok"], bool):
        out["ok"] = data["ok"]
    for k in _ERROR_KEYS:
        if data.get(k) and isinstance(data[k], (str, dict)) and (k != "message" or data.get("success") is False):
            out["error"] = scrub(data[k] if isinstance(data[k], str) else json.dumps(data[k]))
            break
    counts = {}
    for k, v in data.items():
        if isinstance(v, list) and (k in _LIST_HINTS or len(counts) < 6):
            counts[k] = len(v)
        elif isinstance(v, dict) and k in _LIST_HINTS:
            counts[k] = len(v)
    if counts:
        out["counts"] = counts
    for k, v in data.items():  # e.g. {"comic": {"image_url": ...}} -> has_image (never the URL)
        if isinstance(v, dict) and "image_url" in v:
            out["has_image"] = bool(v.get("image_url"))
    if "image_url" in data:
        out["has_image"] = bool(data.get("image_url"))
    return out


@dataclass
class Check:
    section: str
    path: str
    required: bool
    status: int = 0
    ms: int = 0
    kind: str = ""
    shape: Dict[str, Any] = field(default_factory=dict)
    verdict: str = ""        # ok | empty | error | http | timeout
    note: str = ""


def judge(c: Check) -> None:
    if c.status == 0:
        c.verdict = "timeout" if "timeout" in c.note.lower() else "error"
        return
    if c.status >= 400:
        c.verdict = "http"
        return
    sh = c.shape
    if sh.get("success") is False or sh.get("ok") is False or ("error" in sh and sh.get("type") == "dict"):
        c.verdict = "error"
        c.note = c.note or sh.get("error", "success=false")
        return
    if sh.get("sample") is True:
        c.verdict = "empty"
        c.note = c.note or "sample data (live source unavailable)"
        return
    if sh.get("has_image") is False:
        c.verdict = "empty"
        return
    if sh.get("type") == "list" and sh.get("count") == 0:
        c.verdict = "empty"
        return
    if sh.get("counts") and all(v == 0 for v in sh["counts"].values()):
        c.verdict = "empty"
        return
    c.verdict = "ok"


async def run_http(base: str, ui: str, timeout: float, verbose: bool) -> List[Check]:
    results: List[Check] = []
    sem = asyncio.Semaphore(4)

    async with httpx.AsyncClient(base_url=base, timeout=timeout, follow_redirects=True) as client:
        async def one(section: str, path: str, required: bool) -> Check:
            c = Check(section, path, required)
            async with sem:
                t0 = time.monotonic()
                try:
                    r = await client.get(path)
                    c.status = r.status_code
                    c.kind = r.headers.get("content-type", "").split(";")[0]
                    if "json" in c.kind:
                        try:
                            c.shape = shape(r.json())
                        except ValueError:
                            c.note = "invalid JSON"
                    elif c.kind.startswith("text/html"):
                        c.shape = {"type": "html", "bytes": len(r.content)}
                    else:
                        c.shape = {"type": c.kind or "?", "bytes": len(r.content)}
                        if path.endswith("VERSION.txt"):
                            c.note = scrub(r.text.strip(), 60)
                except httpx.TimeoutException:
                    c.note = f"timeout after {timeout:.0f}s"
                except httpx.HTTPError as e:
                    c.note = scrub(f"{type(e).__name__}: {e}")
                c.ms = int((time.monotonic() - t0) * 1000)
            judge(c)
            if verbose:
                print(f"  {c.section:16} {c.path:48} {c.status:>3} {c.ms:>6}ms {c.verdict} {c.note}", file=sys.stderr)
            return c

        tasks = []
        for section, spec in SECTIONS.items():
            if ui not in spec["ui"]:
                continue
            for path, required, *only in spec["checks"]:
                if only and ui not in only[0]:
                    continue
                tasks.append(one(section, path, required))
        results = list(await asyncio.gather(*tasks))
    return results


# ---------------------------------------------------------------- browser (CDP)

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


def find_chrome() -> Optional[str]:
    for c in CHROME_CANDIDATES:
        p = c if os.path.isabs(c) else shutil.which(c)
        if p and os.path.exists(p):
            return p
    return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class CDP:
    def __init__(self, ws):
        self.ws, self.n, self.events, self.waiters = ws, 0, [], {}

    async def pump(self):
        async for raw in self.ws:
            msg = json.loads(raw)
            if "id" in msg and msg["id"] in self.waiters:
                self.waiters.pop(msg["id"]).set_result(msg)
            elif "method" in msg:
                self.events.append(msg)

    async def call(self, method, **params):
        self.n += 1
        fut = asyncio.get_running_loop().create_future()
        self.waiters[self.n] = fut
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        return await asyncio.wait_for(fut, 30)


def _summarize_events(events: List[dict], base: str) -> Dict[str, Any]:
    js, console, failed = [], [], []
    req_urls: Dict[str, str] = {}
    host = urlparse(base).netloc
    for e in events:
        m, p = e["method"], e.get("params", {})
        if m == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails", {})
            desc = (d.get("exception") or {}).get("description") or d.get("text", "")
            src = d.get("url", "").rsplit("/", 1)[-1].split("?")[0]
            js.append(scrub(f"{desc.splitlines()[0] if desc else '?'} @{src}:{d.get('lineNumber', '?')}", 160))
        elif m == "Runtime.consoleAPICalled" and p.get("type") == "error":
            args = p.get("args", [])
            txt = " ".join(str(a.get("value", a.get("description", "")))[:80] for a in args[:2])
            console.append(scrub(txt, 160))
        elif m == "Log.entryAdded" and p.get("entry", {}).get("level") == "error":
            ent = p["entry"]
            if ent.get("source") != "network":
                console.append(scrub(ent.get("text", ""), 160))
        elif m == "Network.requestWillBeSent":
            req_urls[p["requestId"]] = p["request"]["url"]
        elif m == "Network.responseReceived":
            st = p["response"]["status"]
            u = urlparse(p["response"]["url"])
            if st >= 400 and u.netloc == host:
                failed.append(f"{st} {u.path}")
        elif m == "Network.loadingFailed" and not p.get("canceled"):
            u = urlparse(req_urls.get(p["requestId"], "?"))
            if u.netloc == host:
                failed.append(f"FAILED({scrub(p.get('errorText', ''), 40)}) {u.path}")
    dedup = lambda xs: sorted(set(xs))  # noqa: E731
    return {"js_errors": dedup(js), "console_errors": dedup(console), "failed_requests": dedup(failed)}


# Family UI interaction probes: return counts/flags only (never content).
FAMILY_PROBES = {
    "comics_archive_paging": """(async()=>{const sel=document.getElementById('comic-select');
        if(!sel) return {missing:true};
        const out={};
        for (const c of ['calvin','garfield']) {
          if(![...sel.options].some(o=>o.value===c)) {out[c]='not in dropdown'; continue;}
          sel.value=c; await showComicsArchive(); await new Promise(r=>setTimeout(r,1500));
          const n=document.querySelectorAll('#garfield-archive-content > div[onclick]').length;
          if(!n){out[c]={archive:0}; closeGarfieldArchive(); continue;}
          openComicFromArchive((window.comicArchiveList||[]).length-1);
          const before=document.getElementById('comic-viewer-counter').textContent;
          previousComic(); previousComic();
          const after=document.getElementById('comic-viewer-counter').textContent;
          closeComicViewer(); closeGarfieldArchive();
          out[c]={archive:n, paged: before!==after, counter_after: after.trim()};
        }
        return out;})()""",
    "tasks_list_loaded": """(async()=>{showSection('tasks'); await new Promise(r=>setTimeout(r,2500));
        const t=(document.getElementById('tasks-list')||{}).innerText||''; return {loading: /Loading tasks/.test(t), length: t.length};})()""",
    "music_player_state": """(async()=>{showSection('overview'); await new Promise(r=>setTimeout(r,500));
        const t=(document.getElementById('now-playing')||{}).innerText||''; return {stuck_loading: /^Loading/m.test(t), length: t.length};})()""",
    "theme_picker_present": """(()=>({skinSelect: !!document.querySelector('#skin-select,#skin-select-header,#dash-skin-select'),
        bgPicker: !!document.getElementById('bg-select')}))()""",
}


async def _family_probes(cdp) -> Dict[str, Any]:
    res: Dict[str, Any] = {}
    for name, expr in FAMILY_PROBES.items():
        mark = len(cdp.events)
        try:
            r = await cdp.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
            res[name] = r.get("result", {}).get("result", {}).get("value")
            exc = r.get("result", {}).get("exceptionDetails")
            if exc:
                res[name] = {"throw": scrub((exc.get("exception") or {}).get("description", exc.get("text", "")), 120)}
        except Exception as e:  # noqa: BLE001
            res[name] = {"error": scrub(e)}
        ev = _summarize_events(cdp.events[mark:], "")
        if ev["js_errors"]:
            res[name + "_js_errors"] = ev["js_errors"]
    return res


async def run_browser(base: str, ui: str, wait: float, local_storage: Dict[str, str]) -> Dict[str, Any]:
    try:
        import websockets  # type: ignore
    except ImportError:
        return {"skipped": "websockets package not installed"}
    chrome = find_chrome()
    if not chrome:
        return {"skipped": "Google Chrome not found"}
    port = free_port()
    profile = tempfile.mkdtemp(prefix="smoke-chrome-")
    proc = subprocess.Popen([chrome, "--headless=new", f"--remote-debugging-port={port}",
                             f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
                             "--disable-extensions", "--mute-audio", "--window-size=1440,1000",
                             "--autoplay-policy=user-gesture-required", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out: Dict[str, Any] = {}
    try:
        ws_url = None
        for _ in range(50):
            try:
                tabs = httpx.get(f"http://127.0.0.1:{port}/json", timeout=1).json()
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page")
                break
            except Exception:
                await asyncio.sleep(0.2)
        if not ws_url:
            return {"skipped": "Chrome did not start"}
        async with websockets.connect(ws_url, max_size=50_000_000) as ws:
            cdp = CDP(ws)
            pump = asyncio.create_task(cdp.pump())
            for dom in ("Runtime", "Log", "Network", "Page"):
                await cdp.call(f"{dom}.enable")
            if local_storage:
                # set storage on the origin before the app script runs
                js = "".join(f"localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in local_storage.items())
                await cdp.call("Page.addScriptToEvaluateOnNewDocument", source=(
                    "try{if(window.top===window&&!sessionStorage.__smokeSeeded){sessionStorage.__smokeSeeded=1;"
                    + js + "}}catch(e){}"))
            t0 = time.monotonic()
            await cdp.call("Page.navigate", url=base.rstrip("/") + "/")
            await asyncio.sleep(wait)
            out["load_s"] = round(time.monotonic() - t0, 1)
            r = await cdp.call("Runtime.evaluate", returnByValue=True, expression=(
                "JSON.stringify({theme:document.documentElement.dataset.theme||'',"
                "ui:document.documentElement.dataset.ui||'',season:document.documentElement.dataset.season||'',"
                "companion:!!document.querySelector('buster-companion'),"
                "companionDefined:!!(window.customElements&&customElements.get('buster-companion')),"
                "skinSelect:!!document.getElementById('skin-select'),"
                "themeSelect:!!document.querySelector('#skin-select-header,#theme-select,[data-theme-picker]'),"
                "storedSkin:(()=>{try{return localStorage.getItem('dashboard_skin')}catch(e){return null}})(),"
                "storedModernTheme:(()=>{try{return localStorage.getItem('dashboard_modern_theme')}catch(e){return null}})(),"
                "showSection:typeof window.showSection})"))
            try:
                out["page"] = json.loads(r["result"]["result"]["value"])
            except Exception:
                out["page"] = {}
            out["load"] = _summarize_events(cdp.events, base)
            sections = {}
            for name in UI_SECTIONS[ui]:
                mark = len(cdp.events)
                r = await cdp.call("Runtime.evaluate", returnByValue=True, awaitPromise=True, expression=(
                    f"(async()=>{{const el=document.getElementById('section-{name}');"
                    f"if(!el) return 'missing';"
                    f"try{{ await window.showSection('{name}'); }}catch(e){{return 'throw:'+e.message}}"
                    f"await new Promise(r=>setTimeout(r,2500));"
                    f"const vis=el.offsetParent!==null||getComputedStyle(el).display!=='none';"
                    f"return (vis?'visible':'hidden')+':'+el.innerText.trim().length}})()"))
                res = r.get("result", {}).get("result", {}).get("value", "?")
                ev = _summarize_events(cdp.events[mark:], base)
                st, _, length = str(res).partition(":")
                sections[name] = {"state": st if not st.startswith("throw") else "throw",
                                  "text_len": int(length) if length.isdigit() else None,
                                  **({"throw": scrub(res, 120)} if st.startswith("throw") else {}),
                                  **{k: v for k, v in ev.items() if v}}
            out["sections"] = sections
            if ui == FAMILY:
                out["probes"] = await _family_probes(cdp)
            pump.cancel()
    except Exception as e:  # noqa: BLE001
        out["browser_error"] = scrub(f"{type(e).__name__}: {e}")
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except Exception:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
    return out


async def detect_ui(base: str, timeout: float) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            html = (await c.get(base.rstrip("/") + "/")).text
        m = re.search(r'<html[^>]*data-ui="(family|modern)"', html)
        if m:
            return m.group(1)
        return FAMILY if 'id="skin-css"' in html or "dashboard_family.js" in html else MODERN
    except Exception:
        return MODERN


async def smoke(base: str, args) -> Dict[str, Any]:
    ui = args.ui if args.ui != "auto" else await detect_ui(base, args.timeout)
    if args.verbose:
        print(f"== {base} (ui={ui})", file=sys.stderr)
    checks = await run_http(base, ui, args.timeout, args.verbose)
    report: Dict[str, Any] = {"base": base, "ui": ui, "checks": [asdict(c) for c in checks]}
    if args.browser:
        ls = dict(kv.split("=", 1) for kv in args.local_storage)
        report["browser"] = await run_browser(base, ui, args.wait, ls)
    return report


def section_matrix(report: Dict[str, Any]) -> Dict[str, str]:
    """section -> OK | PARTIAL(...) | BROKEN(...)"""
    out: Dict[str, str] = {}
    by: Dict[str, List[dict]] = {}
    for c in report["checks"]:
        by.setdefault(c["section"], []).append(c)
    for section, cs in by.items():
        bad_req = [c for c in cs if c["required"] and c["verdict"] in ("http", "error", "timeout")]
        bad_opt = [c for c in cs if not c["required"] and c["verdict"] in ("http", "error", "timeout")]
        empty = [c for c in cs if c["verdict"] == "empty"]
        if bad_req:
            out[section] = "BROKEN(" + "; ".join(f"{c['path'].split('?')[0]} {c['status'] or c['verdict']}" for c in bad_req) + ")"
        elif bad_opt:
            out[section] = "PARTIAL(" + "; ".join(f"{c['path'].split('?')[0]} {c['status'] or c['verdict']}" for c in bad_opt) + ")"
        elif empty:
            out[section] = "OK(empty: " + ", ".join(c["path"].split("?")[0] for c in empty) + ")"
        else:
            out[section] = "OK"
    br = report.get("browser") or {}
    for name, s in (br.get("sections") or {}).items():
        key = f"ui:{name}"
        if s.get("state") == "missing":
            out[key] = "MISSING"
        elif s.get("state") == "throw" or s.get("js_errors"):
            out[key] = "BROKEN(js: " + "; ".join((s.get("js_errors") or [s.get("throw", "")])[:2]) + ")"
        elif s.get("failed_requests"):
            out[key] = "PARTIAL(" + "; ".join(s["failed_requests"][:3]) + ")"
        else:
            out[key] = "OK"
    return out


def print_report(report: Dict[str, Any]) -> None:
    print(f"\n### {report['base']}  (ui={report['ui']})")
    for c in report["checks"]:
        flag = {"ok": "  ", "empty": " ~", "http": "!!", "error": "!!", "timeout": "!!"}[c["verdict"]]
        if not c["required"] and flag == "!!":
            flag = " ?"
        extra = json.dumps({**(c["shape"].get("counts") or {}),
                            **{k: v for k, v in c["shape"].items() if k in ("count", "bytes", "has_image", "success", "sample")}})
        print(f"{flag} {c['section']:16} {c['path'][:52]:52} {c['status']:>3} {c['ms']:>6}ms "
              f"{c['verdict']:7} {extra[:60]} {c['note']}")
    br = report.get("browser")
    if br:
        if br.get("skipped") or br.get("browser_error"):
            print("   browser:", br.get("skipped") or br.get("browser_error"))
        else:
            print(f"   browser: page={json.dumps(br.get('page'))} load={br.get('load_s')}s")
            for k, v in (br.get("load") or {}).items():
                for item in v[:12]:
                    print(f"   load {k}: {item}")
            for name, v in (br.get("probes") or {}).items():
                print(f"   probe {name:22} {json.dumps(v)[:300]}")
            for name, s in (br.get("sections") or {}).items():
                extras = {k: v for k, v in s.items() if k not in ("state", "text_len")}
                print(f"   section {name:14} {s.get('state')} text={s.get('text_len')} {json.dumps(extras)[:300] if extras else ''}")
    print("   matrix:", json.dumps(section_matrix(report), indent=None))


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bases", nargs="+", help="dashboard base URLs")
    ap.add_argument("--ui", choices=["auto", FAMILY, MODERN], default="auto")
    ap.add_argument("--timeout", type=float, default=30.0, help="per-request timeout (s)")
    ap.add_argument("--browser", action="store_true", help="also load the page in headless Chrome")
    ap.add_argument("--wait", type=float, default=8.0, help="seconds to let the page load in the browser")
    ap.add_argument("--local-storage", action="append", default=[], metavar="KEY=VALUE",
                    help="preset localStorage before load (e.g. dashboard_skin=roger to test migration)")
    ap.add_argument("--json", help="write the full (content-free) report to this file")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    reports = []
    for base in args.bases:
        reports.append(await smoke(base.rstrip("/"), args))
        print_report(reports[-1])
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"reports": reports, "matrix": {r["base"]: section_matrix(r) for r in reports}}, f, indent=2)
    failed = any(c["required"] and c["verdict"] in ("http", "error", "timeout") for r in reports for c in r["checks"])
    failed |= any((r.get("browser") or {}).get("load", {}).get("js_errors") for r in reports)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
