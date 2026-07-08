from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from pydantic import BaseModel, Field
from typing import Any

from microsandbox import Sandbox, SandboxHandle
from microsandbox_service.config import Settings

logger = logging.getLogger(__name__)

# A factory that creates and starts a sandbox handle. Injectable for testing.
SandboxFactory = Callable[..., Awaitable[Sandbox]]

_creator_lock = asyncio.Lock()
_sandbox_locks: dict[str, asyncio.Lock] = {}
_sandbox_cache: dict[str, Sandbox] = {}  # this is needed to keep the sandboxes running

async def get_sandbox_lock(sandbox_id: str) -> asyncio.Lock:
    # Fast path: most requests just read the dict
    if sandbox_id in _sandbox_locks:
        return _sandbox_locks[sandbox_id]

    # Slow path: create the lock safely
    async with _creator_lock:
        # Double-check: another task might have created it while we waited
        if sandbox_id in _sandbox_locks:
            return _sandbox_locks[sandbox_id]
        
        lock = asyncio.Lock()
        _sandbox_locks[sandbox_id] = lock
        return lock


class SandboxLimitError(RuntimeError):
    """Raised when the configured maximum number"""


class SandboxEntry(BaseModel):
    """A live sandbox handle plus its metadata and per-sandbox lock."""
    name: str
    status: str
    config_json: str
    created_at: float
    updated_at: float


def to_entry(sb: SandboxHandle) -> SandboxEntry:
    return SandboxEntry(
        name=sb.name,
        status=sb.status,
        config_json=sb.config_json,
        created_at=sb.created_at or 0.0,
        updated_at=sb.updated_at or 0.0,
    )


def get_label(sb: SandboxHandle, key: str) -> Any:
    try:
        labels = sb.config().get("labels", {})
        return labels.get(key)
    except Exception as e:
        raise ValueError(f"Cannot get label: {e}") from e


async def _default_sandbox_factory(
    name: str,
    image: str,
    cpus: int,
    memory: int,
    namespace: str
) -> Sandbox:
    """Create a real microsandbox microVM. Imported lazily to keep this module
    importable (and unit-testable) without the microsandbox runtime present."""

    return await Sandbox.create(
        name,
        image=image,
        cpus=cpus,
        memory=memory,
        replace=True,
        labels={"namespace": namespace}
    )


class SandboxRegistry:
    """Manages the lifecycle of live sandbox handles."""
    # NOTE: The creator OWNS the sandboxes, and IS responsible for cleaning them up
    
    def __init__(
        self,
        settings: Settings,
        namespace:str="base"
    ) -> None:
        self._settings = settings
        self._namespace = namespace
    
    # NOTE: Conventions:
    # - DO NOT start names with msb-svc
    # - DO NOT use the 'namespace' label
    def owns(self, sb: SandboxHandle) -> bool:
        return (sb.name.startswith("msb-svc-") and self._namespace == get_label(sb, "namespace"))

    async def create(
        self,
        image: str | None = None,
        cpus: int | None = None,
        memory: int | None = None,
        name: str | None = None,
    ) -> SandboxHandle:
        image = image or self._settings.default_image
        cpus = cpus or self._settings.default_cpus
        memory = memory or self._settings.default_memory

        
        limit = self._settings.max_sandboxes
        count = await self.count_own()
        if count >= limit:
            raise SandboxLimitError(f"Cannot create: Max sandbox count exceeded: (limit={limit}, count={count})")
        
        # microsandbox names are used as VM identifiers; keep them short/unique.
        sandbox_name = (f"msb-svc-{name or uuid.uuid4().hex}")[:64]

        sandbox_inst = await _default_sandbox_factory(
            name=sandbox_name,
            image=image,
            cpus=cpus,
            memory=memory,
            namespace=self._namespace
        )
        
        _sandbox_cache[sandbox_name] = sandbox_inst

        sb = await Sandbox.get(sandbox_name)  # handle
        
        logger.info("created sandbox (name=%s, image=%s)", sandbox_name, image)
        return sb

    async def get(self, name: str) -> SandboxHandle:
        """Return the entry for ``sandbox_id`` or raise ``KeyError``."""
        sb = await Sandbox.get(name)
        __ = await sb.touch()
        return sb

    async def list_all(self) -> list[SandboxHandle]:
        sbs = await Sandbox.list()
        return sbs

    async def list_own(self) -> list[SandboxHandle]:
        sbs = await Sandbox.list()
        sbs = list(filter(self.owns, sbs))
        return sbs
    
    async def count_all(self) -> int:
        return len(await self.list_all())
    
    async def count_own(self) -> int:
        return len(await self.list_own())

    async def remove(self, name: str) -> None:
        """Delete a sandbox"""
        # NOTE: (TODO) think about if we need to aquire the lock here
        # NOTE: (TODO) think about the case where the vm is detached 
        try:
            sb = await Sandbox.get(name)
            await sb.stop(timeout=3.0)
            await sb.wait_until_stopped()
            await sb.remove()
            # we also invalidate the cache to avoid use after free
            if name in _sandbox_cache: del _sandbox_cache[name]
        except Exception as e:
            raise ValueError(f"Error while deleting sandbox:\n{e}") from e
        
    async def remove_own(self) -> None:
        """Delete all sandboxes created by service (used on shutdown)."""
        try:
            sbs = await self.list_own()
            for sb in sbs: await self.remove(sb.name)
            logger.info("Sandboxes cleaned up")
        except Exception as e:
            msg = f"Error while deleting sandboxes:\n{e}"
            logger.error(msg)
            raise ValueError(msg) from e
