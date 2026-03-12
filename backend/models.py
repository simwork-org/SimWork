from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentName(StrEnum):
    ANALYST = "analyst"
    UX_RESEARCHER = "ux_researcher"
    DEVELOPER = "developer"


class Visualization(BaseModel):
    type: str
    title: str | None = None
    data: list[dict[str, Any]]


class StartSessionRequest(BaseModel):
    candidate_id: str
    scenario_id: str


class StartSessionResponse(BaseModel):
    session_id: str
    scenario_id: str
    problem_statement: str
    available_agents: list[AgentName]
    time_limit_minutes: int


class ScenarioSummary(BaseModel):
    id: str
    title: str
    difficulty: str
    industry: str | None = None
    product: str | None = None


class ScenarioDetailsResponse(BaseModel):
    scenario_id: str
    title: str
    problem_statement: str


class QueryRequest(BaseModel):
    agent: AgentName
    query: str = Field(min_length=3)


class QueryResponse(BaseModel):
    agent: AgentName
    response: str
    data_visualization: Visualization | None = None


class HypothesisRequest(BaseModel):
    hypothesis: str = Field(min_length=3)


class HypothesisResponse(BaseModel):
    status: str
    hypothesis_version: int


class HistoryItem(BaseModel):
    timestamp: datetime
    agent: AgentName
    query: str
    response: str
    data_visualization: Visualization | None = None


class HypothesisHistoryItem(BaseModel):
    timestamp: datetime
    hypothesis: str
    hypothesis_version: int


class HistoryResponse(BaseModel):
    queries: list[HistoryItem]
    hypotheses: list[HypothesisHistoryItem] = Field(default_factory=list)
    final_submission: dict[str, Any] | None = None


class SubmitSolutionRequest(BaseModel):
    root_cause: str = Field(min_length=3)
    proposed_actions: list[str] = Field(min_length=1)
    summary: str = Field(min_length=3)


class SubmitSolutionResponse(BaseModel):
    status: str
    session_complete: bool


class SessionStatusResponse(BaseModel):
    session_id: str
    scenario_id: str
    time_remaining_minutes: int
    current_hypothesis: str | None = None
    queries_made: int
    completed: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
