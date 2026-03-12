from __future__ import annotations

from typing import Any

import pandas as pd

from backend.config import get_settings
from backend.llm_interface.client import LLMClient
from backend.llm_interface.prompts import build_agent_prompt
from backend.models import AgentName
from backend.scenario_loader.loader import ScenarioBundle
from backend.telemetry_layer.service import TelemetryService


class LLMInterface:
    def __init__(self, telemetry_service: TelemetryService) -> None:
        self.settings = get_settings()
        self.client = LLMClient(self.settings)
        self.telemetry_service = telemetry_service

    def answer_query(self, bundle: ScenarioBundle, agent: AgentName, query: str) -> str:
        if "root cause" in query.lower():
            return (
                "I can share evidence from my domain, but I cannot determine the root cause alone. "
                "You will need to combine signals from the other teammates before concluding."
            )

        if self.client.is_available:
            system = build_agent_prompt(agent, bundle.config["problem_statement"])
            user = (
                f"Candidate query: {query}\n\n"
                f"Allowed telemetry:\n{self.telemetry_service.build_context(bundle, agent)}\n\n"
                "Respond like a helpful teammate. Stay within your domain and mention concrete evidence."
            )
            try:
                return self.client.chat_text(system, user).strip()
            except Exception:
                pass

        return self._fallback_response(bundle, agent, query)

    def _fallback_response(self, bundle: ScenarioBundle, agent: AgentName, query: str) -> str:
        telemetry = self.telemetry_service.get_allowed_telemetry(bundle, agent)
        query_lower = query.lower()

        if agent == AgentName.ANALYST:
            metrics = telemetry.get("metrics_timeseries")
            funnel = telemetry.get("funnel_metrics")
            segments = telemetry.get("segments")
            if isinstance(metrics, pd.DataFrame) and ("orders" in query_lower or "trend" in query_lower):
                start = metrics.iloc[0]
                end = metrics.iloc[-1]
                return (
                    f"Orders declined from {int(start['orders']):,} to {int(end['orders']):,} across the loaded period, "
                    f"while conversion rate moved from {float(start['conversion_rate']) * 100:.1f}% "
                    f"to {float(end['conversion_rate']) * 100:.1f}%."
                )
            if isinstance(segments, pd.DataFrame) and (
                "segment" in query_lower or "cohort" in query_lower or "new user" in query_lower
            ):
                worst = segments.sort_values("current_checkout_conversion").iloc[0]
                return (
                    f"The weakest segment in the current data is {worst['segment']}, with checkout conversion at "
                    f"{float(worst['current_checkout_conversion']) * 100:.1f}% versus "
                    f"{float(worst['previous_checkout_conversion']) * 100:.1f}% previously."
                )
            if isinstance(funnel, pd.DataFrame):
                checkout = funnel[funnel["step"] == "checkout"].iloc[0]
                payment = funnel[funnel["step"] == "payment"].iloc[0]
                return (
                    "The main funnel degradation appears near payment. "
                    f"Checkout moved from {float(checkout['previous_period']) * 100:.1f}% to "
                    f"{float(checkout['current_period']) * 100:.1f}%, while payment dropped from "
                    f"{float(payment['previous_period']) * 100:.1f}% to {float(payment['current_period']) * 100:.1f}%."
                )

        if agent == AgentName.DEVELOPER:
            latency = telemetry.get("service_latency")
            error_rates = telemetry.get("error_rates")
            deployments = telemetry.get("deployments")
            if isinstance(deployments, list) and ("deploy" in query_lower or "release" in query_lower):
                latest = deployments[-1]
                return (
                    f"The latest relevant deployment was on {latest['date']} for {latest['service']}: "
                    f"{latest['change']}."
                )
            if isinstance(error_rates, pd.DataFrame) and ("error" in query_lower or "fail" in query_lower):
                worst = error_rates.sort_values("error_rate", ascending=False).iloc[0]
                return (
                    f"{worst['service']} has the highest error rate in this dataset at {float(worst['error_rate']):.1f}%."
                )
            if isinstance(latency, pd.DataFrame):
                payment = latency[latency["service"] == "payment_service"].iloc[0]
                return (
                    "Payment-service latency is the main engineering anomaly. "
                    f"It increased from {float(payment['week1']):.1f}s in week 1 to {float(payment['week4']):.1f}s in week 4, "
                    "while the checkout service stayed relatively flat."
                )

        if agent == AgentName.UX_RESEARCHER:
            tickets = telemetry.get("support_tickets")
            findings = telemetry.get("usability_findings", "")
            feedback = telemetry.get("user_feedback")
            if isinstance(tickets, pd.DataFrame) and ("ticket" in query_lower or "support" in query_lower):
                issues = ", ".join(str(value) for value in tickets["issue"].head(3))
                return f"Recent support tickets cluster around checkout friction: {issues}."
            if "usability" in query_lower or "research" in query_lower:
                return str(findings).strip()
            if isinstance(feedback, pd.DataFrame):
                samples = "; ".join(str(value) for value in feedback["feedback"].head(3))
                return f"Recent qualitative feedback includes: {samples}."

        return "I can answer questions within my domain. Ask me for a specific metric, signal, or data slice."
