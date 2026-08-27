"""Fail-fast database schema compatibility checks for API startup and developer tooling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platform_common.environment import find_repository_root
from platform_common.migrations import discover_migrations
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from platform_api.models import Base

FLYWAY_HISTORY_TABLE = "flyway_schema_history"
SUPPORTED_MYSQL_SERIES = "8.4"


@dataclass(frozen=True)
class SchemaPreflightFailure(RuntimeError):
    """Safe startup blocker containing only a stable code and non-secret metadata."""

    code: str
    metadata: dict[str, object]

    def __str__(self) -> str:
        return self.code


def _authority_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    root = find_repository_root(Path(__file__))
    return root / "docs" / "authority"


def validate_mapped_schema_shape(engine: Engine) -> dict[str, int]:
    """Require every SQLAlchemy-mapped table/column consumed by the API to exist."""
    inspector = inspect(engine)
    missing_tables: list[str] = []
    missing_columns: list[str] = []
    mapped_columns = 0
    mapped_tables = tuple(Base.metadata.tables.values())
    for table in mapped_tables:
        mapped_columns += len(table.columns)
        if not inspector.has_table(table.name):
            missing_tables.append(table.name)
            continue
        actual_columns = {str(item["name"]) for item in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in actual_columns:
                missing_columns.append(f"{table.name}.{column.name}")
    if missing_tables or missing_columns:
        raise SchemaPreflightFailure(
            "DATABASE_SCHEMA_SHAPE_MISMATCH",
            {
                "missing_tables": tuple(sorted(missing_tables)),
                "missing_columns": tuple(sorted(missing_columns)),
            },
        )
    return {
        "mapped_table_count": len(mapped_tables),
        "mapped_column_count": mapped_columns,
    }


def _flyway_history(engine: Engine) -> list[dict[str, Any]]:
    inspector = inspect(engine)
    if not inspector.has_table(FLYWAY_HISTORY_TABLE):
        raise SchemaPreflightFailure("FLYWAY_SCHEMA_HISTORY_MISSING", {})
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT installed_rank, version, description, type, script, success "
                f"FROM {FLYWAY_HISTORY_TABLE} ORDER BY installed_rank"
            )
        ).mappings()
        return [dict(row) for row in rows]


def run_schema_preflight(
    engine: Engine,
    *,
    authority_root: Path | None = None,
) -> dict[str, object]:
    """Verify MySQL series, Flyway head/history, and the API's mapped schema surface."""
    authority = _authority_root(authority_root)
    migrations = discover_migrations(authority)
    expected_head = migrations[-1]
    try:
        with engine.connect() as connection:
            mysql_version = str(connection.execute(text("SELECT VERSION()")).scalar_one())
        if not (
            mysql_version == SUPPORTED_MYSQL_SERIES
            or mysql_version.startswith(SUPPORTED_MYSQL_SERIES + ".")
        ):
            raise SchemaPreflightFailure(
                "MYSQL_VERSION_UNSUPPORTED",
                {"mysql_version": mysql_version, "required_series": SUPPORTED_MYSQL_SERIES},
            )
        history = _flyway_history(engine)
        failed = [row for row in history if not bool(row.get("success"))]
        if failed:
            raise SchemaPreflightFailure(
                "FLYWAY_HISTORY_CONTAINS_FAILED_MIGRATION",
                {"failed_count": len(failed)},
            )
        versioned = [row for row in history if row.get("version") not in {None, ""}]
        if not versioned:
            raise SchemaPreflightFailure("FLYWAY_HISTORY_EMPTY", {})
        latest = versioned[-1]
        latest_version = str(latest.get("version"))
        expected_version = str(expected_head["version"])
        if latest_version != expected_version:
            raise SchemaPreflightFailure(
                "DATABASE_MIGRATION_HEAD_MISMATCH",
                {
                    "expected_version": expected_version,
                    "actual_version": latest_version,
                    "expected_script": str(expected_head["name"]),
                },
            )
        shape = validate_mapped_schema_shape(engine)
    except SchemaPreflightFailure:
        raise
    except SQLAlchemyError as exc:
        raise SchemaPreflightFailure(
            "DATABASE_SCHEMA_PREFLIGHT_QUERY_FAILED",
            {"exception_type": type(exc).__name__},
        ) from None
    return {
        "status": "PASS",
        "mysql_version": mysql_version,
        "migration_head": str(expected_head["name"]),
        "migration_version": int(expected_head["version"]),
        "flyway_history_rows": len(history),
        **shape,
    }
