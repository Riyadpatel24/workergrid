from datetime import datetime
from typing import Any
from pydantic import BaseModel


class RepositorySchema(BaseModel):
    id: int
    owner: str
    name: str
    full_name: str
    default_branch: str
    created_at: datetime


class AnalysisRunStatusResponse(BaseModel):
    run_id: str
    repository: str
    status: str
    progress_pct: int
    current_stage: str
    time_window_days: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class MetricResponse(BaseModel):
    category: str
    name: str
    value: float
    unit: str | None = None
    details: dict[str, Any] | None = None


class EvidenceResponse(BaseModel):
    id: int
    entity_type: str | None = None
    external_id: str | None = None
    title: str | None = None
    url: str | None = None
    metrics_breakdown: dict[str, Any] | None = None


class IndicatorResponse(BaseModel):
    id: int
    category: str
    severity: str
    title: str
    summary: str
    score_impact: float
    recommendation: str | None = None
    evidence: list[EvidenceResponse] = []


class FrictionReportResponse(BaseModel):
    run_id: str
    repository: str
    status: str
    time_window_days: int
    overall_friction_score: float | None = None
    friction_level: str | None = None
    completed_at: datetime | None = None
    dimensions: dict[str, float] = {}
    metrics: list[MetricResponse] = []
    indicators: list[IndicatorResponse] = []
