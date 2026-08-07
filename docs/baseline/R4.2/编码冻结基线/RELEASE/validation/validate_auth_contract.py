#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml


RELEASE_ID = "PDBR-2026.08.07-R4.2"
AUTH_OPERATIONS = {
    "login_platform_user": ("post", "/api/v1/auth/login", False),
    "refresh_platform_session": ("post", "/api/v1/auth/refresh", False),
    "logout_platform_user": ("post", "/api/v1/auth/logout", False),
    "get_current_user": ("get", "/api/v1/auth/me", True),
    "change_current_user_password": ("post", "/api/v1/auth/change-password", True),
}
AUTH_SCHEMAS = {
    "LoginRequest",
    "AuthCookieActionRequest",
    "ChangePasswordRequest",
    "CurrentUserResource",
    "AuthenticationTokenResource",
    "AuthenticationResponse",
    "CurrentUserResponse",
    "AuthenticationErrorCode",
    "AuthenticationProblemDetails",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root
    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})
        if not passed:
            errors.append(f"{check_id}: {detail}")

    auth_path = root / "编码冻结基线/AUTHENTICATION_CONTRACT/authentication-contract.yaml"
    auth = yaml.safe_load(auth_path.read_text(encoding="utf-8"))
    add(
        "AUTH-CONTRACT-METADATA",
        auth["metadata"]["release_id"] == RELEASE_ID
        and auth["metadata"]["status"] == "FROZEN_IMPLEMENTABLE"
        and auth["metadata"]["pending_user_decisions"] == 0,
        f"release={auth['metadata']['release_id']}; status={auth['metadata']['status']}",
    )
    add(
        "AUTH-ARCHITECTURE-DECISION",
        auth["authentication"]["mechanism"] == "BEARER_JWT_ACCESS_WITH_REVOCABLE_REFRESH_SESSION"
        and auth["access_token"]["signing_algorithm"] == "RS256"
        and auth["access_token"]["ttl_seconds"] == 900
        and auth["refresh_session"]["ttl_seconds"] == 604800
        and auth["refresh_session"]["rotation"] == "REQUIRED_ON_EVERY_REFRESH"
        and auth["authentication"]["permissions_in_access_token"] is False,
        "RS256 access=900s; refresh=604800s; rotation required; permissions excluded",
    )
    password_hash = auth["password_hash"]
    add(
        "AUTH-PASSWORD-HASH",
        password_hash == {
            "algorithm": "Argon2id",
            "implementation": "成熟维护库；禁止自实现算法。",
            "phc_version": 19,
            "memory_cost_kib": 65536,
            "time_cost": 3,
            "parallelism": 1,
            "salt_length_bytes": 16,
            "hash_length_bytes": 32,
            "encoding": "PHC_STRING_INCLUDES_PARAMETERS_AND_SALT",
            "rehash_policy": "成功验证后发现版本或参数低于当前策略时，在同一安全事务中重新哈希并更新；不得降低参数。",
        },
        "Argon2id v19 m=65536 t=3 p=1 salt=16 hash=32",
    )
    policy = auth["password_policy"]
    add(
        "AUTH-PASSWORD-POLICY",
        policy["minimum_length"] == 12
        and policy["maximum_length"] == 128
        and set(policy["required_character_classes"]) == {"LETTER", "DIGIT"}
        and "不强制" in policy["periodic_expiry"],
        "password policy is complete and V1-bounded",
    )
    add(
        "AUTH-ADMIN-BOOTSTRAP",
        auth["admin_bootstrap"]["username"] == "admin"
        and "ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE" in auth["admin_bootstrap"]["automation_secret_input"]
        and auth["admin_bootstrap"]["force_password_change"] is True
        and "不覆盖" in auth["admin_bootstrap"]["repeated_execution"],
        "admin fixed; controlled secret input; force change; no overwrite",
    )
    add(
        "AUTH-STATE-MAPPING",
        auth["state_model"]["login_allowed_user_state"] == "ACTIVE"
        and "不新增ENABLED" in auth["state_model"]["enabled_normalization"]
        and "不增加security_status" in auth["state_model"]["security_normal_semantics"],
        "ACTIVE is canonical; NORMAL derived; no duplicate security_status",
    )

    api = yaml.safe_load((root / "编码冻结基线/OPENAPI/openapi.yaml").read_text(encoding="utf-8"))
    operation_index: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for path, item in api["paths"].items():
        for method, operation in item.items():
            if isinstance(operation, dict) and operation.get("operationId"):
                operation_index[operation["operationId"]] = (method.lower(), path, operation)
    operation_errors = []
    for operation_id, (method, path, bearer_required) in AUTH_OPERATIONS.items():
        actual = operation_index.get(operation_id)
        if actual is None or actual[:2] != (method, path):
            operation_errors.append(operation_id)
            continue
        security = actual[2].get("security")
        if bearer_required and security != [{"BearerAuth": []}]:
            operation_errors.append(f"{operation_id}:bearer")
        if not bearer_required and security != []:
            operation_errors.append(f"{operation_id}:public_or_cookie")
    add("AUTH-OPENAPI-OPERATIONS", not operation_errors, f"errors={operation_errors}")
    schemas = api["components"]["schemas"]
    missing_schemas = AUTH_SCHEMAS - set(schemas)
    add("AUTH-OPENAPI-SCHEMAS", not missing_schemas, f"missing={sorted(missing_schemas)}")
    error_codes = set(schemas["AuthenticationErrorCode"]["enum"])
    required_401 = set(auth["error_semantics"]["unauthenticated_401"])
    required_403 = set(auth["error_semantics"]["forbidden_403"])
    add(
        "AUTH-ERROR-CODES",
        required_401 | required_403 == error_codes and required_401.isdisjoint(required_403),
        f"401={len(required_401)}; 403={len(required_403)}",
    )

    schema = yaml.safe_load((root / "编码冻结基线/DATABASE_DDL/database-schema.yaml").read_text(encoding="utf-8"))
    tables = {table["table_name"]: table for table in schema["tables"]}
    credential = tables.get("atp_platform_user_credential", {})
    session = tables.get("atp_auth_refresh_session", {})
    credential_fks = {fk["name"] for fk in credential.get("foreign_keys", [])}
    session_fks = {fk["name"] for fk in session.get("foreign_keys", [])}
    add(
        "AUTH-CREDENTIAL-PHYSICAL-MODEL",
        credential.get("object_id") == "AUTH-OBJ-001"
        and credential.get("primary_key") == ["credential_id"]
        and any(key["columns"] == ["user_id"] for key in credential.get("unique_keys", []))
        and "fk_atp_platform_user_credential_user" in credential_fks,
        "credential table, user uniqueness and FK",
    )
    add(
        "AUTH-SESSION-PHYSICAL-MODEL",
        session.get("object_id") == "AUTH-OBJ-002"
        and session.get("primary_key") == ["session_id"]
        and any(key["columns"] == ["token_hash"] for key in session.get("unique_keys", []))
        and {"fk_atp_auth_refresh_session_credential", "fk_atp_auth_refresh_session_replacement"}.issubset(session_fks),
        "refresh session table, token uniqueness and FKs",
    )
    add(
        "AUTH-MIGRATION-ORDER",
        schema["migration_files"]
        == ["V3__platform_contract_rebuild.sql", "V4__rbac_seed_data.sql", "V5__platform_authentication_contract.sql"],
        str(schema["migration_files"]),
    )

    owner_registry = yaml.safe_load((root / "编码冻结基线/STATE_OWNER_REGISTRY/state-owner-registry.yaml").read_text(encoding="utf-8"))
    owners = owner_registry.get("authentication_state_owners", [])
    semantic_ids = [owner["state_semantic_id"] for owner in owners]
    persistence_fields = [field for owner in owners for field in owner["persistence_fields"]]
    add(
        "AUTH-STATE-OWNER-UNIQUENESS",
        len(owners) == 6 and len(semantic_ids) == len(set(semantic_ids)) and len(persistence_fields) == len(set(persistence_fields)),
        f"owners={len(owners)}; fields={len(persistence_fields)}",
    )

    permission = yaml.safe_load((root / "编码冻结基线/PERMISSION_CLOSURE/permission-closure.yaml").read_text(encoding="utf-8"))
    maps = permission["role_permission_mappings"]
    super_admin_allowed = sum(
        item["role_id"] == "ROLE-SUPER-ADMIN" and item["decision"] == "ALLOWED" for item in maps
    )
    add(
        "AUTH-RBAC-CLOSURE-UNCHANGED",
        len(permission["permission_catalog"]) == 50
        and len(permission["role_templates"]) == 12
        and len(maps) == 600
        and super_admin_allowed == 50,
        f"50/12/600; super_admin_allowed={super_admin_allowed}",
    )

    acceptance = json.loads((root / "编码冻结基线/ACCEPTANCE_CLOSURE/acceptance-closure.json").read_text(encoding="utf-8"))
    p1_items = [
        item
        for item in acceptance["acceptance_closure"]
        if 1602 <= int(item["acceptance_id"].rsplit("-", 1)[1]) <= 1688
    ]
    governance = acceptance.get("p1_authentication_governance", {})
    add(
        "AUTH-ACCEPTANCE-SPECIFIED-NOT-STARTED",
        len(p1_items) == 87
        and all(item["status"] == "SPECIFIED" for item in p1_items)
        and all(item["evidence_status"] in {"EXPECTED_NOT_EXECUTED", "NOT_STARTED"} for item in p1_items)
        and governance.get("revised_items") == 87
        and governance.get("new_items") == 0,
        f"p1_items={len(p1_items)}; revised={governance.get('revised_items')}",
    )

    release = yaml.safe_load((root / "编码冻结基线/RELEASE/platform_design_baseline_release.yaml").read_text(encoding="utf-8"))
    add(
        "AUTH-RELEASE-CLOSED",
        release["release_id"] == RELEASE_ID
        and release["pending_user_decisions"] == 0
        and release["authentication_contract_status"] == "FROZEN_IMPLEMENTABLE"
        and release["code_readiness"] == "READY_FOR_P1_IMPLEMENTATION",
        f"pending={release['pending_user_decisions']}; readiness={release['code_readiness']}",
    )

    forbidden_literal_hits = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml", ".json", ".md", ".sql", ".py", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if re.search(r"(?i)ATP_BOOTSTRAP_ADMIN_PASSWORD\s*=\s*[^\s<]+", text):
            forbidden_literal_hits.append(path.relative_to(root).as_posix())
    add("AUTH-NO-BOOTSTRAP-SECRET-LITERAL", not forbidden_literal_hits, str(forbidden_literal_hits))

    report = {
        "release_id": RELEASE_ID,
        "validator": "validate_auth_contract.py",
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "PASS" if not errors else "FAIL",
        "checks": checks,
        "error_count": len(errors),
        "errors": errors,
        "metrics": {
            "auth_operations": len(AUTH_OPERATIONS),
            "auth_schemas": len(AUTH_SCHEMAS),
            "authentication_state_owners": len(owners),
            "p1_acceptance_items": len(p1_items),
            "permissions": len(permission["permission_catalog"]),
            "roles": len(permission["role_templates"]),
            "mappings": len(maps),
        },
    }
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
