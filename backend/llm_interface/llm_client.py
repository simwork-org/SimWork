"""Multi-provider LLM client adapted from city_of_agents."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def _load_env() -> None:
    """Load environment variables from .env file if present."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()

_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


class LLMClient:
    """Multi-provider LLM client.

    Supports: openai, anthropic, deepseek, ollama.
    Configuration via environment variables.
    """

    def __init__(self, model: str | None = None) -> None:
        self.provider = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()
        self.model = model or os.environ.get("LLM_MODEL", "mistral:latest")
        self.temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "2500"))

        if self.provider == "openai":
            from openai import OpenAI

            api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
            if not api_key:
                raise RuntimeError("Missing OPENAI_API_KEY in environment")
            self.client = OpenAI(api_key=api_key)

        elif self.provider == "anthropic":
            from anthropic import Anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY")
            if not api_key:
                raise RuntimeError("Missing ANTHROPIC_API_KEY in environment")
            self.client = Anthropic(api_key=api_key)

        elif self.provider == "deepseek":
            from openai import OpenAI

            api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
            if not api_key:
                raise RuntimeError("Missing DEEPSEEK_API_KEY in environment")
            self.client = OpenAI(base_url=_DEEPSEEK_BASE_URL, api_key=api_key)

        elif self.provider == "ollama":
            from openai import OpenAI

            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.client = OpenAI(base_url=base_url, api_key="ollama")

        else:
            raise RuntimeError(
                f"Unsupported LLM_PROVIDER={self.provider!r}. "
                "Use 'openai', 'anthropic', 'deepseek', or 'ollama'."
            )

    @staticmethod
    def _extract_anthropic_text(response: Any) -> str:
        parts: list[str] = []
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Extract first JSON object or array from text."""
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", stripped)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            idx = stripped.find(start_char)
            if idx != -1:
                last = stripped.rfind(end_char)
                if last > idx:
                    try:
                        return json.loads(stripped[idx : last + 1])
                    except json.JSONDecodeError:
                        pass
        raise ValueError(f"Could not extract JSON from LLM response:\n{text[:500]}")

    def chat(self, system: str, user: str) -> dict[str, Any]:
        """Send a prompt and return a parsed JSON dict."""
        if self.provider in {"openai", "deepseek"}:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=self.temperature,
            )
            raw = response.choices[0].message.content
        elif self.provider == "ollama":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system + "\n\nReturn ONLY a valid JSON object."},
                    {"role": "user", "content": user},
                ],
                temperature=self.temperature,
            )
            raw = response.choices[0].message.content
        else:  # anthropic
            response = self.client.messages.create(
                model=self.model,
                system=system + "\n\nReturn ONLY a valid JSON object.",
                messages=[{"role": "user", "content": user}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            raw = self._extract_anthropic_text(response)

        return self._extract_json(raw)

    def chat_text(self, system: str, user: str) -> str:
        """Send a prompt and return plain text."""
        if self.provider in {"openai", "deepseek", "ollama"}:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=self.temperature,
            )
            return response.choices[0].message.content or ""
        # anthropic
        response = self.client.messages.create(
            model=self.model,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return self._extract_anthropic_text(response)

    def chat_messages(self, messages: list[dict[str, str]]) -> str:
        """Multi-turn chat. Returns plain text."""
        if self.provider in {"openai", "deepseek", "ollama"}:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
            return response.choices[0].message.content or ""
        # anthropic
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        convo = [m for m in messages if m["role"] != "system"]
        system_text = "\n\n".join(system_parts) if system_parts else "You are a helpful assistant."
        response = self.client.messages.create(
            model=self.model,
            system=system_text,
            messages=convo,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return self._extract_anthropic_text(response)
