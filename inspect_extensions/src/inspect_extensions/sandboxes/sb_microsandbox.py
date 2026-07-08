from typing import Literal, overload
from pydantic import BaseModel

class MicrosandboxConfig(BaseModel, frozen=True):
    image: str = "python"
    cpus: int = 1
    memory: int = 512  # MiB

from inspect_ai.util import (
    SandboxEnvironment,
    SandboxEnvironmentConfigType,
    sandboxenv,
)
from inspect_ai.util import ExecResult
from microsandbox import Sandbox

@sandboxenv(name="microsandbox")
class MicrosandboxSandboxEnvironment(SandboxEnvironment):

    def __init__(self, sandbox: Sandbox):
        self._sandbox = sandbox

    # ---------- lifecycle (classmethods) ----------

    @classmethod
    def config_files(cls) -> list[str]:
        # We only support configuration via MicrosandboxConfig (passed through a
        # SandboxEnvironmentSpec), not a default config file on disk. Returning
        # an empty list keeps this consistent with _resolve_config(), which
        # rejects file-path configs.
        return []

    @classmethod
    def is_docker_compatible(cls) -> bool:
        return False  # not compose/Dockerfile driven

    @classmethod
    def default_concurrency(cls) -> int | None:
        return None  # microVMs are cheap; let Inspect's own limits govern

    @classmethod
    async def task_init(
        cls, task_name: str, config: SandboxEnvironmentConfigType | None
    ) -> None:
        # good place to pre-pull the image once per unique config
        cfg = cls._resolve_config(config)
        # microsandbox pulls lazily on first create(); you could
        # warm the cache here with a throwaway create()/stop().
        pass

    @classmethod
    async def sample_init(
        cls,
        task_name: str,
        config: SandboxEnvironmentConfigType | None,
        metadata: dict[str, str],
    ) -> dict[str, SandboxEnvironment]:
        cfg = cls._resolve_config(config)
        # NOTE: we create a sandbox from a sample:
        # the inspect sample id is stored in the
        # `__sample_id__` field of the metadata record
        sample_id = metadata.get('__sample_id__', 'x').replace('/', '-')  # only alfanumeric
        name = f"inspect-{task_name}-{sample_id}"[:64]  # limit length
        sb = await Sandbox.create(
            name,
            image=cfg.image,
            cpus=cfg.cpus,
            memory=cfg.memory,
            replace=True,
        )
        # first entry in the dict is treated as "default"
        return {"default": cls(sb)}

    @classmethod
    async def sample_cleanup(
        cls,
        task_name: str,
        config: SandboxEnvironmentConfigType | None,
        environments: dict[str, SandboxEnvironment],
        interrupted: bool,
    ) -> None:
        for env in environments.values():
            assert isinstance(env, cls)
            try:
                await env._sandbox.stop()
            except Exception:
                pass  # don't fail the sample on teardown errors

    @classmethod
    async def task_cleanup(
        cls,
        task_name: str,
        config: SandboxEnvironmentConfigType | None,
        cleanup: bool,
    ) -> None:
        # last-resort sweep; microsandbox has no shared daemon state
        # to reap the way Docker does, so usually nothing to do here
        pass

    @classmethod
    async def cli_cleanup(cls, id: str | None) -> None:
        # backs `inspect sandbox cleanup microsandbox [id]`
        pass

    @staticmethod
    def _resolve_config(
        config: SandboxEnvironmentConfigType | None,
    ) -> MicrosandboxConfig:
        if config is None:
            return MicrosandboxConfig()
        if isinstance(config, MicrosandboxConfig):
            return config
        raise ValueError(f"Unsupported config type: {type(config)}")

    # ---------- instance methods ----------

    async def exec(
        self,
        cmd: list[str],
        input: str | bytes | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        user: str | None = None,
        timeout: int | None = None,
        timeout_retry: bool = True,
    ) -> ExecResult[str]:
        # microsandbox's collected exec() has no stdin channel; piping input
        # requires the streaming exec_stream() + Stdin.pipe() API. Rather than
        # silently discarding stdin (which produces wrong results), fail loudly
        # until that path is implemented.
        if input is not None:
            raise NotImplementedError(
                "MicrosandboxSandboxEnvironment.exec() does not support the "
                "`input` (stdin) argument yet; implement it via "
                "microsandbox's exec_stream() + Stdin.pipe()."
            )
        # `user` and `timeout_retry` are part of the Inspect contract but have no
        # microsandbox equivalent, so they are intentionally ignored here.
        result = await self._sandbox.exec(
            cmd[0],
            cmd[1:],
            cwd=cwd,
            env=env,
            timeout=float(timeout) if timeout else None,
        )
        return ExecResult(
            success=result.exit_code == 0,
            returncode=result.exit_code,
            stdout=result.stdout_text,
            stderr=result.stderr_text,
        )

    async def write_file(self, file: str, contents: str | bytes) -> None:
        if isinstance(contents, str):
            contents = contents.encode(encoding="utf-8")
        await self._sandbox.fs.write(file, contents)

    @overload
    async def read_file(self, file: str, text: Literal[True] = True) -> str: ...
    @overload
    async def read_file(self, file: str, text: Literal[False]) -> bytes: ...

    async def read_file(self, file: str, text: bool = True) -> str | bytes:
        data = await self._sandbox.fs.read(file)  # bytes
        if text:
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError as e:
                raise UnicodeDecodeError(*e.args) from e
        return data
