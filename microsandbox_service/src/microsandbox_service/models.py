"""Request/response schemas for the microsandbox service API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    sandbox_count: int


class CreateSandboxRequest(BaseModel):
    image: str | None = Field(default=None, description="OCI image; defaults to the server default")
    cpus: int | None = Field(default=None, ge=1)
    memory: int | None = Field(default=None, ge=1, description="Memory in MiB")
    name: str | None = Field(default=None, description="Optional sandbox name (otherwise auto-generated)")


class ExecRequest(BaseModel):
    cmd: list[str] = Field(min_length=1, description="Command and arguments, e.g. ['python3', '-c', 'print(1)']")
    cwd: str | None = None
    env: dict[str, str] | None = None
    timeout: int | None = Field(default=None, ge=1, description="Timeout in seconds")


class ShellRequest(BaseModel):
    script: str = Field(min_length=1, description="Shell command string, e.g. 'ls -la'")
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
    encoding: str = "utf-8"


class WriteFileResponse(BaseModel):
    path: str
    bytes_written: int


class ReadFileRequest(BaseModel):
    path: str
    encoding: str = "utf-8"


class ReadFileResponse(BaseModel):
    path: str
    content: str


class ErrorResponse(BaseModel):
    detail: str

