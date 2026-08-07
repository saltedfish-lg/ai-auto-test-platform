"""Problem-details foundation shared by future formal API implementations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "about:blank"
    title: str
    status: int = Field(ge=400, le=599)
    detail: str
    correlation_id: str | None = None


class PlatformError(Exception):
    def __init__(
        self,
        *,
        title: str,
        detail: str,
        status: int = 500,
        type: str = "about:blank",
    ) -> None:
        super().__init__(detail)
        self.title = title
        self.detail = detail
        self.status = status
        self.type = type
