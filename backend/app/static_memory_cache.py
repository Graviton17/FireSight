import json
import os
from typing import Any, Dict


class StaticMemoryCache:
    """In-memory configuration cache loaded once at startup from config.json.

    Any module can call ``StaticMemoryCache.get_config(section, key)`` without
    needing an instance or DI wiring.
    """

    # Static class variables
    config: Dict[str, Any] = {}
    _cache: Dict[str, Any] = {}

    # ---------------------------------------------------------------------------
    # Generic key-value cache (for ad-hoc runtime data)
    # ---------------------------------------------------------------------------

    @classmethod
    def get(cls, key: str) -> Any:
        return cls._cache.get(key)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        cls._cache[key] = value

    # ---------------------------------------------------------------------------
    # Initialisation
    # ---------------------------------------------------------------------------

    @classmethod
    def initialize(cls, config_file: str = "config.json") -> None:
        """Load config.json into memory at startup."""
        if not os.path.isfile(config_file):
            print(
                f"[StaticMemoryCache] WARNING: '{config_file}' not found. "
                "Using empty config — copy config.json.example and fill in credentials."
            )
            cls.config = {}
            return

        with open(config_file, "r", encoding="utf-8") as f:
            cls.config = json.load(f)

        print(f"[StaticMemoryCache] Loaded config from '{config_file}'")

    # ---------------------------------------------------------------------------
    # Config accessors
    # ---------------------------------------------------------------------------

    @classmethod
    def get_config(cls, section: str, key: str) -> Any:
        """Retrieve ``config[section][key]``, returning ``None`` on miss."""
        return cls.config.get(section, {}).get(key)

    @classmethod
    def get_section(cls, section: str) -> Dict[str, Any]:
        """Return an entire config section (empty dict on miss)."""
        return cls.config.get(section, {}) or {}

    # ---------------------------------------------------------------------------
    # Convenience helpers (add domain-specific helpers as the project grows)
    # ---------------------------------------------------------------------------

    @classmethod
    def get_server_port(cls) -> int:
        return int(cls.config.get("server", {}).get("port", 8000))

    @classmethod
    def get_server_base_url(cls) -> str:
        return cls.config.get("server", {}).get("base_url", "http://localhost:8000")

    @classmethod
    def get_auto_reload(cls) -> bool:
        """Return whether Uvicorn should auto-reload on code changes."""
        return bool(cls.config.get("server", {}).get("auto_reload", False))

    @classmethod
    def get_environment(cls) -> str:
        """Return the active environment — ``development`` or ``production``.

        The ``FIRESIGHT_ENV`` environment variable wins over config.json.
        """
        env_var = (os.getenv("FIRESIGHT_ENV") or "").strip().lower()
        if env_var in ("dev", "development"):
            return "development"
        if env_var in ("prod", "production"):
            return "production"
        raw = cls.config.get("server", {}).get("environment", "development")
        normalised = str(raw).strip().lower()
        if normalised in ("prod", "production"):
            return "production"
        return "development"


# Auto-initialise on import
StaticMemoryCache.initialize()
