from __future__ import annotations

import inspect
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from libs.loaders.dataloaders import HuggingFaceDatasetLoader
from libs.manifest import Manifest, ManifestMetadata, ManifestMetadataSource
from libs.runners.base import Runner


class HumanEvalBenchmark:
    def __init__(
        self,
        loader: Callable[[], Iterable[dict[str, Any]]] | None = None,
        llm_client: Any | None = None,
        runner: Runner[Any] | None = None,
        limit: int = 5,
    ) -> None:
        self.loader = loader
        self.llm_client = llm_client
        self.runner = runner
        self.limit = limit

    def load_tasks(self) -> list[dict[str, Any]]:
        loaded = self._load_rows()
        return [self._hydrate_task(row) for row in loaded]

    def _load_rows(self) -> Iterable[dict[str, Any]]:
        if self.loader is None:
            return HuggingFaceDatasetLoader("openai/openai_humaneval", split="test", limit=self.limit).load()

        if callable(self.loader):
            return self.loader()

        raise TypeError("Loader must be callable or provide a load() method")

    async def complete_tasks(self, tasks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.llm_client is None:
            raise ValueError("An llm_client instance is required to complete tasks")

        completed = []
        for task in tasks:
            completion = self.llm_client.complete(task["prompt"])
            if inspect.isawaitable(completion):
                completion = await completion
            completed.append({**task, "completion": completion, "prompt+completion": f"{task['prompt']}\n\n{completion}"})
        return completed

    def build_submission(self, task: dict[str, Any], completion: str) -> str:
        test_harness = task.get("test") or ""
        if not isinstance(test_harness, str) or not test_harness.strip():
            return completion

        entry_point = task.get("entry_point")
        if entry_point is None:
            raise ValueError("HumanEval tasks require an entry_point to build submissions")

        return "\n\n".join(
            [
                completion.rstrip(),
                test_harness.rstrip(),
                f"\ncheck({entry_point})",
            ]
        )

    async def run_submissions(self, tasks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.runner is None:
            raise ValueError("A runner instance is required to execute submissions")

        results = []
        async with self.runner as runner:
            for task in tasks:
                completion = task.get("prompt+completion")
                if not isinstance(completion, str):
                    raise ValueError("Each task must contain a completion string before execution")

                submission = self.build_submission(task, completion)
                payload = await runner.run("python", submission, [])
                results.append({**task, "submission": submission, "result": payload})
        return results

    async def run(self, manifest_path: str | None = None) -> dict[str, Any]:
        if self.llm_client is None:
            raise ValueError("An llm_client instance is required to run the benchmark")

        tasks = self.load_tasks()
        completed_tasks = await self.complete_tasks(tasks)
        results = await self.run_submissions(completed_tasks)
        manifest = self.build_manifest()

        if manifest_path is not None:
            output_path = Path(manifest_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return {"tasks": tasks, "results": results, "manifest": manifest}

    def build_manifest(self) -> dict[str, Any]:
        metadata = self._collect_manifest_metadata()
        manifest = Manifest(
            run_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            benchmark={"name": "HumanEval", "url": "https://github.com/openai/human-eval"},
            target_model=metadata.target_model or {"name": None, "url": None},
            inference_provider=metadata.inference_provider,
            temperature=metadata.temperature,
            api_provider=metadata.api_provider,
            api_endpoint=metadata.api_endpoint,
            system_fingerprint=None,
        )
        return manifest.model_dump(mode="json")

    def _collect_manifest_metadata(self) -> ManifestMetadata:
        metadata = ManifestMetadata()
        for dependency in (self.llm_client, self.runner, self.loader):
            if dependency is None:
                continue

            if isinstance(dependency, ManifestMetadataSource):
                dependency_metadata = dependency.get_manifest_metadata()
                metadata = metadata.model_copy(update=dependency_metadata.model_dump(exclude_none=True))

        return metadata

    def _hydrate_task(self, row: dict[str, Any]) -> dict[str, Any]:
        prompt = row.get("prompt")
        if not isinstance(prompt, str):
            raise ValueError(f"Expected a HumanEval prompt string, got: {row!r}")

        return {
            "prompt": self._build_prompt(prompt),
            "task_id": row.get("task_id"),
            "entry_point": row.get("entry_point"),
            "canonical_solution": row.get("canonical_solution"),
            "test": row.get("test"),
            "raw": row,
        }

    def _build_prompt(self, prompt: str) -> str:
        return (
            "#You are solving a Python coding task from the HumanEval benchmark. "
            "Return only the RAW implementation for the requested function (raw source code inside the function scope, after the signature, NO MD formatting!, RAW code)\n\n"
            f"{prompt}"
        )
