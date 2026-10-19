"""Reference implementation of the Buster seasonal calendar (mirrors dist/seasons.js).

Copy this file into a FastAPI/Jinja app and render the result onto <html>:

    from buster_seasons import resolve_season
    season, variant = resolve_season()            # uses DEFAULT_WINDOWS and today's date
    # <html data-season="{{ season }}" {% if variant %}data-season-variant="{{ variant }}"{% endif %}>

Window format: {"season": str, "variant": str | None, "start": "MM-DD", "end": "MM-DD"}
Inclusive on both ends; if end < start the window wraps over New Year; first match wins.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Iterable, Mapping, Optional, Tuple

SEASONS = ("none", "halloween", "thanksgiving", "winter")

DEFAULT_WINDOWS = [
    {"season": "winter", "variant": "newyear", "start": "12-31", "end": "01-01"},
    {"season": "halloween", "start": "10-01", "end": "11-01"},
    {"season": "thanksgiving", "start": "11-02", "end": "11-30"},
    {"season": "winter", "start": "12-01", "end": "01-06"},
]


def _md(value: str) -> int:
    month, day = (int(p) for p in str(value).split("-"))
    return month * 100 + day


def resolve_season(
    date: Optional[_dt.date] = None,
    windows: Optional[Iterable[Mapping]] = None,
) -> Tuple[str, str]:
    """Return (season, variant) for ``date`` ("none", "" when no window matches)."""
    date = date or _dt.date.today()
    today = date.month * 100 + date.day
    for w in DEFAULT_WINDOWS if windows is None else windows:
        a, b = _md(w["start"]), _md(w["end"])
        hit = (a <= today <= b) if a <= b else (today >= a or today <= b)
        if hit and w.get("season") in SEASONS:
            return w["season"], w.get("variant") or ""
    return "none", ""


def season_for(date: Optional[_dt.date] = None, windows: Optional[Iterable[Mapping]] = None) -> str:
    """Season name only (variant ignored) — same as seasonFor() in seasons.js."""
    return resolve_season(date, windows)[0]


def load_windows(path: str | Path) -> list:
    """Load a calendar JSON file ({"windows": [...]}) such as dist/seasons.json."""
    return json.loads(Path(path).read_text())["windows"]


if __name__ == "__main__":  # python3 buster_seasons.py 2026-12-31
    import sys

    d = _dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else _dt.date.today()
    print(*resolve_season(d))
