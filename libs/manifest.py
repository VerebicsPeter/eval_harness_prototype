from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ManifestMetadata(BaseModel):
    target_model: dict[str, str | None] | None = None
    temperature: float | None = None
    api_provider: str | None = None
    inference_provider: str | None = None
    api_endpoint: str | None = None


class Manifest(BaseModel):
    run_id: str
    timestamp: str
    benchmark: dict[str, str]
    target_model: dict[str, str | None]
    inference_provider: str | None = None
    temperature: float | None = None
    api_provider: str | None = None
    api_endpoint: str | None = None
    system_fingerprint: str | None = None


@runtime_checkable
class ManifestMetadataSource(Protocol):
    def get_manifest_metadata(self) -> ManifestMetadata:
        ...
