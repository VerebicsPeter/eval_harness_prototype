import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

import uuid
import json
from datetime import datetime

from libs.manifest import Manifest
from libs.clients.llm_clients import GoogleAIStudioClient
from libs.loaders import HuggingFaceDatasetLoader
from libs.runners import PistonRunner
from benchmarks.humaneval import *

load_dotenv(".env")


# TODO: add factories for generic, declarative instantiation
async def run_humaneval_benchmark() -> None:
    DUMP_DIR = Path("tests/dumps")
    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    
    client = GoogleAIStudioClient(api_key=os.getenv("GEMINI_API_KEY"), model="gemini-2.5-flash")
    runner = PistonRunner("http://127.0.0.1:2000", language="python", version="3.10.0")
    loader = HuggingFaceDatasetLoader("openai/openai_humaneval", split="test", limit=5)
    
    manifest = Manifest(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        benchmark="humaneval",
        benchmark_url="https://github.com/openai/human-eval",
        client_meta=client.get_manifest_metadata(),
        runner_meta=runner.get_manifest_metadata(),
        loader_meta=loader.get_manifest_metadata(),
    )
    
    async with runner:
        dat = he_load_tasks(loader)
        res = await he_solve_tasks(dat, client, runner)

    results_path = DUMP_DIR / "results.json"
    manifest_path = DUMP_DIR / "manifest.json"
    
    with open(results_path, "w", encoding="utf-8") as handle: json.dump(res, handle)
    with open(manifest_path, "w", encoding="utf-8") as handle: json.dump(manifest.model_dump(), handle)


if __name__ == "__main__":
    asyncio.run(run_humaneval_benchmark())
    print("DONE")
