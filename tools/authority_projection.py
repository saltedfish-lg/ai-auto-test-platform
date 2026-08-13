#!/usr/bin/env python3
"""Generate/check non-authoritative Markdown/CSV projections from Living Authority sources."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from typing import Any

import yaml

YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

def _yaml_load(text: str):
    return yaml.load(text, Loader=YAML_LOADER)

from current_facts import derive_current_facts

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "docs" / "authority"
SYSTEM_SOURCE = AUTHORITY / "编码权威事实" / "SYSTEM_DESIGN.yaml"
SYSTEM_PROJECTION = AUTHORITY / "编码权威事实" / "SYSTEM_DESIGN.md"
STATE_SOURCE = AUTHORITY / "编码权威事实" / "STATE_OWNER_REGISTRY" / "state-owner-registry.yaml"
STATE_PROJECTION = AUTHORITY / "编码权威事实" / "STATE_OWNER_REGISTRY" / "state-owner-registry.md"
STATE_CSV_PROJECTION = AUTHORITY / "编码权威事实" / "STATE_OWNER_REGISTRY" / "state-owner-registry.csv"
ACCEPTANCE_SOURCE = AUTHORITY / "编码权威事实" / "ACCEPTANCE_CLOSURE" / "acceptance-closure.json"
ACCEPTANCE_CSV_PROJECTION = AUTHORITY / "编码权威事实" / "ACCEPTANCE_CLOSURE" / "acceptance-closure.csv"
PERMISSION_SOURCE = AUTHORITY / "编码权威事实" / "PERMISSION_CLOSURE" / "permission-closure.yaml"
ROLE_MATRIX_PROJECTION = AUTHORITY / "编码权威事实" / "PERMISSION_CLOSURE" / "role-permission-matrix.csv"
OPENAPI_SOURCE = AUTHORITY / "编码权威事实" / "OPENAPI" / "openapi.yaml"
AUTH_SOURCE = AUTHORITY / "编码权威事实" / "AUTHENTICATION_CONTRACT" / "authentication-contract.yaml"
OPERATION_PERMISSION_PROJECTION = AUTHORITY / "编码权威事实" / "OPENAPI" / "operation-permission-mapping.csv"
CORE_OBJECT_SOURCE = AUTHORITY / "核心对象、业务规则与生命周期" / "核心对象、业务规则与生命周期.yaml"
DATABASE_SCHEMA_SOURCE = AUTHORITY / "编码权威事实" / "DATABASE_DDL" / "database-schema.yaml"
OBJECT_TABLE_MAPPING_PROJECTION = AUTHORITY / "编码权威事实" / "DATABASE_DDL" / "object-table-mapping.csv"
MYSQL_ASSERTIONS_TEMPLATE = AUTHORITY / "validation" / "mysql84_assertions.template.sql"
MYSQL_ASSERTIONS_PROJECTION = AUTHORITY / "validation" / "mysql84_assertions.sql"

AUTH_PROJECTION_PRESENTATION = {
    "AUTH-OBJ-001": {"name": "平台用户凭据", "lifecycle_id": "AUTH-LC-001", "state_fields": "lifecycle_status|force_password_change|credential_version|locked_until", "aggregate_id": "OBJ-001"},
    "AUTH-OBJ-002": {"name": "认证Refresh Session", "lifecycle_id": "AUTH-LC-002", "state_fields": "lifecycle_status|session_version|credential_version", "aggregate_id": "AUTH-OBJ-001"},
    "AUTH-OBJ-003": {"name": "认证安全审计", "lifecycle_id": "AUTH-LC-003", "state_fields": "occurred_at", "aggregate_id": "OBJ-001"},
    "AUTH-OBJ-004": {"name": "认证来源限流窗口", "lifecycle_id": "AUTH-LC-004", "state_fields": "request_count|expires_at|row_version", "aggregate_id": "OBJ-001"},
}


def _load(path: Path) -> dict[str, Any]:
    value = _yaml_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"projection source must be a mapping: {path}")
    return value


def _join(values: list[Any]) -> str:
    return " / ".join(str(v).replace("|", "\\|") for v in values)



def _csv_bytes(fieldnames: list[str], rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    return buffer.getvalue().encode("utf-8-sig")


def render_system_design() -> str:
    data = _load(SYSTEM_SOURCE)
    facts = derive_current_facts(ROOT)
    db = data.get("database_contract", {})
    runtime = data.get("runtime_gate_contract", {})
    auth = data.get("authentication_contract", {})
    stack = data.get("current_stack", {})
    migration = facts["migration"]["file_chain"]
    gate_rows = runtime.get("gates", [])
    lines = [
        "# AI自动化测试执行平台系统设计（当前 Living Authority 阅读投影）",
        "",
        "> GENERATED_PROJECTION · NON_AUTHORITATIVE · DO_NOT_EDIT_MANUALLY  ",
        "> 权威源：`SYSTEM_DESIGN.yaml`；权威模型：`SINGLE_LIVING_AUTHORITY`；生成器：`tools/authority_projection.py`。",
        "",
        "## 当前架构",
        "",
        str(data.get("architecture_style", "")),
        "",
        "## 当前工程事实",
        "",
        f"- 前端：`{stack.get('frontend', '')}`；API：`{stack.get('api', '')}`；Runner：`{stack.get('runner', '')}`。",
        f"- 状态维度：{facts['domain']['state_dimension_count']}。",
        f"- 数据库：{facts['database']['table_count']} 张表；Migration：`{migration}`。",
        f"- RBAC：{facts['rbac']['permission_count']} 个权限点、{facts['rbac']['role_count']} 个角色模板、{facts['rbac']['mapping_count']} 条映射。",
        f"- 认证实现状态：`{runtime.get('implementation_status', data.get('metadata', {}).get('implementation_release_readiness', ''))}`。",
        f"- 平台发布状态：`{runtime.get('platform_release_status', '')}`。",
        f"- 权限解析：{auth.get('permission_resolution', '每个受保护请求实时读取关系型RBAC、项目职责和数据范围。')}",
        "",
        "## Runtime Gates",
        "",
        "|Gate|Status|Evidence/Blocker|",
        "|---|---|---|",
    ]
    for gate in gate_rows:
        if not isinstance(gate, dict):
            continue
        evidence = gate.get("evidence") or gate.get("blocker") or gate.get("note") or ""
        lines.append(f"|{gate.get('gate_id','')}|{gate.get('status','')}|{str(evidence).replace('|','\\|')}|")
    lines.extend([
        "",
        "## Authority 规则",
        "",
        "- 当前事实源仅为 `docs/authority/**` 的 Single Living Authority。",
        "- 本文件是生成投影，不得人工编辑；`python tools/authority_projection.py check` 必须通过。",
        "",
    ])
    return "\n".join(lines)


def render_state_owner() -> str:
    data = _load(STATE_SOURCE)
    owners = data.get("state_owners", [])
    auth = data.get("authentication_state_owners", [])
    lines = [
        "# 状态Owner注册表（当前 Living Authority 阅读投影）",
        "",
        "> GENERATED_PROJECTION · NON_AUTHORITATIVE · DO_NOT_EDIT_MANUALLY  ",
        "> 权威源：`state-owner-registry.yaml`；生成器：`tools/authority_projection.py`。",
        "",
        "- Authority: `SINGLE_LIVING_AUTHORITY`",
        f"- 状态维度：{len(owners)}",
        f"- 认证补充Owner：{len(auth)}",
        "",
        "|ID|对象|维度|初始值|值域|",
        "|---|---|---|---|---|",
    ]
    for item in owners:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"|{item.get('state_dimension_id','')}|{str(item.get('object_name','')).replace('|','\\|')}|"
            f"{str(item.get('dimension_name','')).replace('|','\\|')}|{item.get('initial_value','')}|"
            f"{_join(item.get('values', []))}|"
        )
    lines.extend(["", "## 认证补充Owner", "", "|ID|语义|对象|Owner|持久化字段|", "|---|---|---|---|---|"])
    for item in auth:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"|{item.get('state_semantic_id','')}|{item.get('semantic','')}|{item.get('object_id','')}|"
            f"{item.get('owner','')}|{_join(item.get('persistence_fields', []))}|"
        )
    lines.extend(["", "本投影只用于阅读；状态事实以 YAML 为准。", ""])
    return "\n".join(lines)


def render_state_owner_csv() -> bytes:
    """Render the compact CSV projection from the canonical state-owner YAML."""
    data = _load(STATE_SOURCE)
    rows: list[dict[str, Any]] = []
    for item in data.get("state_owners", []):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "state_dimension_id": item.get("state_dimension_id", ""),
                "object_id": item.get("object_id", ""),
                "object_name": item.get("object_name", ""),
                "dimension_name": item.get("dimension_name", ""),
                "persistence_field": item.get("persistence_field", ""),
                "owner": item.get("owner", ""),
                "initial_value": item.get("initial_value", ""),
                "terminal_values": "|".join(str(v) for v in item.get("terminal_values", [])),
                "values": "|".join(str(v) for v in item.get("values", [])),
            }
        )
    return _csv_bytes(
        ["state_dimension_id", "object_id", "object_name", "dimension_name", "persistence_field", "owner", "initial_value", "terminal_values", "values"],
        rows,
    )


def render_acceptance_csv() -> bytes:
    payload = json.loads(ACCEPTANCE_SOURCE.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in payload.get("acceptance_closure", []):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "acceptance_id": item.get("acceptance_id", ""),
                "requirement_ids": "|".join(str(v) for v in item.get("requirement_ids", [])),
                "invariant_id": item.get("invariant_id", "") or "",
                "rule_id": item.get("rule_id", "") or "",
                "test_id": item.get("test_id", ""),
                "priority": item.get("priority", ""),
                "status": item.get("status", ""),
                "evidence_status": item.get("evidence_status", ""),
                "evidence_spec_id": item.get("evidence_spec_id", ""),
                "action": item.get("action", ""),
                "expected_description": json.dumps(item.get("expected_response", {}), ensure_ascii=False),
            }
        )
    return _csv_bytes(
        ["acceptance_id", "requirement_ids", "invariant_id", "rule_id", "test_id", "priority", "status", "evidence_status", "evidence_spec_id", "action", "expected_description"],
        rows,
    )


def render_role_permission_matrix_csv() -> bytes:
    payload = _load(PERMISSION_SOURCE)
    rows = [
        {key: item.get(key, "") for key in ("mapping_id", "role_id", "permission_id", "permission_code", "decision", "data_scope", "conditions")}
        for item in payload.get("role_permission_mappings", [])
        if isinstance(item, dict)
    ]
    return _csv_bytes(["mapping_id", "role_id", "permission_id", "permission_code", "decision", "data_scope", "conditions"], rows)


def _primary_key_text(table: dict[str, Any] | None) -> str:
    if not table:
        return ""
    value = table.get("primary_key", "")
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return str(value or "")


def render_object_table_mapping_csv() -> bytes:
    """Render the object-to-persistence crosswalk from canonical object/auth/schema facts."""
    core = _load(CORE_OBJECT_SOURCE)
    schema = _load(DATABASE_SCHEMA_SOURCE)
    auth = _load(AUTH_SOURCE)
    tables_by_object = {
        str(item.get("object_id")): item
        for item in schema.get("tables", [])
        if isinstance(item, dict) and item.get("object_id")
    }
    state_fields: dict[str, list[str]] = {}
    for item in core.get("state_dimensions", []):
        if not isinstance(item, dict) or not item.get("object_id"):
            continue
        field = str(item.get("persistence_field") or "")
        if field:
            state_fields.setdefault(str(item["object_id"]), []).append(field)

    rows: list[dict[str, Any]] = []
    for item in core.get("objects", []):
        if not isinstance(item, dict):
            continue
        object_id = str(item.get("object_id", ""))
        table = tables_by_object.get(object_id)
        if table:
            persistence = "TABLE"
        elif item.get("object_type") == "VALUE_OBJECT":
            persistence = "EMBEDDED_VALUE"
        else:
            persistence = "SERVICE_OR_EXTERNAL_NOT_PERSISTED"
        rows.append({
            "object_id": object_id,
            "name": item.get("canonical_name_zh", ""),
            "object_type": item.get("object_type", ""),
            "aggregate_id": item.get("aggregate_id") or "",
            "persistence_strategy": persistence,
            "table_name": table.get("table_name", "") if table else "",
            "primary_key": _primary_key_text(table),
            "lifecycle_id": item.get("lifecycle_id") or "",
            "state_fields": "|".join(state_fields.get(object_id, [])),
        })

    for item in auth.get("supporting_objects", []):
        if not isinstance(item, dict):
            continue
        object_id = str(item.get("object_id", ""))
        presentation = AUTH_PROJECTION_PRESENTATION.get(object_id, {})
        rows.append({
            "object_id": object_id,
            "name": presentation.get("name", item.get("canonical_name", "")),
            "object_type": "AUTHENTICATION_SUPPORT",
            "aggregate_id": presentation.get("aggregate_id", item.get("aggregate_owner", "")),
            "persistence_strategy": "TABLE",
            "table_name": item.get("table", ""),
            "primary_key": str(item.get("primary_key", "")).replace("+", "|"),
            "lifecycle_id": presentation.get("lifecycle_id", ""),
            "state_fields": presentation.get("state_fields", ""),
        })
    return _csv_bytes(
        ["object_id", "name", "object_type", "aggregate_id", "persistence_strategy", "table_name", "primary_key", "lifecycle_id", "state_fields"],
        rows,
    )


def render_operation_permission_mapping_csv() -> bytes:
    api = _load(OPENAPI_SOURCE)
    auth = _load(AUTH_SOURCE)
    p1_operation_ids = {item.get("operation_id") for item in auth.get("operations", []) if isinstance(item, dict)}
    rows: list[dict[str, Any]] = []
    for path_value, path_item in api.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options", "head", "trace"} or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId", "")
            rows.append(
                {
                    "operationId": operation_id,
                    "method": method.upper(),
                    "path": path_value,
                    "permission_code": operation.get("x-permission-code") or "",
                    "approval_status": "LIVING_AUTHORITY_P1" if operation_id in p1_operation_ids else "CURRENT_LIVING_AUTHORITY",
                }
            )
    return _csv_bytes(["operationId", "method", "path", "permission_code", "approval_status"], rows)


def render_mysql84_assertions() -> bytes:
    facts = derive_current_facts(ROOT)
    template = MYSQL_ASSERTIONS_TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{{MIGRATION_CHAIN}}": facts["migration"]["chain"],
        "{{TABLE_COUNT}}": str(facts["database"]["table_count"]),
        "{{PERMISSION_COUNT}}": str(facts["rbac"]["permission_count"]),
        "{{ROLE_COUNT}}": str(facts["rbac"]["role_count"]),
        "{{RBAC_MAPPING_COUNT}}": str(facts["rbac"]["mapping_count"]),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    if "{{" in template or "}}" in template:
        raise ValueError("unresolved mysql84 assertion template token")
    return template.encode("utf-8")


TEXT_PROJECTIONS = {
    SYSTEM_PROJECTION: render_system_design,
    STATE_PROJECTION: render_state_owner,
}
BYTE_PROJECTIONS = {
    STATE_CSV_PROJECTION: render_state_owner_csv,
    ACCEPTANCE_CSV_PROJECTION: render_acceptance_csv,
    ROLE_MATRIX_PROJECTION: render_role_permission_matrix_csv,
    OPERATION_PERMISSION_PROJECTION: render_operation_permission_mapping_csv,
    OBJECT_TABLE_MAPPING_PROJECTION: render_object_table_mapping_csv,
    MYSQL_ASSERTIONS_PROJECTION: render_mysql84_assertions,
}


def check() -> list[str]:
    errors: list[str] = []
    for path, renderer in TEXT_PROJECTIONS.items():
        expected = renderer()
        actual = path.read_text(encoding="utf-8") if path.is_file() else ""
        if actual != expected:
            errors.append(path.relative_to(ROOT).as_posix())
    for path, renderer in BYTE_PROJECTIONS.items():
        expected = renderer()
        actual = path.read_bytes() if path.is_file() else b""
        if actual != expected:
            errors.append(path.relative_to(ROOT).as_posix())
    return errors


def write() -> None:
    for path, renderer in TEXT_PROJECTIONS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(renderer(), encoding="utf-8", newline="\n")
    for path, renderer in BYTE_PROJECTIONS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(renderer())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "write"))
    args = parser.parse_args()
    if args.command == "write":
        write()
        print("AUTHORITY_PROJECTIONS_WRITTEN")
        return 0
    errors = check()
    if errors:
        print("AUTHORITY_PROJECTION_DRIFT")
        for rel in errors:
            print(rel)
        return 1
    print("AUTHORITY_PROJECTIONS_CONSISTENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
