"""Public schemas for the AI exploration foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

AIExplorationLifecycleStatus = Literal[
    "CREATED",
    "PLANNING",
    "READY",
    "FAILED",
    "RUNNING",
    "SUCCEEDED",
]


class ExplorationPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    intent: str = Field(min_length=1, max_length=1000)
    expected_observation: str = Field(min_length=1, max_length=1000)


class ExplorationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=2000)
    assumptions: list[str] = Field(default_factory=list, max_length=50)
    steps: list[ExplorationPlanStep] = Field(min_length=1, max_length=100)

    @field_validator("assumptions")
    @classmethod
    def validate_assumptions(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 1000 for value in normalized):
            raise ValueError("assumptions must contain non-empty values up to 1000 characters")
        return normalized

    @model_validator(mode="after")
    def validate_step_sequence(self) -> ExplorationPlan:
        if [step.sequence for step in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("steps must use a contiguous sequence beginning at 1")
        return self


class CreateAIExplorationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=26, max_length=26)
    source_case_id: str | None = Field(default=None, min_length=26, max_length=26)
    objective: str = Field(min_length=1, max_length=4000)
    target_url: HttpUrl = Field(max_length=2048)

    @field_validator("objective")
    @classmethod
    def normalize_objective(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("objective must not be blank")
        return normalized


class AIExplorationSessionResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    ai_task_id: str
    project_id: str
    source_case_id: str | None
    objective: str
    target_url: str
    lifecycle_status: AIExplorationLifecycleStatus
    resolved_model_config_id: str
    resolved_model_display_name: str | None
    resolved_provider_code: str
    resolved_model_name: str
    plan: ExplorationPlan | None
    failure_code: str | None
    failure_message: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class CreateAIExplorationResponse(BaseModel):
    data: AIExplorationSessionResource
    correlation_id: str
