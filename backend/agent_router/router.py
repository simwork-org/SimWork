"""Agent router — routes candidate queries to the correct AI agent with domain-scoped data."""

from __future__ import annotations

import json
import logging

from llm_interface.llm_client import LLMClient
from telemetry_layer.telemetry import (
    VALID_AGENTS,
    format_telemetry_context,
    get_telemetry_for_agent,
)

logger = logging.getLogger(__name__)

# ── Structured output schema shared with all agents ──
RESPONSE_SCHEMA_INSTRUCTION = """
You MUST respond with a valid JSON object matching this schema exactly:
{
  "insight": "A concise 1-2 sentence insight from the data. No raw numbers dump.",
  "chart": {
    "type": "bar | line | funnel | table",
    "title": "Short chart title",
    "labels": ["Label1", "Label2", ...],
    "values": [100, 200, ...],
    "unit": "orders | users | % | ms | count"
  },
  "next_steps": ["Suggested follow-up question 1", "Suggested follow-up question 2"]
}

Rules for chart:
- "line" for time-series / trends. Labels are dates or weeks.
- "bar" for comparisons across categories/segments.
- "funnel" for step-by-step conversion flows. Values must be in descending order (top of funnel first).
- "table" if data is better shown as key-value pairs.
- Values must be raw numbers (not strings). Use the actual numbers from the data.
- If the data shows a DECLINE, values must decrease over time. Never invert the trend.
- labels and values arrays must have the same length.

Rules for insight:
- Summarize the key finding in plain language.
- Mention the most important number or trend.
- Do NOT dump all the data. Be concise.
- Tell the candidate you've pulled a chart and point them to the dashboard.

Rules for next_steps:
- Suggest 2 relevant follow-up questions the candidate could ask you or another teammate.
"""

# ── Agent system prompts ──
AGENT_PROMPTS: dict[str, str] = {
    "analyst": (
        "You are a Data Analyst on a product team. "
        "You have access ONLY to analytics data (product metrics, funnels, segments). "
        "Your skills: query metrics, build charts from data, analyze funnels, compare segments. "
        "When the candidate asks a question, look at the telemetry data, pick the right visualization, "
        "and return a structured JSON response. "
        "You must NOT reveal the root cause directly — let the candidate figure it out. "
        "You must NOT access or reference engineering/observability data or user feedback. "
        "If asked about something outside your domain, tell them to ask the relevant teammate. "
        "If asked about something outside your domain, you MUST clearly refuse and redirect. "
        "Say something like: 'I only have access to analytics data. For engineering questions, please ask the Developer.' "
        "Do NOT repeat previous answers or guess. Always respond with the JSON schema. "
        "For out-of-domain questions, set chart labels and values to empty arrays []."
    ),
    "ux_researcher": (
        "You are a UX Researcher on a product team. "
        "You have access ONLY to user signals data (support tickets, usability findings, user feedback). "
        "Your skills: analyze user feedback themes, surface support ticket patterns, identify usability issues. "
        "When the candidate asks a question, look at the telemetry data, pick the right visualization, "
        "and return a structured JSON response. "
        "You must NOT reveal the root cause directly — let the candidate figure it out. "
        "You must NOT access or reference analytics metrics or engineering/system data. "
        "If asked about something outside your domain, tell them to ask the relevant teammate. "
        "If asked about something outside your domain, you MUST clearly refuse and redirect. "
        "Say something like: 'I only have access to user signals data. For analytics questions, please ask the Data Analyst.' "
        "Do NOT repeat previous answers or guess. Always respond with the JSON schema. "
        "For out-of-domain questions, set chart labels and values to empty arrays []."
    ),
    "developer": (
        "You are a Developer / Technical Lead on a product team. "
        "You have access ONLY to observability data (service latency, error rates, deployments). "
        "Your skills: check service latency, analyze error rates, review deployment history, assess system health. "
        "When the candidate asks a question, look at the telemetry data, pick the right visualization, "
        "and return a structured JSON response. "
        "You must NOT reveal the root cause directly — let the candidate figure it out. "
        "You must NOT access or reference analytics metrics or user feedback. "
        "If asked about something outside your domain, tell them to ask the relevant teammate. "
        "If asked about something outside your domain, you MUST clearly refuse and redirect. "
        "Say something like: 'I only have access to observability data. For analytics questions, please ask the Data Analyst.' "
        "Do NOT repeat previous answers or guess. Always respond with the JSON schema. "
        "For out-of-domain questions, set chart labels and values to empty arrays []."
    ),
}


def validate_agent(agent: str) -> None:
    """Raise ValueError if the agent name is invalid."""
    if agent not in VALID_AGENTS:
        raise ValueError(f"Invalid agent: {agent}. Valid agents: {sorted(VALID_AGENTS)}")


def _parse_structured_response(raw_text: str) -> dict:
    """Try to parse the LLM's response as structured JSON.

    Falls back to plain text if parsing fails.
    """
    text = raw_text.strip()

    # Try direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "insight" in parsed:
            return _validate_chart(parsed)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    import re
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        try:
            parsed = json.loads(match.group(1).strip())
            if isinstance(parsed, dict) and "insight" in parsed:
                return _validate_chart(parsed)
        except json.JSONDecodeError:
            pass

    # Try finding JSON object in text
    idx = text.find("{")
    if idx != -1:
        last = text.rfind("}")
        if last > idx:
            try:
                parsed = json.loads(text[idx:last + 1])
                if isinstance(parsed, dict) and "insight" in parsed:
                    return _validate_chart(parsed)
            except json.JSONDecodeError:
                pass

    # Fallback: return as plain text response
    logger.warning("Could not parse structured response from LLM, falling back to plain text")
    return {
        "insight": text[:500],
        "chart": None,
        "next_steps": [],
    }


def _validate_chart(parsed: dict) -> dict:
    """Ensure chart data is well-formed."""
    chart = parsed.get("chart")
    if chart and isinstance(chart, dict):
        labels = chart.get("labels", [])
        values = chart.get("values", [])
        # Ensure labels and values are lists of same length
        if not isinstance(labels, list) or not isinstance(values, list):
            chart["labels"] = []
            chart["values"] = []
        elif len(labels) != len(values):
            min_len = min(len(labels), len(values))
            chart["labels"] = labels[:min_len]
            chart["values"] = values[:min_len]
        # Ensure values are numbers
        cleaned_values = []
        for v in chart.get("values", []):
            try:
                cleaned_values.append(float(v))
            except (ValueError, TypeError):
                cleaned_values.append(0)
        chart["values"] = cleaned_values
        # Ensure chart type is valid
        if chart.get("type") not in ("bar", "line", "funnel", "table"):
            chart["type"] = "bar"
        parsed["chart"] = chart
    else:
        parsed["chart"] = None

    if not isinstance(parsed.get("next_steps"), list):
        parsed["next_steps"] = []

    return parsed


def route_query(
    llm: LLMClient,
    scenario_id: str,
    agent: str,
    query: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict:
    """Route a candidate query to the specified agent and return structured response.

    Returns dict with keys: agent, response (insight text), chart, next_steps.
    """
    validate_agent(agent)

    # Load domain-scoped telemetry
    telemetry_data = get_telemetry_for_agent(scenario_id, agent)
    telemetry_context = format_telemetry_context(telemetry_data)

    system_prompt = AGENT_PROMPTS[agent]
    system_prompt += f"\n\n{RESPONSE_SCHEMA_INSTRUCTION}"
    system_prompt += f"\n\nHere is the telemetry data you have access to:\n\n{telemetry_context}"

    # Build user prompt
    user_prompt = f"Candidate question: {query}"

    # Use multi-turn if history is available
    if conversation_history:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_prompt})
        response_text = llm.chat_messages(messages)
    else:
        response_text = llm.chat_text(system_prompt, user_prompt)

    # Parse structured response
    structured = _parse_structured_response(response_text)

    return {
        "agent": agent,
        "response": structured.get("insight", response_text),
        "chart": structured.get("chart"),
        "next_steps": structured.get("next_steps", []),
    }
