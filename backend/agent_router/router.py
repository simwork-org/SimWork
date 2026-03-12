from __future__ import annotations

from dataclasses import dataclass

from backend.models import AgentName
from backend.telemetry_layer.service import AGENT_DOMAIN_MAP


DOMAIN_KEYWORDS = {
    "analytics": [
        "analytics",
        "metric",
        "metrics",
        "trend",
        "funnel",
        "conversion",
        "orders",
        "cohort",
        "segment",
        "retention",
        "breakdown",
    ],
    "observability": [
        "latency",
        "error",
        "errors",
        "deployment",
        "deployments",
        "service",
        "incident",
        "timeout",
        "logs",
        "performance",
        "api",
    ],
    "user_signals": [
        "feedback",
        "ticket",
        "tickets",
        "support",
        "research",
        "usability",
        "interview",
        "users say",
        "complaint",
        "complaints",
        "sentiment",
    ],
}


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    message: str | None = None


class AgentRouter:
    def validate_query_domain(self, agent: AgentName, query: str) -> ValidationResult:
        query_lower = query.lower()
        matched_domains = {
            domain
            for domain, keywords in DOMAIN_KEYWORDS.items()
            if any(keyword in query_lower for keyword in keywords)
        }
        selected_domain = AGENT_DOMAIN_MAP[agent]

        if len(matched_domains) > 1:
            return ValidationResult(
                ok=False,
                message="Your query spans multiple domains. Please ask separate questions to the relevant team members.",
            )

        if matched_domains and selected_domain not in matched_domains:
            return ValidationResult(
                ok=False,
                message=f"This question belongs to another domain. Ask the teammate responsible for {next(iter(matched_domains)).replace('_', ' ')}.",
            )

        return ValidationResult(ok=True)
