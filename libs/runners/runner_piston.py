from typing import Any, Iterable

import httpx

from libs.runners.runner_base import Runner, RunnerMetadata


class PistonRunner(Runner[dict]):
    def __init__(self, host: str, language: str, version: str, timeout: float = 30.0):
        self.host = host
        self.language = language
        self.version = version
        self.timeout = timeout
        self._aclient: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "PistonRunner":
        self._aclient = httpx.AsyncClient(base_url=self.host, timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._aclient is not None:
            await self._aclient.aclose()
            self._aclient = None
    
    async def _run_with_client(self, client: httpx.AsyncClient, code: str, modules: Iterable[str]) -> dict:
        def _wrap_code(code: str) -> dict:
            return {"content": code}
        
        def _create_payload(code: str, modules: Iterable[str]) -> dict:
            return {
                "language": self.language,
                "version": self.version,
                "files": [_wrap_code(code), *map(_wrap_code, modules)],
            }
        
        url = f"{self.host}/api/v2/execute"
        payload = _create_payload(code, modules)
        response = await client.post(url, json=payload)
        response.raise_for_status()
        response = response.json() 
        return response

    async def run(self, code: str, modules: Iterable[str]) -> dict:
        if self._aclient is None:
            raise RuntimeError("PistonRunner.run() must be called within an async context manager (use 'async with PistonRunner(...) as runner: ...')")
        return await self._run_with_client(self._aclient, code, modules)

    def get_manifest_metadata(self) -> RunnerMetadata:
        return RunnerMetadata(
            language=self.language,
            runtime=f"{self.language}::{self.version}",
            backend="piston",
            timeout=self.timeout,
        )
