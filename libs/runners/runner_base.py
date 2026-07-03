from pydantic import BaseModel
from typing import Any, Iterable, Protocol, TypeVar

type_T = TypeVar("type_T", covariant=True)


class RunnerMetadata(BaseModel):
    language: str
    runtime: str  # language runtime (eg. python3.10, nodejsxx, etc.)
    backend: str
    timeout: float  # timeout in seconds


class Runner(Protocol[type_T]):
    async def __aenter__(self) -> "Runner[type_T]":
        ...

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        ...

    async def aclose(self) -> None:
        ...

    async def run(self, code: str, modules: Iterable[str]) -> type_T:
        ...
    
    def get_manifest_metadata(self) -> RunnerMetadata:
        ...
