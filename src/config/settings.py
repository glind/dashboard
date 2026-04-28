"""Compatibility shim for importing project-level settings from src package context.

Some modules import `config.settings` while running with `/src` on `sys.path`.
This file re-exports symbols from the root `config/settings.py` so imports
resolve consistently regardless of working directory.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_root_settings_path = Path(__file__).resolve().parents[2] / "config" / "settings.py"
_spec = spec_from_file_location("_project_root_config_settings", _root_settings_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load settings module from {_root_settings_path}")

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

# Re-export public symbols to mimic direct import from root config/settings.py
for _name in dir(_module):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_module, _name)

__all__ = [name for name in globals() if not name.startswith("_")]
