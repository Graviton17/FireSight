import json
import os
from typing import Any, Dict, Optional


class StaticMemoryCache:
    """In-memory configuration cache loaded at startup from config.json.

    Any module can call ``StaticMemoryCache.get_config(section, key)`` without
    needing an instance or DI wiring. Settings that may change while the server
    runs (the phone camera) call :meth:`reload_if_changed` first, so editing
    config.json takes effect without a restart.
    """

    # Static class variables
    config: Dict[str, Any] = {}
    _cache: Dict[str, Any] = {}
    _config_file: str = "config.json"
    _config_mtime: Optional[float] = None

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
        cls._config_file = config_file
        cls._config_mtime = None
        if not os.path.isfile(config_file):
            print(
                f"[StaticMemoryCache] WARNING: '{config_file}' not found. "
                "Using empty config — copy config.json.example and fill in credentials."
            )
            cls.config = {}
            return

        cls._config_mtime = os.stat(config_file).st_mtime
        with open(config_file, "r", encoding="utf-8") as f:
            cls.config = json.load(f)

        print(f"[StaticMemoryCache] Loaded config from '{config_file}'")

    @classmethod
    def reload_if_changed(cls) -> bool:
        """Re-read config.json if it was saved since the last load. True if reloaded.

        One ``stat`` call when nothing changed. Invalid JSON (e.g. a half-saved
        file) keeps the previous config and is retried on the next save.
        """
        try:
            mtime = os.stat(cls._config_file).st_mtime
        except OSError:
            return False
        if mtime == cls._config_mtime:
            return False

        cls._config_mtime = mtime
        try:
            with open(cls._config_file, "r", encoding="utf-8") as f:
                new_config = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(
                f"[StaticMemoryCache] WARNING: could not reload '{cls._config_file}', "
                f"keeping old config: {e}"
            )
            return False

        cls.config = new_config
        print(f"[StaticMemoryCache] Reloaded config from '{cls._config_file}'")
        return True

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
    def get_camera_base_url(cls) -> Optional[str]:
        """IP Webcam address, e.g. ``http://192.168.1.50:8080``; ``None`` when unset.

        Re-reads config.json if it changed, so the phone's IP can be updated
        while the server runs. The ``FIRESIGHT_CAMERA_URL`` environment variable
        wins over config.json (and can't be changed without a restart).
        """
        cls.reload_if_changed()
        url = (os.getenv("FIRESIGHT_CAMERA_URL") or "").strip()
        if url:
            return url
        configured = str(cls.config.get("camera", {}).get("base_url") or "").strip()
        return configured or None

    @classmethod
    def get_detection_threshold(cls) -> float:
        """Fire score (0-1) at or above which the image confirms fire. Re-read live."""
        cls.reload_if_changed()
        return float(cls.config.get("detection", {}).get("threshold", 0.7))

    @classmethod
    def get_detection_force_fire(cls) -> bool:
        """TESTING ONLY: the model's verdict is always "fire". Re-read live."""
        cls.reload_if_changed()
        return cls.config.get("detection", {}).get("force_fire") is True

    @classmethod
    def get_verification_timeout_seconds(cls) -> float:
        """Budget for camera + model on a fire POST. The ESP32 waits 5 s in total."""
        cls.reload_if_changed()
        return float(cls.config.get("detection", {}).get("timeout_seconds", 4.0))

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
