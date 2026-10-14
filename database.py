"""
Compatibility shim: the database layer lives in ``src/database.py``.

The repo root is on ``sys.path`` (ahead of ``src/``) for ``config/`` imports, and
older scripts / Dockerfiles reference a top-level ``database.py``. This shim makes
``import database`` resolve to the single real implementation in ``src/database.py``
so there is exactly one ``DatabaseManager`` / ``db`` singleton.
"""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_real_path = Path(__file__).resolve().parent / "src" / "database.py"
_spec = spec_from_file_location("database", _real_path)
if _spec is None or _spec.loader is None:  # pragma: no cover
    raise ImportError(f"Unable to load database module from {_real_path}")

_module = module_from_spec(_spec)
# Replace this shim in sys.modules before executing so `import database`
# (and any re-imports) return the real module object.
sys.modules["database"] = _module
_spec.loader.exec_module(_module)
