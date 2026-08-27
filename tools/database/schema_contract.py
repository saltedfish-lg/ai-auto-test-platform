"""Strict current-database shape checks derived from the database Living Authority."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

FLYWAY_HISTORY_TABLE = "flyway_schema_history"


@dataclass(frozen=True)
class AuthoritySchemaMismatch(RuntimeError):
    code: str
    metadata: dict[str, object]

    def __str__(self) -> str:
        return self.code


def load_expected_columns(authority_root: Path) -> dict[str, set[str]]:
    path = authority_root / "编码权威事实" / "DATABASE_DDL" / "database-schema.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("tables"), list):
        raise AuthoritySchemaMismatch("DATABASE_AUTHORITY_SCHEMA_INVALID", {})
    expected: dict[str, set[str]] = {}
    for item in payload["tables"]:
        if not isinstance(item, dict) or not isinstance(item.get("table_name"), str):
            raise AuthoritySchemaMismatch("DATABASE_AUTHORITY_SCHEMA_INVALID", {})
        columns = item.get("columns")
        if not isinstance(columns, list):
            raise AuthoritySchemaMismatch("DATABASE_AUTHORITY_SCHEMA_INVALID", {})
        names = {
            str(column["name"])
            for column in columns
            if isinstance(column, dict) and isinstance(column.get("name"), str)
        }
        if len(names) != len(columns):
            raise AuthoritySchemaMismatch("DATABASE_AUTHORITY_SCHEMA_INVALID", {})
        expected[str(item["table_name"])] = names
    return expected


def validate_authority_schema_shape(
    connection: object,
    *,
    database: str,
    authority_root: Path,
    allow_flyway_history: bool,
) -> dict[str, int]:
    """Compare all formal tables/columns with one information_schema snapshot."""
    expected = load_expected_columns(authority_root)
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=%s AND table_type='BASE TABLE'",
            (database,),
        )
        actual_tables = {str(row[0]) for row in cursor.fetchall()}
        cursor.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema=%s",
            (database,),
        )
        actual_columns: dict[str, set[str]] = {}
        for table_name, column_name in cursor.fetchall():
            actual_columns.setdefault(str(table_name), set()).add(str(column_name))

    allowed_extra = {FLYWAY_HISTORY_TABLE} if allow_flyway_history else set()
    expected_tables = set(expected)
    missing_tables = sorted(expected_tables - actual_tables)
    unexpected_tables = sorted(actual_tables - expected_tables - allowed_extra)
    missing_columns: list[str] = []
    unexpected_columns: list[str] = []
    for table_name, expected_names in expected.items():
        if table_name not in actual_tables:
            continue
        actual_names = actual_columns.get(table_name, set())
        missing_columns.extend(
            f"{table_name}.{name}" for name in sorted(expected_names - actual_names)
        )
        unexpected_columns.extend(
            f"{table_name}.{name}" for name in sorted(actual_names - expected_names)
        )
    if missing_tables or unexpected_tables or missing_columns or unexpected_columns:
        raise AuthoritySchemaMismatch(
            "DATABASE_AUTHORITY_SCHEMA_SHAPE_MISMATCH",
            {
                "missing_tables": tuple(missing_tables),
                "unexpected_tables": tuple(unexpected_tables),
                "missing_columns": tuple(missing_columns),
                "unexpected_columns": tuple(unexpected_columns),
            },
        )
    return {
        "authority_table_count": len(expected_tables),
        "authority_column_count": sum(len(columns) for columns in expected.values()),
    }
