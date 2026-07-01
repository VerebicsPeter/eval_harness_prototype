import json
import os
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.humaneval import HumanEvalBenchmark
from libs.clients.llm_clients import GoogleAIStudioClient
from libs.loaders.dataloaders import AssertTestLoader, HuggingFaceDatasetLoader
from libs.manifest import ManifestMetadata


class FakeLoader:
    def load(self):
        return ["def is_even(n): return n % 2 == 0"]


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeGenAIClient:
    def __init__(self, text: str) -> None:
        self._text = text

    class models:
        @staticmethod
        def generate_content(*args, **kwargs):
            return FakeResponse("hello from gemini")


class AssertTestLoaderTests(unittest.TestCase):
    def test_appends_asserts_to_loaded_code(self):
        loader = AssertTestLoader(FakeLoader(), "assert is_even(4) is True")

        loaded = loader.load()

        self.assertEqual(loaded, ["def is_even(n): return n % 2 == 0\n\nassert is_even(4) is True"])


class HuggingFaceDatasetLoaderTests(unittest.TestCase):
    @patch("libs.loaders.dataloaders.load_dataset")
    def test_loads_first_n_records_from_dataset(self, mocked_load_dataset):
        mocked_load_dataset.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]

        loader = HuggingFaceDatasetLoader("demo/dataset", split="test", limit=2)
        records = loader.load()

        self.assertEqual(records, [{"id": 1}, {"id": 2}])


class HumanEvalBenchmarkTests(unittest.TestCase):
    def test_hydrates_prompt_from_humaneval_row(self):
        benchmark = HumanEvalBenchmark(loader=lambda: [{"prompt": "def f(n):\n    return n"}], limit=1)

        tasks = benchmark.load_tasks()

        self.assertEqual(
            tasks,
            [
                {
                    "prompt": "You are solving a Python coding task from the HumanEval benchmark. Return only the implementation for the requested function, preserving the provided signature and docstring.\n\ndef f(n):\n    return n",
                    "task_id": None,
                    "entry_point": None,
                    "canonical_solution": None,
                    "test": None,
                    "raw": {"prompt": "def f(n):\n    return n"},
                }
            ],
        )

    def test_builds_submission_with_test_harness(self):
        benchmark = HumanEvalBenchmark(loader=lambda: [{"prompt": "def f(n):\n    return n", "test": "def check(candidate):\n    assert candidate(2) == 2", "entry_point": "f"}], limit=1)

        task = benchmark.load_tasks()[0]
        submission = benchmark.build_submission(task, "def f(n):\n    return n")

        self.assertIn("def check(candidate):", submission)
        self.assertIn("check(f)", submission)

    def test_build_manifest_contains_required_schema_fields(self):
        benchmark = HumanEvalBenchmark(loader=lambda: [{"prompt": "def f(n):\n    return n"}], limit=1)

        manifest = benchmark.build_manifest()

        self.assertIn("run_id", manifest)
        self.assertEqual(manifest["benchmark"]["name"], "HumanEval")
        self.assertEqual(manifest["api_provider"], None)
        self.assertEqual(manifest["temperature"], None)


class HumanEvalBenchmarkAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_writes_manifest_and_returns_results(self):
        class FakeLLMClient:
            def __init__(self) -> None:
                self.model = "gemini-2.5-flash"
                self.temperature = 0.0
                self.api_provider = "google"
                self.inference_provider = "cloud"
                self.api_endpoint = "https://generativelanguage.googleapis.com"
                self.model_url = "https://ai.google.dev/"

            async def complete(self, prompt):
                return "def f(n):\n    return n"

            def get_manifest_metadata(self):
                return ManifestMetadata(
                    target_model={"name": self.model, "url": self.model_url},
                    temperature=self.temperature,
                    api_provider=self.api_provider,
                    inference_provider=self.inference_provider,
                    api_endpoint=self.api_endpoint,
                )

        class FakeRunner:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def run(self, lang, code, modules):
                return {"lang": lang, "code": code, "modules": modules}

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "manifest.json")
            benchmark = HumanEvalBenchmark(
                loader=lambda: [{"prompt": "def f(n):\n    return n", "test": "def check(candidate):\n    assert candidate(2) == 2", "entry_point": "f"}],
                llm_client=FakeLLMClient(),
                runner=FakeRunner(),
                limit=1,
            )

            payload = await benchmark.run(manifest_path=manifest_path)

            self.assertTrue(os.path.exists(manifest_path))
            with open(manifest_path, encoding="utf-8") as handle:
                manifest = json.load(handle)

            self.assertEqual(payload["manifest"]["benchmark"]["name"], "HumanEval")
            self.assertEqual(payload["manifest"]["target_model"]["name"], "gemini-2.5-flash")
            self.assertEqual(payload["manifest"]["temperature"], 0.0)
            self.assertEqual(payload["manifest"]["api_provider"], "google")
            self.assertEqual(len(payload["results"]), 1)
            self.assertIn("submission", payload["results"][0])
            self.assertEqual(manifest["benchmark"]["name"], "HumanEval")


class GoogleAIStudioClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_text_from_gemini_response(self):
        with patch("libs.clients.llm_clients.genai.Client", return_value=FakeGenAIClient("hello from gemini")):
            client = GoogleAIStudioClient(api_key="test-key")
            text = await client.complete("hello")

        self.assertEqual(text, "hello from gemini")
