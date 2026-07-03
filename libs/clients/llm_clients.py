from __future__ import annotations

import os
from typing import Any, Protocol
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


class LLMClientMetadata(BaseModel):
    model: str
    model_url: str
    inference_provider_type: str
    api_provider: str
    api_endpoint: str
    hyperparameters: dict[str, Any] = Field(default_factory=dict)


class LLMClient(Protocol):
    async def complete(self, prompt: str) -> str:
        ...

    def get_manifest_metadata(self) -> LLMClientMetadata:
        ...


class GoogleAIStudioClient(LLMClient):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        model_url: str = "https://ai.google.dev/",
        inference_provider_type: str = "cloud",
        api_provider: str = "google",
        api_endpoint: str = "https://generativelanguage.googleapis.com",
        h_timeout: float = 120.0,
        h_temperature: float = 0.0,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Google AI Studio API key is required")

        self._metad = LLMClientMetadata(
            model=model,
            model_url=model_url,
            inference_provider_type=inference_provider_type,
            api_provider=api_provider,
            api_endpoint=api_endpoint,
            hyperparameters={"timeout": h_timeout, "temperature": h_temperature},
        )
        
        self._client = genai.Client(api_key=self.api_key)

    async def complete(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._metad.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self._metad.hyperparameters.get("temperature", 0.0))
        )
        
        if not (response.candidates and len(response.candidates) > 0):
            return ""
        
        candidate = response.candidates[0]
        if not (candidate.content and candidate.content.parts and len(candidate.content.parts) > 0):
            return ""
        
        part = candidate.content.parts[0]
        return part.text or ""

    def get_manifest_metadata(self) -> LLMClientMetadata:
        return self._metad
