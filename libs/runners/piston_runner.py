from typing import Any, Iterable

import httpx

from .base import Runner


class PistonRunner(Runner[dict]):
    def __init__(self, host: str, lang: str, version: str, timeout: float = 30.0):
        self.host = host
        self.lang = lang
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

    def _create_payload(self, lang: str, code: str, modules: Iterable[str]) -> dict:
        def _wrap_code(code: str) -> dict:
            return {"content": code}

        return {
            "language": lang,
            "version": self.version,
            "files": [_wrap_code(code), *map(_wrap_code, modules)],
        }
    
    async def _run_with_client(self, client: httpx.AsyncClient, lang: str, code: str, modules: Iterable[str]) -> dict:
        url = f"{self.host}/api/v2/execute"
        payload = self._create_payload(lang, code, modules)
        response = await client.post(url, json=payload)
        response.raise_for_status()
        response = response.json() 
        return response


    async def run(self, lang: str, code: str, modules: Iterable[str]) -> dict:
        if self._aclient is None:
            raise RuntimeError("PistonRunner.run() must be called within an async context manager (use 'async with PistonRunner(...) as runner: ...')")
        return await self._run_with_client(self._aclient, lang, code, modules)
