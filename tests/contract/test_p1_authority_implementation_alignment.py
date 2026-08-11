from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "docs" / "authority"


def test_jwt_key_ring_contract_matches_api_settings() -> None:
    contract = yaml.safe_load(
        (AUTHORITY / "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml").read_text(encoding="utf-8")
    )
    config = (ROOT / "services/api/src/platform_api/config.py").read_text(encoding="utf-8")
    security = (ROOT / "services/api/src/platform_api/security.py").read_text(encoding="utf-8")
    assert contract["access_token"]["key_ring_source"].startswith("ATP_JWT_KEY_RING_FILE")
    assert contract["access_token"]["key_ring_contract"]["minimum_overlap_seconds"] == 960
    assert 'validation_alias="ATP_JWT_KEY_RING_FILE"' in config
    assert "active_signing_kid" in security
    assert "verify_until" in security


def test_auth_security_audit_contract_matches_sqlalchemy_and_v6() -> None:
    schema = yaml.safe_load(
        (AUTHORITY / "编码权威事实/DATABASE_DDL/database-schema.yaml").read_text(encoding="utf-8")
    )
    tables = {item["table_name"]: item for item in schema["tables"]}
    audit = tables["atp_auth_security_audit"]
    models = (ROOT / "services/api/src/platform_api/models.py").read_text(encoding="utf-8")
    v6 = (AUTHORITY / "编码权威事实/DATABASE_DDL/V6__p1_auth_governance_closure.sql").read_text(encoding="utf-8")
    assert audit["object_id"] == "AUTH-OBJ-003"
    assert audit["delete_behavior"] == "APPEND_ONLY_UPDATE_DELETE_FORBIDDEN"
    assert '__tablename__ = "atp_auth_security_audit"' in models
    assert "trg_atp_auth_security_audit_no_update" in v6
    assert "trg_atp_auth_security_audit_no_delete" in v6


def test_p1_migration_and_state_owner_alignment() -> None:
    schema = yaml.safe_load(
        (AUTHORITY / "编码权威事实/DATABASE_DDL/database-schema.yaml").read_text(encoding="utf-8")
    )
    owners = yaml.safe_load(
        (AUTHORITY / "编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.yaml").read_text(encoding="utf-8")
    )
    gate = (ROOT / "tools/p1_auth_mysql_gate.py").read_text(encoding="utf-8")
    assert schema["migration_files"][-1] == "V6__p1_auth_governance_closure.sql"
    assert schema["technical_table_count"] == 6
    assert len(schema["tables"]) == 85
    auth_owners = owners["authentication_state_owners"]
    assert len(auth_owners) == 7
    assert any(item["semantic"] == "AUTH_SECURITY_AUDIT_IMMUTABILITY" for item in auth_owners)
    assert '"V6__p1_auth_governance_closure.sql"' in gate
    assert "docs/baseline" not in gate


def test_auth_implementation_status_matches_existing_implementation() -> None:
    contract = yaml.safe_load(
        (AUTHORITY / "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml").read_text(encoding="utf-8")
    )
    assert contract["metadata"]["implementation_status"] == "IMPLEMENTED_PENDING_RUNTIME_VALIDATION"
    assert contract["metadata"]["deferred_product_decisions"] == 3
    for relative in (
        "services/api/src/platform_api/auth_service.py",
        "services/api/src/platform_api/auth_router.py",
        "services/api/src/platform_api/security.py",
        "services/api/src/platform_api/models.py",
        "apps/web/src/views/LoginView.vue",
        "apps/web/src/stores/session.ts",
    ):
        assert (ROOT / relative).is_file(), relative


def test_unresolved_p1_governance_items_have_executable_placeholders_and_remain_unimplemented() -> None:
    contract = yaml.safe_load(
        (AUTHORITY / "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml").read_text(encoding="utf-8")
    )
    expected = {
        "GOV-P1-002": "TEMPORARY_CREDENTIAL_DELIVERY_AND_WRITE_SEMANTICS",
        "GOV-P1-003": "LOGIN_REFRESH_SOURCE_RATE_LIMIT_POLICY",
        "GOV-P1-005": "CHANGE_PASSWORD_LOST_RESPONSE_IDEMPOTENT_REPLAY",
    }
    placeholders = {item["decision_id"]: item for item in contract["product_decision_placeholders"]}
    assert set(placeholders) == set(expected)
    for decision_id, name in expected.items():
        item = placeholders[decision_id]
        assert item["name"] == name
        assert item["status"] == "BLOCKED_BY_PRODUCT_DECISION"
        assert item["decision_owner"] == "USER_PRODUCT_SOVEREIGNTY"
        assert item["blocks_current_approved_scope"] is False
        assert item["current_fact"]
        assert item["issue"]
        assert item["missing_facts"]
        assert item["blocked_scope"]
        assert "不得" in item["implementation_rule"]

    traceability = (ROOT / "docs/implementation/p1-auth-rbac-traceability.md").read_text(encoding="utf-8")
    for decision_id, name in expected.items():
        assert decision_id in traceability
        assert name in traceability
    assert "DEFERRED_BLOCKED_BY_PRODUCT_DECISION" in traceability

    change_password = placeholders["GOV-P1-005"]
    assert "Idempotency-Key" in change_password["current_fact"]
    assert "409" in change_password["current_fact"]
    service = (ROOT / "services/api/src/platform_api/auth_service.py").read_text(encoding="utf-8")
    router = (ROOT / "services/api/src/platform_api/auth_router.py").read_text(encoding="utf-8")
    assert "Idempotency key conflict" in service
    assert 'alias="Idempotency-Key"' in router
