"""Request/response schemas for the microsandbox service API."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class FileEncoding(str, Enum):
    """How file ``content`` is represented in JSON.

    - ``utf-8``: ``content`` is a plain (UTF-8 decodable) string.
    - ``base64``: ``content`` is base64-encoded bytes (use for binary files).
    """

    utf8 = "utf-8"
    base64 = "base64"


class HealthResponse(BaseModel):
    status: str = "ok"
    sandbox_count: int


class CreateSandboxRequest(BaseModel):
    image: str | None = Field(default=None, description="OCI image; defaults to the server default")
    cpus: int | None = Field(default=None, ge=1)
    memory: int | None = Field(default=None, ge=1, description="Memory in MiB")
    name: str | None = Field(default=None, description="Optional sandbox name (otherwise auto-generated)")


class SandboxInfo(BaseModel):
    id: str
    name: str
    image: str
    cpus: int
    memory: int
    created_at: float = Field(description="Creation time (monotonic clock seconds)")
    last_used: float = Field(description="Last activity time (monotonic clock seconds)")


class ExecRequest(BaseModel):
    cmd: list[str] = Field(min_length=1, description="Command and arguments, e.g. ['python3', '-c', 'print(1)']")
    cwd: str | None = None
    env: dict[str, str] | None = None
    timeout: int | None = Field(default=None, ge=1, description="Timeout in seconds")


class ExecResponse(BaseModel):
    success: bool
    returncode: int
    stdout: str
    stderr: str


class WriteFileRequest(BaseModel):
    path: str
    content: str
    encoding: FileEncoding = FileEncoding.utf8


class WriteFileResponse(BaseModel):
    path: str
    bytes_written: int


class ReadFileRequest(BaseModel):
    path: str
    encoding: FileEncoding = FileEncoding.utf8


class ReadFileResponse(BaseModel):
    path: str
    content: str
    encoding: FileEncoding


class ErrorResponse(BaseModel):
    detail: str
