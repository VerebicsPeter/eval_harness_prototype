"""Service configuration, loaded from ``MSB_SERVICE_*`` environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the microsandbox service.

    All values are read from environment variables prefixed with
    ``MSB_SERVICE_`` (e.g. ``MSB_SERVICE_PORT=9000``).
    """

    model_config = SettingsConfigDict(env_prefix="MSB_SERVICE_", extra="ignore")

    # network
    host: str = "127.0.0.1"
    port: int = 8000

    # auth -- when unset, the service is unauthenticated (a startup warning is logged)
    api_key: str | None = None

    # sandbox defaults (used when a create request omits them)
    default_image: str = "python"
    default_cpus: int = 1
    default_memory: int = 512  # MiB

    # lifecycle management
    max_sandboxes: int = 50
    idle_ttl_seconds: float = 600.0  # 10m
    # TODO: gc


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
