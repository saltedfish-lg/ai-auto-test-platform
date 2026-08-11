"""Safe paths to the current living-authority OpenAPI and event schema sources."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
SCHEMA_NAME = re.compile(r"^[a-z0-9_.-]+\.schema\.json$")


@dataclass(frozen=True, slots=True)
class AuthoritySources:
    authority_root: Path

    def __post_init__(self) -> None:
        required = (self.openapi, self.event_registry)
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError("current authority sources missing: " + ", ".join(missing))

    @property
    def openapi(self) -> Path:
        return self.authority_root / "编码权威事实" / "OPENAPI" / "openapi.yaml"

    @property
    def event_registry(self) -> Path:
        return self.authority_root / "编码权威事实" / "EVENT_CONTRACTS" / "event-registry.yaml"

    def load_event_schema(self, name: str) -> dict[str, object]:
        if SCHEMA_NAME.fullmatch(name) is None:
            raise ValueError("invalid event schema name")
        path = self.authority_root / "编码权威事实" / "EVENT_CONTRACTS" / "schemas" / name
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise TypeError("event schema must be a JSON object")
        return document
