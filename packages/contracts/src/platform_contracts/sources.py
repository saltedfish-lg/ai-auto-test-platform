"""Safe paths to the read-only current OpenAPI and event schema sources."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

BASELINE_RELEASE_ID = "PDBR-2026.08.07-R4.2"
SCHEMA_NAME = re.compile(r"^[a-z0-9_.-]+\.schema\.json$")


@dataclass(frozen=True, slots=True)
class BaselineSources:
    baseline_root: Path

    def __post_init__(self) -> None:
        release = (
            self.baseline_root
            / "编码冻结基线"
            / "RELEASE"
            / "platform_design_baseline_release.yaml"
        )
        if not release.is_file():
            raise FileNotFoundError(f"current baseline release file not found under {self.baseline_root}")
        if f"release_id: {BASELINE_RELEASE_ID}" not in release.read_text(encoding="utf-8"):
            raise ValueError("baseline release_id does not match the current R4.2 release")

    @property
    def openapi(self) -> Path:
        return self.baseline_root / "编码冻结基线" / "OPENAPI" / "openapi.yaml"

    @property
    def event_registry(self) -> Path:
        return self.baseline_root / "编码冻结基线" / "EVENT_CONTRACTS" / "event-registry.yaml"

    def load_event_schema(self, name: str) -> dict[str, object]:
        if SCHEMA_NAME.fullmatch(name) is None:
            raise ValueError("invalid event schema name")
        path = self.baseline_root / "编码冻结基线" / "EVENT_CONTRACTS" / "schemas" / name
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise TypeError("event schema must be a JSON object")
        return document
