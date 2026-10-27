"""Shared Supabase URL / key resolution (anon vs service_role)."""

from __future__ import annotations

import os
from typing import Tuple

from app.static_memory_cache import StaticMemoryCache


def resolve_supabase_url(section: str = "database") -> str:
    """Return configured Supabase project URL for *section*."""
    return (
        (os.getenv("SUPABASE_URL") or "").strip()
        or (StaticMemoryCache.get_config(section, "supabase_url") or "").strip()
    )


def resolve_supabase_key(
    section: str = "database",
    *,
    prefer_service_role: bool = True,
    service_role_env: str = "SUPABASE_SERVICE_ROLE_KEY",
    anon_env: str = "SUPABASE_KEY",
) -> Tuple[str, bool]:
    """Resolve a Supabase API key.

    Returns ``(key, is_service_role)``. Empty key means unconfigured.
    """
    if prefer_service_role:
        svc = (
            (os.getenv(service_role_env) or "").strip()
            or (StaticMemoryCache.get_config(section, "supabase_service_role_key") or "").strip()
        )
        if svc:
            return svc, True

    anon = (
        (os.getenv(anon_env) or "").strip()
        or (StaticMemoryCache.get_config(section, "supabase_key") or "").strip()
    )
    return anon, False


def require_supabase_credentials(
    section: str = "database",
    *,
    prefer_service_role: bool = False,
) -> Tuple[str, str, bool]:
    """Return ``(url, key, is_service_role)`` or raise ``ValueError``."""
    url = resolve_supabase_url(section)
    key, is_service_role = resolve_supabase_key(
        section,
        prefer_service_role=prefer_service_role,
    )
    if not url or not key:
        raise ValueError(
            f"Supabase URL and key must be configured for section '{section}'"
        )
    return url, key, is_service_role
