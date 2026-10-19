"""
Dashboard theme + seasonal (holiday) layer.

The Buster design system (vendored in ``src/static/ds`` with buster-design's
``sync.sh``) provides a shared holiday calendar. This module is the server side of
it for both UIs (family and modern):

* The server resolves the season (``buster_seasons.resolve_season``) so the first
  paint is already seasonal, and renders ``data-season`` (+ ``data-season-variant``)
  on ``<html>`` with ``data-season-lock``, which tells ``ds/seasons.js`` to keep it.
* Calendar windows are configurable in ``config/config.yaml``::

      seasons:
        enabled: true          # false = no automatic holidays (manual picks still work)
        windows:               # same format as buster-design seasons.json
          - {season: halloween, start: "10-15", end: "10-31"}

  Without that block the vendored ``src/static/ds/seasons.json`` defaults are used.
* Precedence (highest first): ``?season=`` query, the per-user choice saved in the
  dashboard's settings table (``season_override``), the calendar.

Season choices: auto | none | halloween | thanksgiving | winter | newyear.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

try:  # imported as config.theme from src/
    from config.buster_seasons import DEFAULT_WINDOWS, SEASONS, resolve_season
except ImportError:  # pragma: no cover - imported as a plain module
    from buster_seasons import DEFAULT_WINDOWS, SEASONS, resolve_season  # type: ignore

logger = logging.getLogger(__name__)

SEASON_SETTING_KEY = "season_override"
SEASON_CHOICES = ("auto", "none", "halloween", "thanksgiving", "winter", "newyear")
UI_THEMES = ("classic", "cosmic")
DENSITIES = ("companion", "operations")

DS_SEASONS_JSON = Path(__file__).resolve().parent.parent / "static" / "ds" / "seasons.json"

_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
_MD = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")


def normalize_choice(value: Optional[str]) -> Optional[str]:
    """Return a valid season choice (lower-case) or None."""
    if value is None:
        return None
    v = str(value).strip().lower()
    return v if v in SEASON_CHOICES else None


def safe_name(value: Optional[str]) -> Optional[str]:
    """Skin / theme names coming from a query string: [a-z0-9_-] only."""
    if not value:
        return None
    v = str(value).strip().lower()
    return v if _SAFE_NAME.match(v) else None


def _valid_window(w: Any) -> bool:
    return (
        isinstance(w, Mapping)
        and w.get("season") in SEASONS
        and isinstance(w.get("start"), str) and bool(_MD.match(w["start"]))
        and isinstance(w.get("end"), str) and bool(_MD.match(w["end"]))
    )


def default_windows() -> List[Dict[str, Any]]:
    """The design system's default calendar (vendored seasons.json), else the built-in copy."""
    try:
        windows = json.loads(DS_SEASONS_JSON.read_text())["windows"]
        if windows and all(_valid_window(w) for w in windows):
            return [dict(w) for w in windows]
    except Exception as e:  # pragma: no cover - file missing / corrupt
        logger.debug(f"seasons.json not usable ({e}); using built-in defaults")
    return [dict(w) for w in DEFAULT_WINDOWS]


def season_config(app_config: Optional[Mapping] = None) -> Dict[str, Any]:
    """Calendar from config.yaml's ``seasons`` block, falling back to the defaults."""
    block = (app_config or {}).get("seasons") or {}
    if not isinstance(block, Mapping):
        block = {}
    windows = block.get("windows")
    if isinstance(windows, list) and windows:
        good = [dict(w) for w in windows if _valid_window(w)]
        if len(good) != len(windows):
            logger.warning("config.yaml seasons.windows: ignored %d invalid window(s)", len(windows) - len(good))
        windows = good or default_windows()
    else:
        windows = default_windows()
    return {"windows": windows, "enabled": block.get("enabled", True) is not False}


def resolve(
    choice: Optional[str] = None,
    query: Optional[str] = None,
    today: Optional[_dt.date] = None,
    windows: Optional[Iterable[Mapping]] = None,
    enabled: bool = True,
) -> Dict[str, str]:
    """Effective season: ``{"season", "variant", "source", "choice"}``.

    ``query`` (?season=) beats the saved per-user ``choice``; both beat the calendar.
    """
    choice = normalize_choice(choice) or "auto"
    for source, value in (("query", normalize_choice(query)), ("user", choice)):
        if not value or value == "auto":
            continue
        if value == "newyear":
            return {"season": "winter", "variant": "newyear", "source": source, "choice": choice}
        return {"season": value, "variant": "", "source": source, "choice": choice}
    if not enabled:
        return {"season": "none", "variant": "", "source": "disabled", "choice": choice}
    season, variant = resolve_season(today or _dt.date.today(), list(windows) if windows is not None else None)
    return {"season": season, "variant": variant, "source": "calendar", "choice": choice}


def _json_for_script(data: Any) -> str:
    """JSON that is safe inside a <script> element."""
    return json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def inject_theme(page: str, ctx: Mapping[str, Any]) -> str:
    """Render the theme context into a dashboard template.

    * ``<html ...>`` gets ``data-ui``, ``data-season`` (+ variant) and ``data-season-lock``.
    * ``<!--DASH_THEME-->`` (right after ``<head>`` in both templates) becomes the
      calendar JSON for ds/seasons.js and ``window.__DASH_THEME__`` for theme/dash-theme.js.
    """
    season = ctx.get("season") or {}
    attrs = [
        f'data-ui="{_html.escape(str(ctx.get("ui", "")))}"',
        f'data-season="{_html.escape(season.get("season", "none"))}"',
    ]
    if season.get("variant"):
        attrs.append(f'data-season-variant="{_html.escape(season["variant"])}"')
    attrs.append("data-season-lock")
    page = re.sub(r"<html\b([^>]*)>", lambda m: f"<html{m.group(1)} {' '.join(attrs)}>", page, count=1)

    calendar = {"windows": ctx.get("windows") or [], "enabled": bool(ctx.get("enabled", True))}
    client = {
        "ui": ctx.get("ui"),
        "season": season,
        "seasonChoices": list(SEASON_CHOICES),
        "requestedSkin": ctx.get("skin"),
        "requestedTheme": ctx.get("theme"),
        "requestedDensity": ctx.get("density"),
    }
    block = (
        f'<script type="application/json" id="buster-seasons">{_json_for_script(calendar)}</script>\n'
        f"    <script>window.__DASH_THEME__ = {_json_for_script(client)};</script>"
    )
    if "<!--DASH_THEME-->" in page:
        return page.replace("<!--DASH_THEME-->", block, 1)
    return re.sub(r"<head\b[^>]*>", lambda m: m.group(0) + "\n    " + block, page, count=1)
