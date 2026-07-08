"""HTTP endpoints mapping onto the microsandbox SDK.

The heavy SDK calls used here mirror those already exercised by the Inspect
sandbox integration: ``Sandbox.create`` / ``sandbox.exec`` / ``sandbox.fs.write``
/ ``sandbox.fs.read`` / ``sandbox.stop``.
"""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from microsandbox_service.auth import require_auth
from microsandbox_service.models import (
    CreateSandboxRequest,
    ExecRequest,
    ExecResponse,
    FileEncoding,
    HealthResponse,
    ReadFileRequest,
    ReadFileResponse,
    SandboxInfo,
    WriteFileRequest,
    WriteFileResponse,
)
from microsandbox_service.registry import (
    SandboxEntry,
    SandboxLimitError,
    SandboxRegistry,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_registry(request: Request) -> SandboxRegistry:
    return request.app.state.registry


def _to_info(entry: SandboxEntry) -> SandboxInfo:
    return SandboxInfo(
        id=entry.id,
        name=entry.name,
        image=entry.image,
        cpus=entry.cpus,
        memory=entry.memory,
        created_at=entry.created_at,
        last_used=entry.last_used,
    )


def _require_entry(registry: SandboxRegistry, sandbox_id: str) -> SandboxEntry:
    try:
        return registry.get(sandbox_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"sandbox '{sandbox_id}' not found",
        )


# ---------- health (no auth) ----------


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health(registry: SandboxRegistry = Depends(get_registry)) -> HealthResponse:
    return HealthResponse(sandbox_count=registry.count())


# ---------- sandbox lifecycle ----------


@router.post(
    "/sandboxes",
    response_model=SandboxInfo,
    status_code=status.HTTP_201_CREATED,
    tags=["sandboxes"],
    dependencies=[Depends(require_auth)],
)
async def create_sandbox(
    body: CreateSandboxRequest,
    registry: SandboxRegistry = Depends(get_registry),
) -> SandboxInfo:
    try:
        entry = await registry.create(
            image=body.image,
            cpus=body.cpus,
            memory=body.memory,
            name=body.name,
        )
    except SandboxLimitError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - surface SDK failures as 502
        logger.exception("failed to create sandbox")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"failed to create sandbox: {exc}")
    return _to_info(entry)


@router.get(
    "/sandboxes",
    response_model=list[SandboxInfo],
    tags=["sandboxes"],
    dependencies=[Depends(require_auth)],
)
async def list_sandboxes(
    registry: SandboxRegistry = Depends(get_registry),
) -> list[SandboxInfo]:
    return [_to_info(entry) for entry in registry.list()]


@router.get(
    "/sandboxes/{sandbox_id}",
    response_model=SandboxInfo,
    tags=["sandboxes"],
    dependencies=[Depends(require_auth)],
)
async def get_sandbox(
    sandbox_id: str,
    registry: SandboxRegistry = Depends(get_registry),
) -> SandboxInfo:
    return _to_info(_require_entry(registry, sandbox_id))


@router.delete(
    "/sandboxes/{sandbox_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["sandboxes"],
    dependencies=[Depends(require_auth)],
)
async def delete_sandbox(
    sandbox_id: str,
    registry: SandboxRegistry = Depends(get_registry),
) -> Response:
    try:
        await registry.remove(sandbox_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"sandbox '{sandbox_id}' not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- execution ----------


@router.post(
    "/sandboxes/{sandbox_id}/exec",
    response_model=ExecResponse,
    tags=["exec"],
    dependencies=[Depends(require_auth)],
)
async def exec_command(
    sandbox_id: str,
    body: ExecRequest,
    registry: SandboxRegistry = Depends(get_registry),
) -> ExecResponse:
    entry = _require_entry(registry, sandbox_id)
    async with entry.lock:
        try:
            result = await entry.sandbox.exec(
                body.cmd[0],
                body.cmd[1:],
                cwd=body.cwd,
                env=body.env,
                timeout=float(body.timeout) if body.timeout else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("exec failed in sandbox %s", sandbox_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"exec failed: {exc}")
    return ExecResponse(
        success=result.exit_code == 0,
        returncode=result.exit_code,
        stdout=result.stdout_text,
        stderr=result.stderr_text,
    )


# ---------- file I/O ----------


@router.post(
    "/sandboxes/{sandbox_id}/files/write",
    response_model=WriteFileResponse,
    tags=["files"],
    dependencies=[Depends(require_auth)],
)
async def write_file(
    sandbox_id: str,
    body: WriteFileRequest,
    registry: SandboxRegistry = Depends(get_registry),
) -> WriteFileResponse:
    entry = _require_entry(registry, sandbox_id)

    if body.encoding is FileEncoding.base64:
        try:
            # binascii.Error (raised on malformed input) subclasses ValueError.
            data = base64.b64decode(body.content, validate=True)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid base64 content: {exc}")
    else:
        data = body.content.encode("utf-8")

    async with entry.lock:
        try:
            await entry.sandbox.fs.write(body.path, data)
        except Exception as exc:  # noqa: BLE001
            logger.exception("write_file failed in sandbox %s", sandbox_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"write failed: {exc}")

    return WriteFileResponse(path=body.path, bytes_written=len(data))


@router.post(
    "/sandboxes/{sandbox_id}/files/read",
    response_model=ReadFileResponse,
    tags=["files"],
    dependencies=[Depends(require_auth)],
)
async def read_file(
    sandbox_id: str,
    body: ReadFileRequest,
    registry: SandboxRegistry = Depends(get_registry),
) -> ReadFileResponse:
    entry = _require_entry(registry, sandbox_id)

    async with entry.lock:
        try:
            data = await entry.sandbox.fs.read(body.path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("read_file failed in sandbox %s", sandbox_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"read failed: {exc}")

    # The SDK returns bytes; some builds may return str for text reads.
    if isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = data

    if body.encoding is FileEncoding.base64:
        content = base64.b64encode(raw).decode("ascii")
    else:
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"file is not valid UTF-8; request encoding='base64' instead ({exc})",
            )

    return ReadFileResponse(path=body.path, content=content, encoding=body.encoding)
