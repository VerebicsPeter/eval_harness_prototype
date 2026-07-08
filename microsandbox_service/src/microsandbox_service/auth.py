"""Optional bearer-token authentication.

If ``MSB_SERVICE_API_KEY`` is set, every route that depends on
``require_auth`` must present ``Authorization: Bearer <key>``. If it is unset,
the dependency is a no-op (and a warning is logged at startup) so local/trusted
deployments work without configuration. ``/health`` never depends on this.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Request, status

from microsandbox_service.config import get_settings


async def require_auth(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """FastAPI dependency enforcing bearer-token auth when a key is configured.

    Reads settings from ``app.state`` (populated at startup by ``create_app``)
    so that per-app overrides -- including those injected in tests -- are
    honored, rather than the process-wide env-derived settings.
    """
    settings = getattr(request.app.state, "settings", None) or get_settings()
    expected = settings.api_key
    if not expected:
        # Unauthenticated mode -- allow all requests.
        return

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header; expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Constant-time comparison to avoid leaking the key via timing.
    if not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
