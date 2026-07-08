"""In-process registry of live microsandbox handles.

The service is stateful: a client creates a sandbox, receives an id, and then
issues many exec/file calls against that id before destroying it. Because the
``Sandbox`` objects returned by the SDK are live handles bound to this process,
they are kept in a module-level registry. This implies the service must run as a
single worker (see the README).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from microsandbox_service.config import Settings

logger = logging.getLogger(__name__)

# A factory that creates and starts a sandbox handle. Injectable for testing.
SandboxFactory = Callable[..., Awaitable[Any]]


class SandboxLimitError(RuntimeError):
    """Raised when the configured maximum number of sandboxes is reached."""


async def _default_sandbox_factory(
    name: str, image: str, cpus: int, memory: int
) -> Any:
    """Create a real microsandbox microVM. Imported lazily to keep this module
    importable (and unit-testable) without the microsandbox runtime present."""
    from microsandbox import Sandbox

    return await Sandbox.create(
        name,
        image=image,
        cpus=cpus,
        memory=memory,
        replace=True,
    )


@dataclass
class SandboxEntry:
    """A live sandbox handle plus its metadata and per-sandbox lock."""

    id: str
    name: str
    sandbox: Any
    image: str
    cpus: int
    memory: int
    created_at: float
    last_used: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def touch(self) -> None:
        self.last_used = time.monotonic()


class SandboxRegistry:
    """Manages the lifecycle of live sandbox handles."""

    def __init__(
        self,
        settings: Settings,
        sandbox_factory: SandboxFactory | None = None,
    ) -> None:
        self._settings = settings
        self._factory = sandbox_factory or _default_sandbox_factory
        self._entries: dict[str, SandboxEntry] = {}
        self._lock = asyncio.Lock()
        self._reaper_task: asyncio.Task[None] | None = None

    # ---------- lifecycle ----------

    async def create(
        self,
        image: str | None = None,
        cpus: int | None = None,
        memory: int | None = None,
        name: str | None = None,
    ) -> SandboxEntry:
        image = image or self._settings.default_image
        cpus = cpus or self._settings.default_cpus
        memory = memory or self._settings.default_memory

        async with self._lock:
            if len(self._entries) >= self._settings.max_sandboxes:
                raise SandboxLimitError(
                    f"maximum number of sandboxes ({self._settings.max_sandboxes}) reached"
                )
            sandbox_id = uuid.uuid4().hex
            # microsandbox names are used as VM identifiers; keep them short/unique.
            sandbox_name = (name or f"msb-svc-{sandbox_id}")[:64]

        sandbox = await self._factory(
            name=sandbox_name, image=image, cpus=cpus, memory=memory
        )

        now = time.monotonic()
        entry = SandboxEntry(
            id=sandbox_id,
            name=sandbox_name,
            sandbox=sandbox,
            image=image,
            cpus=cpus,
            memory=memory,
            created_at=now,
            last_used=now,
        )
        async with self._lock:
            self._entries[sandbox_id] = entry
        logger.info("created sandbox %s (name=%s, image=%s)", sandbox_id, sandbox_name, image)
        return entry

    def get(self, sandbox_id: str) -> SandboxEntry:
        """Return the entry for ``sandbox_id`` or raise ``KeyError``."""
        entry = self._entries.get(sandbox_id)
        if entry is None:
            raise KeyError(sandbox_id)
        entry.touch()
        return entry

    def list(self) -> list[SandboxEntry]:
        return list(self._entries.values())

    def count(self) -> int:
        return len(self._entries)

    async def remove(self, sandbox_id: str) -> None:
        """Stop and forget a sandbox. Raises ``KeyError`` if unknown."""
        async with self._lock:
            entry = self._entries.pop(sandbox_id, None)
        if entry is None:
            raise KeyError(sandbox_id)
        await self._stop_entry(entry)

    async def remove_all(self) -> None:
        """Stop and forget every sandbox (used on shutdown)."""
        async with self._lock:
            entries = list(self._entries.values())
            self._entries.clear()
        for entry in entries:
            await self._stop_entry(entry)

    # NOTE: (IMPORTANT)
    # This does NOT remove named VMs, only stops them,
    # named VM state is accumulated on disk and not cleaned,
    # we should add a way to clean up VM state.
    # You can see the current VMs this by running `msb ls`.
    # TODO: check if unnamed sandboxes are cleaned up!!!
    async def _stop_entry(self, entry: SandboxEntry) -> None:
        try:
            await entry.sandbox.stop()
            logger.info("stopped sandbox %s", entry.id)
        except Exception:  # noqa: BLE001 - never fail teardown on SDK errors
            logger.exception("error stopping sandbox %s", entry.id)

    # ---------- idle reaper ----------

    def start_reaper(self) -> None:
        if self._reaper_task is None:
            self._reaper_task = asyncio.create_task(self._reap_loop())

    async def stop_reaper(self) -> None:
        if self._reaper_task is not None:
            self._reaper_task.cancel()
            try:
                await self._reaper_task
            except asyncio.CancelledError:
                pass
            self._reaper_task = None

    async def _reap_loop(self) -> None:
        interval = self._settings.reaper_interval_seconds
        while True:
            try:
                await asyncio.sleep(interval)
                await self._reap_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - keep the reaper alive
                logger.exception("error during idle sandbox reaping")

    async def _reap_once(self) -> None:
        ttl = self._settings.idle_ttl_seconds
        now = time.monotonic()
        async with self._lock:
            expired = [
                entry
                for entry in self._entries.values()
                if now - entry.last_used > ttl
            ]
            for entry in expired:
                del self._entries[entry.id]
        for entry in expired:
            logger.info("reaping idle sandbox %s (idle for %.0fs)", entry.id, now - entry.last_used)
            await self._stop_entry(entry)
