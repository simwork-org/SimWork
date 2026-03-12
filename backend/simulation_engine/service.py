from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException

from backend.agent_router.router import AgentRouter
from backend.config import get_settings
from backend.investigation_logger.store import InvestigationStore
from backend.llm_interface.service import LLMInterface
from backend.models import (
    AgentName,
    HistoryResponse,
    HypothesisResponse,
    QueryResponse,
    ScenarioDetailsResponse,
    StartSessionResponse,
    SubmitSolutionRequest,
    SubmitSolutionResponse,
)
from backend.scenario_loader.loader import ScenarioLoader
from backend.telemetry_layer.service import TelemetryService


class SimulationEngine:
    def __init__(
        self,
        loader: ScenarioLoader | None = None,
        router: AgentRouter | None = None,
        telemetry_service: TelemetryService | None = None,
        store: InvestigationStore | None = None,
    ) -> None:
        self.settings = get_settings()
        self.loader = loader or ScenarioLoader()
        self.router = router or AgentRouter()
        self.telemetry_service = telemetry_service or TelemetryService()
        self.store = store or InvestigationStore()
        self.llm_interface = LLMInterface(self.telemetry_service)

    def list_scenarios(self):
        return self.loader.list_scenarios()

    def start_session(self, candidate_id: str, scenario_id: str) -> StartSessionResponse:
        bundle = self._load_bundle(scenario_id)
        session_id = f"session_{uuid4().hex[:12]}"
        self.store.create_session(
            session_id=session_id,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
            time_limit_minutes=self.settings.time_limit_minutes,
        )
        return StartSessionResponse(
            session_id=session_id,
            scenario_id=scenario_id,
            problem_statement=bundle.config["problem_statement"],
            available_agents=[
                AgentName.ANALYST,
                AgentName.UX_RESEARCHER,
                AgentName.DEVELOPER,
            ],
            time_limit_minutes=self.settings.time_limit_minutes,
        )

    def get_scenario_details(self, session_id: str) -> ScenarioDetailsResponse:
        session = self._require_session(session_id)
        bundle = self._load_bundle(session["scenario_id"])
        return ScenarioDetailsResponse(
            scenario_id=bundle.scenario_id,
            title=bundle.config["title"],
            problem_statement=bundle.config["problem_statement"],
        )

    def handle_query(self, session_id: str, agent: AgentName, query: str) -> QueryResponse:
        session = self._require_session(session_id)
        validation = self.router.validate_query_domain(agent, query)
        if not validation.ok:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "query_domain_violation",
                    "message": validation.message,
                },
            )

        bundle = self._load_bundle(session["scenario_id"])
        response_text = self.llm_interface.answer_query(bundle, agent, query)
        visualization = self.telemetry_service.build_visualization(bundle, agent, query)
        self.store.log_query(
            session_id=session_id,
            candidate_id=session["candidate_id"],
            agent=agent,
            query_text=query,
            response_text=response_text,
            visualization=visualization,
        )
        return QueryResponse(agent=agent, response=response_text, data_visualization=visualization)

    def save_hypothesis(self, session_id: str, hypothesis_text: str) -> HypothesisResponse:
        self._require_session(session_id)
        version = self.store.save_hypothesis(session_id, hypothesis_text)
        return HypothesisResponse(status="saved", hypothesis_version=version)

    def get_history(self, session_id: str) -> HistoryResponse:
        self._require_session(session_id)
        return HistoryResponse(
            queries=self.store.list_queries(session_id),
            hypotheses=self.store.list_hypotheses(session_id),
            final_submission=self.store.get_final_submission(session_id),
        )

    def get_status(self, session_id: str) -> dict:
        self._require_session(session_id)
        return self.store.get_status(session_id)

    def submit_solution(self, session_id: str, request: SubmitSolutionRequest) -> SubmitSolutionResponse:
        self._require_session(session_id)
        self.store.save_submission(session_id, request.model_dump())
        return SubmitSolutionResponse(status="submitted", session_complete=True)

    def _require_session(self, session_id: str) -> dict:
        session = self.store.get_session(session_id)
        if session is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "invalid_session", "message": "Session not found."},
            )
        return session

    def _load_bundle(self, scenario_id: str):
        try:
            return self.loader.load_scenario(scenario_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={"error": "scenario_not_found", "message": f"Scenario {scenario_id} was not found."},
            ) from exc
