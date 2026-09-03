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
    "CANCELLED",
]

AIExplorationActionType = Literal[
    "Navigate",
    "Click",
    "Fill",
    "Select",
    "Check",
    "Uncheck",
    "PressKey",
    "WaitFor",
    "Inspect",
    "Read",
    "Scroll",
    "goal_completed",
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
    execution_attempt_id: str | None
    execution_binding_snapshot_id: str | None
    browser_session_id: str | None
    project_id: str
    source_case_id: str | None
    objective: str
    target_url: str
    lifecycle_status: AIExplorationLifecycleStatus
    current_step_sequence: int = Field(ge=0)
    current_observation_id: str | None
    max_steps: int | None = Field(default=None, gt=0)
    total_timeout_seconds: int | None = Field(default=None, gt=0)
    model_transient_retry_per_step: int | None = Field(default=None, ge=0, le=10)
    row_version: int = Field(ge=1)
    resolved_model_config_id: str
    resolved_model_display_name: str | None
    resolved_provider_code: str
    resolved_model_name: str
    plan: ExplorationPlan | None
    failure_code: str | None
    failure_message: str | None
    total_deadline_at: datetime | None
    started_at: datetime | None
    terminal_at: datetime | None
    cancel_requested_at: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class CreateAIExplorationResponse(BaseModel):
    data: AIExplorationSessionResource
    correlation_id: str


class StartAIExplorationSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_attempt_id: str = Field(min_length=26, max_length=26)
    expected_row_version: int = Field(ge=1)


class CancelAIExplorationSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_row_version: int = Field(ge=1)


class AIExplorationBrowserAction(BaseModel):
    """Closed action union. No model-produced code can cross this boundary."""

    model_config = ConfigDict(extra="forbid")

    type: AIExplorationActionType
    selector: str | None = Field(default=None, max_length=1000)
    url: HttpUrl | None = Field(default=None, max_length=2048)
    value: str | None = Field(default=None, max_length=4000)
    key: str | None = Field(default=None, max_length=64)
    direction: Literal["up", "down", "left", "right"] | None = None
    amount: int | None = Field(default=None, ge=1, le=10000)
    reason: str | None = Field(default=None, max_length=1000)
    completed_goal: str | None = Field(default=None, max_length=2000)
    satisfied_plan_steps: list[int] | None = Field(default=None, max_length=100)
    evidence: list[str] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def validate_shape(self) -> AIExplorationBrowserAction:
        selector_actions = {
            "Click",
            "Fill",
            "Select",
            "Check",
            "Uncheck",
            "WaitFor",
            "Inspect",
            "Read",
        }
        if self.type in selector_actions and not (self.selector or "").strip():
            raise ValueError(f"{self.type} requires selector")
        if self.type == "Navigate" and self.url is None:
            raise ValueError("Navigate requires url")
        if self.type in {"Fill", "Select"} and self.value is None:
            raise ValueError(f"{self.type} requires value")
        if self.type == "PressKey" and not (self.key or "").strip():
            raise ValueError("PressKey requires key")
        if self.type == "Scroll" and (self.direction is None or self.amount is None):
            raise ValueError("Scroll requires direction and amount")
        if self.type == "goal_completed":
            if not (self.completed_goal or "").strip():
                raise ValueError("goal_completed requires completed_goal")
            if not self.satisfied_plan_steps or any(item < 1 for item in self.satisfied_plan_steps):
                raise ValueError("goal_completed requires satisfied_plan_steps")
            if not self.evidence or any(not item.strip() for item in self.evidence):
                raise ValueError("goal_completed requires non-empty evidence")
        allowed = {
            "Navigate": {"url", "reason"},
            "Click": {"selector", "reason"},
            "Fill": {"selector", "value", "reason"},
            "Select": {"selector", "value", "reason"},
            "Check": {"selector", "reason"},
            "Uncheck": {"selector", "reason"},
            "PressKey": {"selector", "key", "reason"},
            "WaitFor": {"selector", "reason"},
            "Inspect": {"selector", "reason"},
            "Read": {"selector", "reason"},
            "Scroll": {"direction", "amount", "reason"},
            "goal_completed": {
                "reason",
                "completed_goal",
                "satisfied_plan_steps",
                "evidence",
            },
        }[self.type]
        supplied = {
            name
            for name in (
                "selector",
                "url",
                "value",
                "key",
                "direction",
                "amount",
                "reason",
                "completed_goal",
                "satisfied_plan_steps",
                "evidence",
            )
            if getattr(self, name) is not None
        }
        if supplied - allowed:
            raise ValueError(f"{self.type} contains fields that are not allowed")
        return self


class AIExplorationStepResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_exploration_step_id: str
    session_id: str
    execution_attempt_id: str
    sequence: int = Field(ge=1)
    model_call_identity: str
    observation_identity: str
    action_identity: str
    status: Literal[
        "DECIDING", "EXECUTING", "SUCCEEDED", "FAILED", "COMPLETION_PROPOSED", "DISCARDED"
    ]
    observation: dict[str, object]
    action: AIExplorationBrowserAction | None
    action_result: dict[str, object] | None
    sanitized_reason: str | None
    failure_code: str | None
    state_version: int = Field(ge=1)
    identity_lease_generation: int = Field(ge=1)
    runner_lease_generation: int = Field(ge=1)
    started_at: datetime
    completed_at: datetime | None


class AIExplorationSessionResponse(BaseModel):
    data: AIExplorationSessionResource
    correlation_id: str


class AIExplorationStepListResponse(BaseModel):
    items: list[AIExplorationStepResource]
    correlation_id: str
