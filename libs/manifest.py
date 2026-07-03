from __future__ import annotations

from pydantic import BaseModel

from libs.clients import LLMClientMetadata
from libs.loaders import LoaderMetadata
from libs.runners import RunnerMetadata


class Manifest(BaseModel):
    run_id: str
    timestamp: str
    benchmark: str
    benchmark_url: str
    
    client_meta: LLMClientMetadata
    runner_meta: RunnerMetadata
    loader_meta: LoaderMetadata
