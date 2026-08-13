"""Problem-details foundation shared by future formal API implementations."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "about:blank"
    title: str
    status: int = Field(ge=400, le=599)
    code: str
    detail: str | None = None
    correlation_id: str | None = None
    field_errors: list[dict[str, str]] | None = None


class PlatformError(Exception):
    def __init__(
        self,
        *,
        title: str,
        detail: str,
        code: str = "INTERNAL_ERROR",
        status: int = 500,
        type: str = "about:blank",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.title = title
        self.detail = detail
        self.code = code
        self.status = status
        self.type = type
        self.headers = dict(headers or {})
