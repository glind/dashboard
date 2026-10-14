"""
Dashboard profile selection.

One codebase serves two kinds of installs:

* ``modern`` - the full laptop dashboard (email, leads, diagnostics, servers,
  vanity alerts, assistants, ...). Served by ``templates/dashboard_modern.html``
  + ``static/dashboard.js``.
* ``family`` - the family dashboards that run in Docker on the home server
  (comics, Roger voice, skins, iCloud calendar, ...). Served by
  ``templates/dashboard_family.html`` + ``static/dashboard_family.js``.

Selection order:
1. ``DASHBOARD_UI`` (or ``DASHBOARD_PROFILE``) env var: ``family`` or ``modern``.
2. Running inside a container (``/.dockerenv``) or with ``DASHBOARD_USER`` set
   (set by every family docker-compose service) -> ``family``.
3. Otherwise -> ``modern``.
"""

import os
from pathlib import Path

FAMILY = "family"
MODERN = "modern"

_ALIASES = {
    "family": FAMILY,
    "roger": FAMILY,
    "kids": FAMILY,
    "modern": MODERN,
    "full": MODERN,
    "laptop": MODERN,
    "master": MODERN,
}


def get_dashboard_profile() -> str:
    """Return ``"family"`` or ``"modern"`` for the running install."""
    raw = (os.environ.get("DASHBOARD_UI") or os.environ.get("DASHBOARD_PROFILE") or "").strip().lower()
    if raw in _ALIASES:
        return _ALIASES[raw]
    if Path("/.dockerenv").exists() or os.environ.get("DASHBOARD_USER"):
        return FAMILY
    return MODERN


def is_family_profile() -> bool:
    return get_dashboard_profile() == FAMILY
