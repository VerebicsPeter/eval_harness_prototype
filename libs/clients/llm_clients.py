from __future__ import annotations

import os
from typing import Any

from google import genai
from google.genai import types

from libs.manifest import ManifestMetadata


class GoogleAIStudioClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        timeout: float = 120.0,
        temperature: float = 0.0,
        api_provider: str = "google",
        inference_provider: str = "cloud",
        api_endpoint: str = "https://generativelanguage.googleapis.com",
        model_url: str = "https://ai.google.dev/",
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Google AI Studio API key is required")

        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.api_provider = api_provider
        self.inference_provider = inference_provider
        self.api_endpoint = api_endpoint
        self.model_url = model_url
        
        self._client = genai.Client(api_key=self.api_key)

    async def complete(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=self.temperature),
        )
        
        if not (response.candidates and len(response.candidates) > 0):
            return ""
        
        candidate = response.candidates[0]
        if not (candidate.content and candidate.content.parts and len(candidate.content.parts) > 0):
            return ""
        
        part = candidate.content.parts[0]
        return part.text or ""

    def get_manifest_metadata(self) -> ManifestMetadata:
        return ManifestMetadata(
            target_model={"name": self.model, "url": self.model_url},
            temperature=self.temperature,
            api_provider=self.api_provider,
            inference_provider=self.inference_provider,
            api_endpoint=self.api_endpoint,
        )
