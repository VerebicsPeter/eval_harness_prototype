from typing import Any, Iterable, Protocol, TypeVar

type_T = TypeVar("type_T", covariant=True)


class Runner(Protocol[type_T]):
    async def __aenter__(self) -> "Runner[type_T]":
        ...

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        ...

    async def aclose(self) -> None:
        ...

    async def run(self, lang: str, code: str, modules: Iterable[str]) -> type_T:
        ...
