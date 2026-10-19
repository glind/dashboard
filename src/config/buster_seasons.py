"""Reference implementation of the Buster seasonal calendar (mirrors dist/seasons.js).

Copy this file into a FastAPI/Jinja app and render the result onto <html>:

    from buster_seasons import resolve_season
    season, variant = resolve_season()            # uses DEFAULT_WINDOWS and today's date
    # <html data-season="{{ season }}" {% if variant %}data-season-variant="{{ variant }}"{% endif %}>

Window format: {"season": str, "variant": str | None, "start": "MM-DD", "end": "MM-DD"}
("thanksgiving" may be used as a date: the 4th Thursday of November).
Inclusive on both ends; if end < start the window wraps over New Year; first match wins.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Iterable, Mapping, Optional, Tuple

SEASONS = ("none", "halloween", "thanksgiving", "winter")

DEFAULT_WINDOWS = [
    {"season": "winter", "variant": "newyear", "start": "12-27", "end": "01-02"},
    {"season": "halloween", "start": "10-15", "end": "10-31"},
    {"season": "thanksgiving", "start": "11-15", "end": "thanksgiving"},
    {"season": "winter", "start": "12-01", "end": "12-26"},
]


def thanksgiving_day(year: int) -> int:
    """US Thanksgiving: the 4th Thursday of November in ``year`` (day of month)."""
    first = _dt.date(year, 11, 1).weekday()  # Monday = 0 … Thursday = 3
    return 1 + (3 - first) % 7 + 21


def _md(value: str, year: int) -> int:
    """"MM-DD" (or the keyword "thanksgiving") → MMDD integer for ``year``."""
    if str(value).lower() == "thanksgiving":
        return 1100 + thanksgiving_day(year)
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
        a, b = _md(w["start"], date.year), _md(w["end"], date.year)
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
