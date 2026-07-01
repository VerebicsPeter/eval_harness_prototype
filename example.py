import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from benchmarks.humaneval import HumanEvalBenchmark
from libs.clients.llm_clients import GoogleAIStudioClient
from libs.loaders.dataloaders import HuggingFaceDatasetLoader
from libs.runners.piston_runner import PistonRunner

load_dotenv(".env")


async def run_humaneval_benchmark() -> None:
    llm_client = GoogleAIStudioClient(api_key=os.getenv("GEMINI_API_KEY"), model="gemini-2.5-flash")
    runner = PistonRunner(host="http://127.0.0.1:2000", lang="python", version="3.10.0")
    loader = HuggingFaceDatasetLoader("openai/openai_humaneval", split="test", limit=1)

    manifest_dir = Path("tests/dumps")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "manifest.json"
    if manifest_path.exists(): manifest_path.unlink()

    benchmark = HumanEvalBenchmark(loader.load, llm_client, runner, limit=1)

    result = await benchmark.run(manifest_path=str(manifest_path))

    results_dir = Path("tests/dumps")
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / "results.json"
    with open(results_path, "w", encoding="utf-8") as handle: json.dump(result, handle)


if __name__ == "__main__":
    asyncio.run(run_humaneval_benchmark())
    print("DONE")
