import asyncio
from contextlib import nullcontext
from typing import Any, Iterable
from pydantic import BaseModel

from libs.loaders import Loader
from libs.clients import LLMClient
from libs.runners import Runner
from libs.utils import validate_stream


class HumanEvalData(BaseModel):
    task_id: str
    prompt: str
    canonical_solution: str
    test: str
    entry_point: str


def he_load_tasks(loader: Loader[dict]):
    # NOTE: we could check if all pass in validate stream but that is 2N...
    yield from validate_stream(loader.load(), HumanEvalData)


async def he_solve_task(item: HumanEvalData,
                        client: LLMClient,
                        runner: Runner[dict],
                        sem: asyncio.Semaphore | None = None) -> dict:
    ctx = sem if sem is not None else nullcontext()
    async with ctx:
        sysmsg=(
            "#You are solving a Python coding task from the HumanEval benchmark. "
            "Return only the RAW implementation for the requested function: "
            "raw source code inside function scope, "
            "after the signature, NO MD formatting, "
            "RAW correctly indented, working python code\n\n"
        )
        prompt = f"{sysmsg}\n{item.prompt}"
        completion = await client.complete(prompt)
        submission = "\n\n".join(
            [
                item.prompt.rstrip(),
                completion.rstrip(),
                item.test.rstrip(),
                f"check({item.entry_point})",
            ]
        )
        result = await runner.run(submission, [])  # 2nd param is extra modules...
        return {
            **item.model_dump(),
            "prompt_full": prompt,
            "completion": completion,
            "submission": submission,
            "result": result
        }


async def he_solve_tasks(stream: Iterable[HumanEvalData],
                         client: LLMClient,
                         runner: Runner[dict],
                         max_coros=4):
    sem = asyncio.Semaphore(max_coros) if max_coros>1 else None
    # NOTE: there must be a way to stream the result of this as well...
    tasks = [he_solve_task(item, client, runner, sem) for item in stream]
    results = await asyncio.gather(*tasks)  # TODO: semaphore
    return results


# TODO: will run in example for now, we still have to build the factories, some helpers etc...
def run(): pass


__all__ = [
    "HumanEvalData",
    "he_load_tasks",
    "he_solve_task",
    "he_solve_tasks",
]
