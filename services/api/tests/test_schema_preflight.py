from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from platform_api import schema_preflight
from platform_api.schema_preflight import SchemaPreflightFailure


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one(self) -> object:
        return self.value


class _Connection:
    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, _statement: object) -> _ScalarResult:
        return _ScalarResult("8.4.11")


class _Engine:
    def connect(self) -> _Connection:
        return _Connection()


def test_schema_preflight_accepts_exact_flyway_head_and_mapped_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        schema_preflight,
        "discover_migrations",
        lambda _root: [{"version": 13, "name": "V13__business_terminal_foundation.sql"}],
    )
    monkeypatch.setattr(
        schema_preflight,
        "_flyway_history",
        lambda _engine: [
            {
                "installed_rank": 11,
                "version": "13",
                "type": "SQL",
                "script": "V13__business_terminal_foundation.sql",
                "success": 1,
            }
        ],
    )
    monkeypatch.setattr(
        schema_preflight,
        "validate_mapped_schema_shape",
        lambda _engine: {"mapped_table_count": 10, "mapped_column_count": 40},
    )
    result = schema_preflight.run_schema_preflight(
        _Engine(),  # type: ignore[arg-type]
        authority_root=Path("/authority"),
    )
    assert result["status"] == "PASS"
    assert result["migration_version"] == 13
    assert result["mapped_table_count"] == 10


def test_schema_preflight_rejects_database_behind_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        schema_preflight,
        "discover_migrations",
        lambda _root: [{"version": 13, "name": "V13__business_terminal_foundation.sql"}],
    )
    monkeypatch.setattr(
        schema_preflight,
        "_flyway_history",
        lambda _engine: [{"version": "12", "success": 1}],
    )
    with pytest.raises(SchemaPreflightFailure) as raised:
        schema_preflight.run_schema_preflight(
            _Engine(),  # type: ignore[arg-type]
            authority_root=Path("/authority"),
        )
    assert raised.value.code == "DATABASE_MIGRATION_HEAD_MISMATCH"
    assert raised.value.metadata["actual_version"] == "12"
    assert raised.value.metadata["expected_version"] == "13"


def test_mapped_schema_shape_reports_missing_table_and_column_without_query_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    present_table = SimpleNamespace(
        name="atp_present_probe",
        columns=[SimpleNamespace(name="id"), SimpleNamespace(name="required_column")],
    )
    missing_table = SimpleNamespace(
        name="atp_missing_probe",
        columns=[SimpleNamespace(name="id")],
    )
    fake_metadata = SimpleNamespace(
        tables={present_table.name: present_table, missing_table.name: missing_table}
    )
    monkeypatch.setattr(schema_preflight, "Base", SimpleNamespace(metadata=fake_metadata))

    class _Inspector:
        def has_table(self, name: str) -> bool:
            return name != "atp_missing_probe"

        def get_columns(self, _name: str) -> list[dict[str, str]]:
            return [{"name": "id"}]

    monkeypatch.setattr(schema_preflight, "inspect", lambda _engine: _Inspector())
    with pytest.raises(SchemaPreflightFailure) as raised:
        schema_preflight.validate_mapped_schema_shape(object())  # type: ignore[arg-type]
    assert raised.value.code == "DATABASE_SCHEMA_SHAPE_MISMATCH"
    assert "atp_missing_probe" in raised.value.metadata["missing_tables"]
    assert "atp_present_probe.required_column" in raised.value.metadata["missing_columns"]
