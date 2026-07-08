"""A light FastAPI wrapper around the microsandbox SDK.

Exposes microsandbox's stateful microVM lifecycle (create, exec, file I/O,
destroy) over HTTP so networked training loops can drive sandboxes remotely.
This is intentionally thin -- it does not reimplement the microsandbox runtime;
it only adds an in-process registry of live ``Sandbox`` handles, HTTP endpoints,
optional bearer-token auth, and idle cleanup on top of the bundled SDK.
"""

from microsandbox_service.app import create_app
from microsandbox_service.config import Settings, get_settings

__all__ = ["create_app", "Settings", "get_settings"]
