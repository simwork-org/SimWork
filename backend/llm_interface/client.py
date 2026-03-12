from __future__ import annotations

import os
from typing import Any

from backend.config import Settings


DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.provider = settings.model_provider.strip().lower()
        self.model = settings.model_name
        self.client: Any | None = None

        if self.provider == "openai" and settings.openai_api_key:
            from openai import OpenAI

            self.client = OpenAI(api_key=settings.openai_api_key)
        elif self.provider == "anthropic" and settings.anthropic_api_key:
            from anthropic import Anthropic

            self.client = Anthropic(api_key=settings.anthropic_api_key)
        elif self.provider == "deepseek" and settings.deepseek_api_key:
            from openai import OpenAI

            self.client = OpenAI(api_key=settings.deepseek_api_key, base_url=DEEPSEEK_BASE_URL)
        elif self.provider == "ollama":
            from openai import OpenAI

            self.client = OpenAI(api_key=os.environ.get("OLLAMA_API_KEY", "ollama"), base_url=settings.ollama_endpoint)

    @property
    def is_available(self) -> bool:
        return self.client is not None

    def chat_text(self, system: str, user: str) -> str:
        if not self.client:
            raise RuntimeError("LLM client is not configured")

        if self.provider in {"openai", "deepseek", "ollama"}:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content or ""

        response = self.client.messages.create(
            model=self.model,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.2,
            max_tokens=800,
        )
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "\n".join(parts).strip()
