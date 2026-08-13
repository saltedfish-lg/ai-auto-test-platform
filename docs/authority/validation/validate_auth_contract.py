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

YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

def _yaml_load(text: str):
    return yaml.load(text, Loader=YAML_LOADER)

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))
from current_facts import derive_current_facts, discover_migrations  # noqa: E402


AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
AUTH_IMPLEMENTATION_STATUSES = {
    "AUTHORITY_UPDATED_IMPLEMENTATION_PENDING",
    "IMPLEMENTED_PENDING_RUNTIME_VALIDATION",
    "IMPLEMENTED_RUNTIME_VALIDATED",
}
CONFIRMED_PRODUCT_DECISIONS = {
    "GOV-P1-002": "SYSTEM_GENERATED_ONE_TIME_TEMP_CREDENTIAL",
    "GOV-P1-003": "SOURCE_RATE_LIMIT_ENABLED_MYSQL84",
    "GOV-P1-005": "PASSWORD_CHANGE_REVOKES_REFRESH_SESSIONS_AND_REAUTHENTICATES",
}
AUTH_OPERATIONS = {
    "login_platform_user": ("post", "/api/v1/auth/login", False),
    "refresh_platform_session": ("post", "/api/v1/auth/refresh", False),
    "logout_platform_user": ("post", "/api/v1/auth/logout", False),
    "get_current_user": ("get", "/api/v1/auth/me", True),
    "change_current_user_password": ("post", "/api/v1/auth/change-password", True),
    "create_user": ("post", "/api/v1/user", True),
    "reset_user_credential": ("post", "/api/v1/user/{id}/credential-reset", True),
    "enable_user": ("post", "/api/v1/user/{id}/enable", True),
    "disable_user": ("post", "/api/v1/user/{id}/disable", True),
    "create_user_role_binding": ("post", "/api/v1/user-role-binding", True),
    "revoke_user_role_binding": ("post", "/api/v1/user-role-binding/{id}/revoke", True),
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
    "OneTimeCredentialDeliveryResource",
    "OneTimeCredentialDeliveryResponse",
    "ResetUserCredentialRequest",
    "UserStateCommandRequest",
    "CreateUserRoleBindingRequest",
    "RevokeUserRoleBindingRequest",
    "UserRoleBindingResource",
    "UserRoleBindingResponse",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    repo_root = root.parents[1]
    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail})
        if not passed:
            errors.append(f"{check_id}: {detail}")

    auth_path = root / "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml"
    auth = _yaml_load(auth_path.read_text(encoding="utf-8"))
    system_design = _yaml_load((root / "编码权威事实/SYSTEM_DESIGN.yaml").read_text(encoding="utf-8"))
    implementation_status = system_design.get("runtime_gate_contract", {}).get("implementation_status")
    implementation_status_source = auth.get("metadata", {}).get("implementation_status_source")
    add(
        "AUTH-CONTRACT-METADATA",
        auth["metadata"]["status"] == "ACTIVE_CONTROLLED_MUTABLE_AUTHORITY"
        and auth["metadata"]["pending_user_decisions"] == 0
        and auth["metadata"].get("deferred_product_decisions") == 0
        and implementation_status_source == "SYSTEM_DESIGN.runtime_gate_contract.implementation_status"
        and implementation_status in AUTH_IMPLEMENTATION_STATUSES,
        (
            f"status={auth['metadata']['status']}; pending={auth['metadata']['pending_user_decisions']}; "
            f"deferred={auth['metadata'].get('deferred_product_decisions')}; "
            f"implementation={implementation_status}; source={implementation_status_source}"
        ),
    )

    placeholders = auth.get("product_decision_placeholders", [])
    decision_index = {
        item.get("decision_id"): item
        for item in auth.get("confirmed_product_decisions", [])
        if isinstance(item, dict) and item.get("decision_id")
    }
    decision_errors: list[str] = []
    if placeholders:
        decision_errors.append(f"placeholders={len(placeholders)}")
    if set(decision_index) != set(CONFIRMED_PRODUCT_DECISIONS):
        decision_errors.append(f"ids={sorted(decision_index)}")
    for decision_id, selected_option in CONFIRMED_PRODUCT_DECISIONS.items():
        item = decision_index.get(decision_id, {})
        if item.get("selected_option") != selected_option:
            decision_errors.append(f"{decision_id}:selected_option={item.get('selected_option')}")
        if item.get("status") != "CONFIRMED_IN_LIVING_AUTHORITY":
            decision_errors.append(f"{decision_id}:status={item.get('status')}")
    add(
        "AUTH-CONFIRMED-PRODUCT-DECISIONS",
        not decision_errors,
        f"GOV-P1-002/003/005 are confirmed in the living authority; errors={decision_errors}",
    )

    implementation_files = [
        repo_root / "services/api/src/platform_api/auth_service.py",
        repo_root / "services/api/src/platform_api/auth_router.py",
        repo_root / "services/api/src/platform_api/auth_hmac.py",
        repo_root / "services/api/src/platform_api/rate_limit.py",
        repo_root / "services/api/src/platform_api/user_admin_service.py",
        repo_root / "services/api/src/platform_api/security.py",
        repo_root / "services/api/src/platform_api/models.py",
        repo_root / "apps/web/src/views/LoginView.vue",
        repo_root / "apps/web/src/views/ChangePasswordView.vue",
        repo_root / "apps/web/src/stores/session.ts",
    ]
    missing_implementation_files = [
        path.relative_to(repo_root).as_posix() for path in implementation_files if not path.is_file()
    ]
    add(
        "AUTH-IMPLEMENTATION-STATUS-ALIGNMENT",
        implementation_status in AUTH_IMPLEMENTATION_STATUSES
        and implementation_status_source == "SYSTEM_DESIGN.runtime_gate_contract.implementation_status"
        and not missing_implementation_files,
        f"implementation_status={implementation_status}; source={implementation_status_source}; missing={missing_implementation_files}",
    )
    add(
        "AUTH-ARCHITECTURE-DECISION",
        auth["authentication"]["mechanism"] == "BEARER_JWT_ACCESS_WITH_REVOCABLE_REFRESH_SESSION"
        and auth["access_token"]["signing_algorithm"] == "RS256"
        and auth["access_token"].get("key_ring_source", "").startswith("ATP_JWT_KEY_RING_FILE")
        and auth["access_token"].get("key_ring_contract", {}).get("minimum_overlap_seconds") == 960
        and auth["access_token"]["ttl_seconds"] == 900
        and auth["refresh_session"]["ttl_seconds"] == 604800
        and auth["refresh_session"]["rotation"] == "REQUIRED_ON_EVERY_REFRESH"
        and auth["authentication"]["permissions_in_access_token"] is False,
        "RS256 access=900s; key-ring overlap=960s; refresh=604800s; rotation required; permissions excluded",
    )
    hmac_ring = auth.get("auth_hmac_key_ring", {})
    add(
        "AUTH-HMAC-KEY-RING",
        hmac_ring.get("configuration") == "ATP_AUTH_HMAC_MASTER_KEY_FILE"
        and hmac_ring.get("format") == "STRICT_JSON_RING"
        and hmac_ring.get("minimum_rotation_overlap_seconds") == 86400
        and set(hmac_ring.get("root_fields", [])) == {"ring_version", "active_key_id", "keys"}
        and "source-rate-limit" in hmac_ring.get("derivation", "")
        and "change-password-fingerprint" in hmac_ring.get("derivation", "")
        and "idempotency-storage-key" in hmac_ring.get("derivation", ""),
        "required strict JSON HMAC ring; 32-byte keys; 24h overlap; three HKDF domains",
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

    api = _yaml_load((root / "编码权威事实/OPENAPI/openapi.yaml").read_text(encoding="utf-8"))
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
    validation_response_errors = []
    for operation_id, (_, _, operation) in operation_index.items():
        responses = operation.get("responses", {})
        response_422 = responses.get("422", responses.get(422, {}))
        if response_422.get("$ref") != "#/components/responses/RequestValidationFailed":
            validation_response_errors.append(operation_id)
    add(
        "AUTH-REQUEST-VALIDATION-422",
        not validation_response_errors
        and "AUTH_REQUEST_VALIDATION_FAILED" in schemas["AuthenticationErrorCode"]["enum"]
        and api.get("components", {}).get("responses", {}).get("RequestValidationFailed", {}).get("content", {}).get("application/problem+json") is not None,
        f"operations_missing_422={validation_response_errors[:10]}; total={len(operation_index)}",
    )
    role_binding = auth.get("user_administration", {}).get("role_binding", {})
    auth_service_source = (REPO_ROOT / "services/api/src/platform_api/auth_service.py").read_text(encoding="utf-8")
    user_admin_source = (REPO_ROOT / "services/api/src/platform_api/user_admin_service.py").read_text(encoding="utf-8")
    realtime_rule = str(role_binding.get("project_scoped_realtime_authorization", ""))
    add(
        "AUTH-PROJECT-ROLE-BINDING-REALTIME-DUTY",
        "ProjectMember.role_id" in realtime_rule
        and "UserRoleBinding" in realtime_rule
        and "目标项目" in realtime_rule
        and "def require_project_permissions" in auth_service_source
        and "AuthorizationContext(" in auth_service_source
        and user_admin_source.count("require_project_permissions(") >= 3
        and "binding.project_id" in user_admin_source
        and "body.project_id" in user_admin_source,
        realtime_rule,
    )
    error_codes = set(schemas["AuthenticationErrorCode"]["enum"])
    required_401 = set(auth["error_semantics"]["unauthenticated_401"])
    required_403 = set(auth["error_semantics"]["forbidden_403"])
    required_errors = set().union(
        *(set(value) for key, value in auth["error_semantics"].items() if key.endswith(("_400", "_401", "_403", "_409", "_422", "_429", "_503")))
    )
    add(
        "AUTH-ERROR-CODES",
        required_errors == error_codes and required_401.isdisjoint(required_403),
        f"declared={len(required_errors)}; openapi={len(error_codes)}",
    )
    change_password = operation_index["change_current_user_password"][2]
    change_responses = change_password["responses"]
    change_204 = change_responses.get("204", change_responses.get(204, {}))
    add(
        "AUTH-CHANGE-PASSWORD-204-NO-TOKEN",
        bool(change_204)
        and "200" not in change_responses
        and 200 not in change_responses
        and "content" not in change_204
        and "Set-Cookie" not in change_204.get("headers", {}),
        f"responses={sorted(map(str, change_responses))}",
    )
    rate_response_errors = []
    for operation_id in ("login_platform_user", "refresh_platform_session"):
        responses = operation_index[operation_id][2]["responses"]
        limited = responses.get("429", responses.get(429, {}))
        unavailable = responses.get("503", responses.get(503, {}))
        if "Retry-After" not in limited.get("headers", {}):
            rate_response_errors.append(f"{operation_id}:Retry-After")
        if not unavailable:
            rate_response_errors.append(f"{operation_id}:503")
    add("AUTH-SOURCE-RATE-LIMIT-RESPONSES", not rate_response_errors, str(rate_response_errors))
    create_user = operation_index["create_user"][2]
    update_user_schema = schemas["UpdateUserRequest"]
    create_delivery = schemas["OneTimeCredentialDeliveryResource"]
    add(
        "AUTH-USER-GOVERNANCE-CONTRACT",
        create_user.get("x-permission-code") == "USER_CREATE"
        and create_user.get("x-additional-permission-codes") == ["ROLE_BIND"]
        and set(update_user_schema.get("properties", {})).isdisjoint({"username", "role_binding_id"})
        and "temporary_password" in create_delivery.get("properties", {})
        and "temporary_password" not in schemas["UserResource"].get("properties", {}),
        "create uses USER_CREATE+ROLE_BIND; generic update cannot rename/rebind; secret is delivery-only",
    )

    schema = _yaml_load((root / "编码权威事实/DATABASE_DDL/database-schema.yaml").read_text(encoding="utf-8"))
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
    audit = tables.get("atp_auth_security_audit", {})
    add(
        "AUTH-AUDIT-PHYSICAL-MODEL",
        audit.get("object_id") == "AUTH-OBJ-003"
        and audit.get("primary_key") == ["audit_id"]
        and audit.get("delete_behavior") == "APPEND_ONLY_UPDATE_DELETE_FORBIDDEN",
        "immutable auth audit table",
    )
    rate_limit = tables.get("atp_auth_source_rate_limit", {})
    add(
        "AUTH-SOURCE-RATE-LIMIT-PHYSICAL-MODEL",
        rate_limit.get("object_id") == "AUTH-OBJ-004"
        and rate_limit.get("primary_key") == ["source_key_hash", "operation_id", "window_started_at"]
        and rate_limit.get("data_owner") == "AuthenticationRateLimitService",
        "shared MySQL source-rate-limit owner and composite identity",
    )
    facts = derive_current_facts(root.parents[1])
    migrations = discover_migrations(root)
    add(
        "AUTH-MIGRATION-DISCOVERY",
        [item["name"] for item in migrations] == facts["migration"]["files"],
        f"head=V{facts['migration']['head']}; files={facts['migration']['files']}",
    )

    owner_registry = _yaml_load((root / "编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.yaml").read_text(encoding="utf-8"))
    owners = owner_registry.get("authentication_state_owners", [])
    semantic_ids = [owner["state_semantic_id"] for owner in owners]
    persistence_fields = [field for owner in owners for field in owner["persistence_fields"]]
    add(
        "AUTH-STATE-OWNER-UNIQUENESS",
        len(owners) == 8 and len(semantic_ids) == len(set(semantic_ids)) and len(persistence_fields) == len(set(persistence_fields)),
        f"owners={len(owners)}; fields={len(persistence_fields)}",
    )

    permission = _yaml_load((root / "编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml").read_text(encoding="utf-8"))
    maps = permission["role_permission_mappings"]
    super_admin_allowed = sum(
        item["role_id"] == "ROLE-SUPER-ADMIN" and item["decision"] == "ALLOWED" for item in maps
    )
    expected_rbac = facts["rbac"]
    add(
        "AUTH-RBAC-CLOSURE-UNCHANGED",
        len(permission["permission_catalog"]) == expected_rbac["permission_count"]
        and len(permission["role_templates"]) == expected_rbac["role_count"]
        and len(maps) == expected_rbac["mapping_count"]
        and super_admin_allowed == expected_rbac["permission_count"],
        f"derived={expected_rbac}; super_admin_allowed={super_admin_allowed}",
    )

    acceptance = json.loads((root / "编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json").read_text(encoding="utf-8"))
    p1_items = [
        item
        for item in acceptance["acceptance_closure"]
        if 1602 <= int(item["acceptance_id"].rsplit("-", 1)[1]) <= 1688
    ]
    governance = acceptance.get("p1_authentication_governance", {})
    declared_p1_items = governance.get("reused_items")
    allowed_statuses = {"SPECIFIED", "PASSED", "FAILED", "BLOCKED_BY_ENVIRONMENT"}
    allowed_evidence = {"EXPECTED_NOT_EXECUTED", "NOT_STARTED", "VERIFIED", "FAILED", "BLOCKED_BY_ENVIRONMENT"}
    evidence_coherent = all(
        item["evidence_status"] == "VERIFIED" if item["status"] == "PASSED" else item["evidence_status"] != "VERIFIED"
        for item in p1_items
    )
    add(
        "AUTH-ACCEPTANCE-HONEST-RUNTIME-STATUS",
        isinstance(declared_p1_items, int)
        and len(p1_items) == declared_p1_items
        and all(item["status"] in allowed_statuses for item in p1_items)
        and all(item["evidence_status"] in allowed_evidence for item in p1_items)
        and evidence_coherent
        and governance.get("revised_items") == declared_p1_items
        and governance.get("new_items") == 0,
        f"p1_items={len(p1_items)}; passed={sum(item['status'] == 'PASSED' for item in p1_items)}; revised={governance.get('revised_items')}",
    )

    add(
        "AUTH-CURRENT-AUTHORITY-READY",
        system_design.get("release_gate", {}).get("authority_readiness", {}).get("status") == "READY_FOR_P1_IMPLEMENTATION"
        and auth["metadata"]["pending_user_decisions"] == 0,
        "current living authority is ready for P1 implementation",
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
        "authority_model": AUTHORITY_MODEL,
        "authority_root": "docs/authority",
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
