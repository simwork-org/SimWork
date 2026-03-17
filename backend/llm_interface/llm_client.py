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

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Any,  # Callable[[str, dict], str]
        max_iterations: int = 5,
    ) -> str:
        """ReAct tool-use loop. Returns final text after up to max_iterations tool rounds.

        Args:
            messages: Conversation messages (system + user + history).
            tools: OpenAI-format tool definitions.
            tool_executor: Callable(tool_name, args_dict) -> str result.
            max_iterations: Safety cap on tool-call rounds.

        Returns:
            Final text response from the LLM.
        """
        import logging

        logger = logging.getLogger(__name__)
        msgs = [dict(m) for m in messages]  # defensive copy

        if self.provider in {"openai", "deepseek", "ollama"}:
            return self._tool_loop_openai(msgs, tools, tool_executor, max_iterations, logger)
        elif self.provider == "anthropic":
            return self._tool_loop_anthropic(msgs, tools, tool_executor, max_iterations, logger)
        else:
            raise RuntimeError(f"Tool calling not supported for provider: {self.provider}")

    def _tool_loop_openai(
        self,
        msgs: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Any,
        max_iterations: int,
        logger: Any,
    ) -> str:
        """ReAct loop for OpenAI-compatible APIs (openai, deepseek, ollama)."""
        for iteration in range(max_iterations):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=msgs,
                tools=tools,
                tool_choice="auto",
                temperature=self.temperature,
            )
            choice = response.choices[0]

            # If no tool calls, return the text content
            if not choice.message.tool_calls:
                return self._clean_dsml(choice.message.content or "")

            # Append the assistant message with tool calls
            msgs.append(choice.message.model_dump())

            # Execute each tool call and append results
            for tc in choice.message.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                logger.info(f"Tool call [{iteration+1}/{max_iterations}]: {fn_name}({fn_args})")

                try:
                    result = tool_executor(fn_name, fn_args)
                except Exception as e:
                    result = f"Error executing {fn_name}: {e}"

                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result),
                })

        # Exhausted iterations — force a final response with a clean prompt
        logger.warning(f"Tool loop exhausted after {max_iterations} iterations, forcing final response")

        # Collect all tool results to build a data summary
        data_parts = []
        for m in msgs:
            if isinstance(m, dict) and m.get("role") == "tool":
                data_parts.append(m.get("content", ""))

        # Get the system prompt and original user question
        system_msg = next((m.get("content", "") for m in msgs if isinstance(m, dict) and m.get("role") == "system"), "")
        user_msg = next((m.get("content", "") for m in msgs if isinstance(m, dict) and m.get("role") == "user"), "")

        summary_prompt = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": (
                f"Original question: {user_msg}\n\n"
                f"Here is all the data you've gathered from your queries:\n\n"
                + "\n---\n".join(data_parts[-6:]) +  # last 6 tool results
                "\n\nNow formulate your final response as a JSON object with insight, chart, and next_steps. "
                "Do NOT call any tools. Respond with ONLY the JSON object."
            )},
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=summary_prompt,
            temperature=self.temperature,
        )
        text = response.choices[0].message.content or ""
        return self._clean_dsml(text)

    def _tool_loop_anthropic(
        self,
        msgs: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Any,
        max_iterations: int,
        logger: Any,
    ) -> str:
        """ReAct loop for Anthropic API."""
        # Convert OpenAI tool format to Anthropic format
        anthropic_tools = []
        for t in tools:
            fn = t["function"]
            anthropic_tools.append({
                "name": fn["name"],
                "description": fn["description"],
                "input_schema": fn["parameters"],
            })

        # Extract system message
        system_parts = [m["content"] for m in msgs if m["role"] == "system"]
        convo = [m for m in msgs if m["role"] != "system"]
        system_text = "\n\n".join(system_parts) if system_parts else "You are a helpful assistant."

        for iteration in range(max_iterations):
            response = self.client.messages.create(
                model=self.model,
                system=system_text,
                messages=convo,
                tools=anthropic_tools,
                temperature=self.temperature,
                max_tokens=self.max_tokens * 2,  # extra room for tool reasoning
            )

            # Check if there are tool use blocks
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                # No tool calls — extract and return text
                return self._extract_anthropic_text(response)

            # Append assistant response as-is
            convo.append({"role": "assistant", "content": response.content})

            # Execute tools and build tool results
            tool_results = []
            for tb in tool_use_blocks:
                logger.info(f"Tool call [{iteration+1}/{max_iterations}]: {tb.name}({tb.input})")
                try:
                    result = tool_executor(tb.name, tb.input)
                except Exception as e:
                    result = f"Error executing {tb.name}: {e}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": str(result),
                })

            convo.append({"role": "user", "content": tool_results})

        # Exhausted iterations — force a final response without tools
        logger.warning(f"Tool loop exhausted after {max_iterations} iterations, forcing final response")
        response = self.client.messages.create(
            model=self.model,
            system=system_text,
            messages=convo,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return self._extract_anthropic_text(response)

    @staticmethod
    def _clean_dsml(text: str) -> str:
        """Strip DeepSeek DSML tool-call artifacts from response text."""
        # Remove DSML blocks: <｜DSML｜...> or <| DSML |...> patterns
        text = re.sub(r'<[｜|]\s*DSML\s*[｜|][^>]*>[\s\S]*?</[｜|]\s*DSML\s*[｜|][^>]*>', '', text)
        text = re.sub(r'<[｜|]\s*DSML\s*[｜|][^>]*>', '', text)
        text = re.sub(r'</[｜|]\s*DSML\s*[｜|][^>]*>', '', text)
        return text.strip()

