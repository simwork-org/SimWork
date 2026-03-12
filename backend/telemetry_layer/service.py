from __future__ import annotations

from typing import Any

import pandas as pd

from backend.models import AgentName, Visualization
from backend.scenario_loader.loader import ScenarioBundle


AGENT_DOMAIN_MAP = {
    AgentName.ANALYST: "analytics",
    AgentName.UX_RESEARCHER: "user_signals",
    AgentName.DEVELOPER: "observability",
}


class TelemetryService:
    def get_allowed_domain(self, agent: AgentName) -> str:
        return AGENT_DOMAIN_MAP[agent]

    def get_allowed_telemetry(self, bundle: ScenarioBundle, agent: AgentName) -> dict[str, Any]:
        return bundle.telemetry[self.get_allowed_domain(agent)]

    def build_context(self, bundle: ScenarioBundle, agent: AgentName) -> str:
        domain = self.get_allowed_domain(agent)
        telemetry = self.get_allowed_telemetry(bundle, agent)
        lines = [f"Domain: {domain}"]
        for name, payload in telemetry.items():
            lines.append(f"\nDataset: {name}")
            if isinstance(payload, pd.DataFrame):
                lines.append(payload.to_csv(index=False).strip())
            elif isinstance(payload, list):
                lines.append(str(payload))
            else:
                lines.append(str(payload))
        return "\n".join(lines)

    def build_visualization(
        self,
        bundle: ScenarioBundle,
        agent: AgentName,
        query: str,
    ) -> Visualization | None:
        telemetry = self.get_allowed_telemetry(bundle, agent)
        query_lower = query.lower()

        if agent == AgentName.ANALYST:
            if "segment" in query_lower or "cohort" in query_lower or "new user" in query_lower:
                segments = telemetry.get("segments")
                if isinstance(segments, pd.DataFrame):
                    return Visualization(
                        type="bar",
                        title="Segment Checkout Conversion",
                        data=[
                            {
                                "label": str(row["segment"]),
                                "previous": float(row["previous_checkout_conversion"]),
                                "current": float(row["current_checkout_conversion"]),
                                "status": str(row["status"]),
                            }
                            for _, row in segments.iterrows()
                        ],
                    )
            if "order" in query_lower or "trend" in query_lower or "time" in query_lower:
                metrics = telemetry.get("metrics_timeseries")
                if isinstance(metrics, pd.DataFrame):
                    return Visualization(
                        type="line",
                        title="Orders Trend",
                        data=[
                            {
                                "label": str(row["date"]),
                                "orders": int(row["orders"]),
                                "conversion_rate": float(row["conversion_rate"]),
                            }
                            for _, row in metrics.iterrows()
                        ],
                    )
            funnel = telemetry.get("funnel_metrics")
            if isinstance(funnel, pd.DataFrame):
                return Visualization(
                    type="funnel",
                    title="Checkout Funnel",
                    data=[
                        {
                            "step": str(row["step"]),
                            "previous": float(row["previous_period"]),
                            "value": float(row["current_period"]),
                        }
                        for _, row in funnel.iterrows()
                    ],
                )

        if agent == AgentName.DEVELOPER:
            if "deploy" in query_lower or "release" in query_lower or "change" in query_lower:
                deployments = telemetry.get("deployments")
                if isinstance(deployments, list):
                    return Visualization(type="timeline", title="Deployments", data=deployments)
            if "error" in query_lower or "fail" in query_lower:
                error_rates = telemetry.get("error_rates")
                if isinstance(error_rates, pd.DataFrame):
                    return Visualization(
                        type="bar",
                        title="Service Error Rates",
                        data=[
                            {"label": str(row["service"]), "value": float(row["error_rate"])}
                            for _, row in error_rates.iterrows()
                        ],
                    )
            latency = telemetry.get("service_latency")
            if isinstance(latency, pd.DataFrame):
                return Visualization(
                    type="bar",
                    title="Week 4 Service Latency",
                    data=[
                        {"label": str(row["service"]), "value": float(row["week4"])}
                        for _, row in latency.iterrows()
                    ],
                )

        if agent == AgentName.UX_RESEARCHER:
            support_tickets = telemetry.get("support_tickets")
            if "ticket" in query_lower or "support" in query_lower or not query_lower.strip():
                if isinstance(support_tickets, pd.DataFrame):
                    return Visualization(
                        type="table",
                        title="Support Tickets",
                        data=[
                            {"ticket_id": str(row["ticket_id"]), "issue": str(row["issue"])}
                            for _, row in support_tickets.head(5).iterrows()
                        ],
                    )
            user_feedback = telemetry.get("user_feedback")
            if isinstance(user_feedback, pd.DataFrame):
                return Visualization(
                    type="table",
                    title="User Feedback",
                    data=[{"feedback": str(row["feedback"])} for _, row in user_feedback.head(5).iterrows()],
                )

        return None
