"""HTTP endpoints mapping onto the microsandbox SDK.

The heavy SDK calls used here mirror those already exercised by the Inspect
sandbox integration: 
``Sandbox.create``
``sandbox.exec`` 
``sandbox.fs.write``
``sandbox.fs.read``
``sandbox.stop``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from microsandbox_service.auth import require_auth
from microsandbox_service.models import (
    CreateSandboxRequest,
    ExecRequest,
    ShellRequest,
    ExecResponse,
    HealthResponse,
    ReadFileRequest,
    ReadFileResponse,
    WriteFileRequest,
    WriteFileResponse,
)
from microsandbox_service.registry import (
    SandboxLimitError,
    SandboxEntry,
    SandboxRegistry,
    get_sandbox_lock,
    to_entry,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_registry(request: Request) -> SandboxRegistry:
    return request.app.state.registry


async def _require_entry(registry: SandboxRegistry, name: str) -> SandboxEntry:
    try:
        handle = await registry.get(name)
        return to_entry(handle)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"sandbox '{name}' execution failed: {e}",
        ) from e


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health(registry: SandboxRegistry = Depends(get_registry)) -> HealthResponse:
    sandbox_count = await registry.count_own()
    return HealthResponse(sandbox_count=sandbox_count)


@router.post(
    "/sandboxes",
    response_model=SandboxEntry,
    status_code=status.HTTP_201_CREATED,
    tags=["sandboxes"],
    dependencies=[Depends(require_auth)],
)
async def create_sandbox(
    body: CreateSandboxRequest,
    registry: SandboxRegistry = Depends(get_registry),
) -> SandboxEntry:
    try:
        handle = await registry.create(
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
    return to_entry(handle)


@router.get(
    "/sandboxes",
    response_model=list[SandboxEntry],
    tags=["sandboxes"],
    dependencies=[Depends(require_auth)],
)
async def list_sandboxes(
    registry: SandboxRegistry = Depends(get_registry),
) -> list[SandboxEntry]:
    return [to_entry(handle) for handle in await registry.list_own()]


@router.get(
    "/sandboxes/{sandbox_id}",
    response_model=SandboxEntry,
    tags=["sandboxes"],
    dependencies=[Depends(require_auth)],
)
async def get_sandbox(
    sandbox_id: str,
    registry: SandboxRegistry = Depends(get_registry),
) -> SandboxEntry:
    handle = await registry.get(sandbox_id)
    return to_entry(handle)


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
    entry = await _require_entry(registry, sandbox_id)
    async with await get_sandbox_lock(entry.name):
        try:
            hd = await registry.get(sandbox_id)
            sb = await hd.connect()
            result = await sb.exec(
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


@router.post(
    "/sandboxes/{sandbox_id}/shell",
    response_model=ExecResponse,
    tags=["exec"],
    dependencies=[Depends(require_auth)],
)
async def shell_command(
    sandbox_id: str,
    body: ShellRequest,
    registry: SandboxRegistry = Depends(get_registry),
) -> ExecResponse:
    entry = await _require_entry(registry, sandbox_id)
    async with await get_sandbox_lock(entry.name):
        try:
            hd = await registry.get(sandbox_id)
            sb = await hd.connect()
            result = await sb.shell(
                body.script,
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
    entry = await _require_entry(registry, sandbox_id)

    async with await get_sandbox_lock(entry.name):
        try:
            data = body.content.encode(body.encoding)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid content: {exc}")        
        
        try:
            hd = await registry.get(sandbox_id)
            sb = await hd.connect()
            await sb.fs.write(body.path, data)
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
    entry = await _require_entry(registry, sandbox_id)

    async with await get_sandbox_lock(entry.name):
        try:
            hd = await registry.get(sandbox_id)
            sb = await hd.connect()
            data = await sb.fs.read(body.path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("read_file failed in sandbox %s", sandbox_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"read failed: {exc}")

        try:
            content = data.decode(body.encoding)
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"decoding error: {exc}")

    return ReadFileResponse(path=body.path, content=content)
