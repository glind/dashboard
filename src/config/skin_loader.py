"""
Skin Loader Module
Manages dashboard skins/themes with runtime switching support.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

logger = logging.getLogger(__name__)

# Default skin if none specified
DEFAULT_SKIN = "roger"

# Base path for skins - check Docker shared mount first, then local dev path
_DOCKER_SKINS_PATH = Path("/app/shared/skins")
_LOCAL_SKINS_PATH = Path(__file__).parent.parent.parent / "data" / "skins"

# Use Docker path if it exists (running in container), otherwise use local
SKINS_DIR = _DOCKER_SKINS_PATH if _DOCKER_SKINS_PATH.exists() else _LOCAL_SKINS_PATH

# Built-in skins ship with the code (src/config/skins/<name>/skin.yaml), so they are
# available on every install without copying anything into the personal data/skins
# folder. A skin of the same name in SKINS_DIR overrides the built-in one.
BUILTIN_SKINS_DIR = Path(__file__).parent / "skins"


class Skin:
    """Represents a loaded skin configuration."""
    
    def __init__(self, name: str, config: Dict[str, Any], quotes: Dict[str, Any]):
        self.name = name
        self.config = config
        self.quotes = quotes
        
        # Extract commonly used values
        self.identity = config.get("identity", {})
        self.colors = config.get("colors", {})
        self.voice = config.get("voice", {})
        self.dashboard = config.get("dashboard", {})
        self.backgrounds = config.get("backgrounds", [])
        self.navigation = config.get("navigation", [])
        self.features = config.get("features", {})
        self.ai_personality = config.get("ai_personality", {})
        # Optional design-system theme block (e.g. the built-in "cosmic" skin).
        self.theme = config.get("theme", {}) or {}
        self.builtin = False
    
    @property
    def display_name(self) -> str:
        return self.identity.get("display_name", self.name.title())
    
    @property
    def tagline(self) -> str:
        return self.identity.get("tagline", "Personal Assistant")
    
    @property
    def avatar(self) -> str:
        return self.identity.get("avatar", "/assets/images/assistant.png")
    
    @property
    def wake_words(self) -> List[str]:
        return self.identity.get("wake_words", [self.name])
    
    @property
    def signature_phrase(self) -> str:
        return self.identity.get("signature_phrase", "Acknowledged.")
    
    def get_css_variables(self) -> Dict[str, str]:
        """Generate CSS variables from color config."""
        css_vars = {}
        for key, value in self.colors.items():
            css_key = f"--skin-{key.replace('_', '-')}"
            css_vars[css_key] = value
        return css_vars
    
    def get_css_string(self) -> str:
        """Generate CSS variable declarations as a string."""
        vars_dict = self.get_css_variables()
        lines = [f"  {k}: {v};" for k, v in vars_dict.items()]
        return ":root {\n" + "\n".join(lines) + "\n}"
    
    def get_random_quote(self, category: str = "random_quotes") -> str:
        """Get a random quote from the specified category."""
        import random
        quotes_list = self.quotes.get(category, [])
        if quotes_list:
            return random.choice(quotes_list)
        return self.signature_phrase
    
    def get_widgets(self) -> Dict[str, Any]:
        """Get widget configuration from dashboard settings."""
        return self.dashboard.get("widgets", {})
    
    def is_widget_enabled(self, widget_name: str) -> bool:
        """Check if a specific widget is enabled for this skin."""
        widgets = self.get_widgets()
        widget_config = widgets.get(widget_name, {})
        return widget_config.get("enabled", False)
    
    def get_enabled_widgets(self) -> List[str]:
        """Get list of enabled widget names."""
        widgets = self.get_widgets()
        return [name for name, config in widgets.items() 
                if isinstance(config, dict) and config.get("enabled", False)]
    
    def get_widget_config(self, widget_name: str) -> Dict[str, Any]:
        """Get configuration for a specific widget."""
        widgets = self.get_widgets()
        return widgets.get(widget_name, {})
    
    def to_json(self) -> Dict[str, Any]:
        """Export skin data for frontend use."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "tagline": self.tagline,
            "avatar": self.avatar,
            "wake_words": self.wake_words,
            "signature_phrase": self.signature_phrase,
            "colors": self.colors,
            "css_variables": self.get_css_variables(),
            "voice": self.voice,
            "dashboard": self.dashboard,
            "backgrounds": self.backgrounds,
            "navigation": self.navigation,
            "features": self.features,
            "quotes": self.quotes,
            "ai_personality": self.ai_personality,
            "identity": self.identity,
            "theme": self.theme,
            "builtin": self.builtin,
        }


class SkinLoader:
    """Loads and manages dashboard skins."""
    
    def __init__(self, skins_dir: Optional[Path] = None, builtin_dir: Optional[Path] = None):
        self.skins_dir = skins_dir or SKINS_DIR
        self.builtin_dir = builtin_dir if builtin_dir is not None else BUILTIN_SKINS_DIR
        self._skins_cache: Dict[str, Skin] = {}
        self._active_skin_name: str = DEFAULT_SKIN
        self._active_skin: Optional[Skin] = None
        
        # Ensure skins directory exists
        self.skins_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"SkinLoader initialized with skins directory: {self.skins_dir}")
    
    def _skin_dirs(self) -> List[Path]:
        """Skin search path: personal/shared skins first, then built-in skins."""
        dirs = [self.skins_dir]
        if self.builtin_dir and self.builtin_dir != self.skins_dir:
            dirs.append(self.builtin_dir)
        return dirs

    def _find_skin_dir(self, skin_name: str) -> Optional[Path]:
        if not skin_name or "/" in skin_name or "\\" in skin_name or skin_name.startswith("."):
            return None
        for base in self._skin_dirs():
            candidate = base / skin_name
            if (candidate / "skin.yaml").exists():
                return candidate
        return None

    def list_available_skins(self) -> List[Dict[str, Any]]:
        """List all available skins (personal + built-in) with basic info including voice."""
        skins = []
        seen = set()

        if not self.skins_dir.exists():
            logger.warning(f"Skins directory does not exist: {self.skins_dir}")

        for base in self._skin_dirs():
            if not base or not base.exists():
                continue
            builtin = base == self.builtin_dir
            for skin_dir in sorted(base.iterdir()):
                if not skin_dir.is_dir() or skin_dir.name in seen:
                    continue
                skin_yaml = skin_dir / "skin.yaml"
                if skin_yaml.exists():
                    try:
                        with open(skin_yaml, 'r') as f:
                            config = yaml.safe_load(f) or {}
                        identity = config.get("identity", {})
                        voice = config.get("voice", {})
                        skins.append({
                            "name": skin_dir.name,
                            "display_name": identity.get("display_name", skin_dir.name.title()),
                            "tagline": identity.get("tagline", ""),
                            "avatar": identity.get("avatar", ""),
                            "voice": voice,
                            "builtin": builtin,
                        })
                        seen.add(skin_dir.name)
                    except Exception as e:
                        logger.error(f"Error reading skin {skin_dir.name}: {e}")
        
        return skins
    
    def load_skin(self, skin_name: str) -> Optional[Skin]:
        """Load a skin by name."""
        # Check cache first
        if skin_name in self._skins_cache:
            logger.debug(f"Returning cached skin: {skin_name}")
            return self._skins_cache[skin_name]
        
        skin_dir = self._find_skin_dir(skin_name)
        
        if skin_dir is None:
            logger.error(f"Skin not found: {skin_name} (searched {', '.join(str(d) for d in self._skin_dirs())})")
            return None
        
        skin_yaml = skin_dir / "skin.yaml"
        quotes_json = skin_dir / "quotes.json"
        
        if not skin_yaml.exists():
            logger.error(f"Skin config not found: {skin_yaml}")
            return None
        
        try:
            # Load skin config
            with open(skin_yaml, 'r') as f:
                config = yaml.safe_load(f)
            
            # Load quotes (optional)
            quotes = {}
            if quotes_json.exists():
                with open(quotes_json, 'r') as f:
                    quotes = json.load(f)
            
            skin = Skin(skin_name, config or {}, quotes)
            skin.builtin = skin_dir.parent == self.builtin_dir
            self._skins_cache[skin_name] = skin
            
            logger.info(f"Loaded skin: {skin_name} ({skin.display_name})")
            return skin
            
        except Exception as e:
            logger.error(f"Error loading skin {skin_name}: {e}")
            return None
    
    def get_active_skin(self) -> Skin:
        """Get the currently active skin."""
        if self._active_skin is None:
            self._active_skin = self.load_skin(self._active_skin_name)
            if self._active_skin is None:
                # Fall back to default
                logger.warning(f"Could not load skin {self._active_skin_name}, falling back to {DEFAULT_SKIN}")
                self._active_skin_name = DEFAULT_SKIN
                self._active_skin = self.load_skin(DEFAULT_SKIN)
        
        return self._active_skin
    
    def set_active_skin(self, skin_name: str) -> bool:
        """Set the active skin by name."""
        skin = self.load_skin(skin_name)
        if skin:
            self._active_skin_name = skin_name
            self._active_skin = skin
            logger.info(f"Active skin set to: {skin_name}")
            return True
        return False
    
    @property
    def active_skin_name(self) -> str:
        return self._active_skin_name
    
    def reload_skin(self, skin_name: str) -> Optional[Skin]:
        """Force reload a skin from disk."""
        if skin_name in self._skins_cache:
            del self._skins_cache[skin_name]
        
        skin = self.load_skin(skin_name)
        
        # Update active skin if it was reloaded
        if skin_name == self._active_skin_name:
            self._active_skin = skin
        
        return skin
    
    def reload_all_skins(self):
        """Force reload all cached skins."""
        self._skins_cache.clear()
        self._active_skin = None


# Global skin loader instance
_skin_loader: Optional[SkinLoader] = None


def get_skin_loader() -> SkinLoader:
    """Get the global skin loader instance."""
    global _skin_loader
    if _skin_loader is None:
        _skin_loader = SkinLoader()
    return _skin_loader


def get_active_skin() -> Skin:
    """Convenience function to get the active skin."""
    return get_skin_loader().get_active_skin()


def set_active_skin(skin_name: str) -> bool:
    """Convenience function to set the active skin."""
    return get_skin_loader().set_active_skin(skin_name)


def list_skins() -> List[Dict[str, str]]:
    """Convenience function to list available skins."""
    return get_skin_loader().list_available_skins()
