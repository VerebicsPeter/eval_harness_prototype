"""A from-scratch HumanEval implementation that scores inside microsandbox
microVMs via our custom MicrosandboxSandboxEnvironment.

Usage:
    inspect eval humaneval_microvm.py --limit 5 --model <provider/model>
    inspect view
"""

from __future__ import annotations

import gzip
import json
import re
import urllib.request
from typing import Any
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Scorer, Target, accuracy, scorer, stderr
from inspect_ai.solver import TaskState, generate
from inspect_ai.util import ExecResult, sandbox

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs" / "sandboxes"))

# TODO: add setuptools buildstep and use libs.sandboxes.sb_microsandbox instead...
# Importing this registers "microsandbox" with Inspect's sandbox registry
# as a side effect of the @sandboxenv decorator -- no entry point needed.
import sb_microsandbox  # noqa: E402, F401

HUMANEVAL_URL = (
    "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz"
)

INSTRUCTION = (
    "Read the following function signature and docstring, and fully "
    "implement the function described. Respond with ONLY the complete "
    "function (signature + body) inside a single ```python code block -- "
    "no explanation, no extra text.\n\n"
)


# ----------------------------------------------------------------------
# dataset
# ----------------------------------------------------------------------


def _load_humaneval_records() -> list[dict[str, Any]]:
    with urllib.request.urlopen(HUMANEVAL_URL) as resp:  # noqa: S310
        raw = gzip.decompress(resp.read())
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


def record_to_sample(record: dict[str, Any]) -> Sample:
    return Sample(
        id=record["task_id"],
        input=INSTRUCTION + record["prompt"],
        target=record["canonical_solution"],
        metadata={
            "task_id": record["task_id"],
            "prompt": record["prompt"],
            "entry_point": record["entry_point"],
            "test": record["test"],
        },
    )


def humaneval_dataset(limit: int | None = None) -> MemoryDataset:
    records = _load_humaneval_records()
    if limit is not None:
        records = records[:limit]
    return MemoryDataset(samples=[record_to_sample(r) for r in records], name="humaneval")


# ----------------------------------------------------------------------
# scorer: run the model's code + the official test suite in the microVM
# ----------------------------------------------------------------------


def _extract_code(completion: str) -> str:
    """Pull code out of a ```python fenced block; fall back to raw text."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", completion, re.DOTALL)
    return match.group(1) if match else completion


@scorer(metrics=[accuracy(), stderr()])
def microvm_test_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        completion = _extract_code(state.output.completion)
        test_code = state.metadata["test"]
        entry_point = state.metadata["entry_point"]

        program = "\n\n".join([completion, test_code, f"check({entry_point})"])

        await sandbox().write_file("test_solution.py", program)
        result: ExecResult[str] = await sandbox().exec(
            ["python3", "test_solution.py"], timeout=30
        )

        return Score(
            value="C" if result.success else "I",
            answer=completion,
            explanation="all tests passed" if result.success else result.stderr,
        )

    return score


# ----------------------------------------------------------------------
# task
# ----------------------------------------------------------------------


@task
def humaneval_microvm(limit: int | None = 5) -> Task:
    """HumanEval, scored inside microsandbox microVMs.

    Args:
        limit: Number of problems to include (None for the full 164).
               Note: `inspect eval ... --limit N` also works and composes
               with this -- whichever is smaller wins.
    """
    return Task(
        dataset=humaneval_dataset(limit=limit),
        solver=[generate()],
        scorer=microvm_test_scorer(),
        sandbox="microsandbox",
    )
