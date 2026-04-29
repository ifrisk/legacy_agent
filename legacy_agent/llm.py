from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(RuntimeError):
    """Raised when the configured LLM provider cannot complete a request."""


@dataclass
class LLMConfig:
    provider: str = "none"
    model: str = "gpt-5"
    api_key_env: str = "OPENAI_API_KEY"

    @property
    def enabled(self) -> bool:
        return self.provider.lower() != "none"


class LLMProvider(Protocol):
    def generate_json(self, *, instructions: str, prompt: str) -> dict[str, Any]:
        ...


class NullLLMProvider:
    def generate_json(self, *, instructions: str, prompt: str) -> dict[str, Any]:
        raise LLMError("LLM provider is disabled")


class OpenAIResponsesProvider:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise LLMError(f"Environment variable {config.api_key_env} is not set")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError("OpenAI SDK is not installed. Install with `pip install .[openai]`") from exc
        self.client = OpenAI(api_key=api_key)

    def generate_json(self, *, instructions: str, prompt: str) -> dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=self.config.model,
                instructions=instructions,
                input=prompt,
            )
        except Exception as exc:  # pragma: no cover
            raise LLMError(f"OpenAI request failed: {type(exc).__name__}: {exc}") from exc

        text = getattr(response, "output_text", None)
        if not text:
            output = getattr(response, "output", None) or []
            chunks: list[str] = []
            for item in output:
                for content in getattr(item, "content", []) or []:
                    chunk_text = getattr(content, "text", None)
                    if chunk_text:
                        chunks.append(chunk_text)
            text = "\n".join(chunks)

        if not text:
            raise LLMError("OpenAI response did not include text output")

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model output was not valid JSON: {exc}") from exc


def build_llm_provider(config: LLMConfig) -> LLMProvider:
    provider = config.provider.lower()
    if provider == "none":
        return NullLLMProvider()
    if provider == "openai":
        return OpenAIResponsesProvider(config)
    raise LLMError(f"Unsupported LLM provider: {config.provider}")
