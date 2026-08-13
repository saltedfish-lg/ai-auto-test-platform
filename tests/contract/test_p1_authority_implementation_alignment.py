from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "tools"))
from current_facts import derive_current_facts, discover_migrations
AUTHORITY = ROOT / "docs" / "authority"


def test_jwt_key_ring_contract_matches_api_settings() -> None:
    contract = yaml.safe_load(
        (AUTHORITY / "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    config = (ROOT / "services/api/src/platform_api/config.py").read_text(encoding="utf-8")
    security = (ROOT / "services/api/src/platform_api/security.py").read_text(encoding="utf-8")
    assert contract["access_token"]["key_ring_source"].startswith("ATP_JWT_KEY_RING_FILE")
    assert contract["access_token"]["key_ring_contract"]["minimum_overlap_seconds"] == 960
    assert 'validation_alias="ATP_JWT_KEY_RING_FILE"' in config
    assert "active_signing_kid" in security
    assert "verify_until" in security


def test_auth_hmac_ring_contract_matches_fail_closed_api_configuration() -> None:
    contract = yaml.safe_load(
        (AUTHORITY / "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    config = (ROOT / "services/api/src/platform_api/config.py").read_text(encoding="utf-8")
    hmac_keys = (ROOT / "services/api/src/platform_api/auth_hmac.py").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    key_ring = contract["auth_hmac_key_ring"]
    assert key_ring["format"] == "STRICT_JSON_RING"
    assert key_ring["minimum_rotation_overlap_seconds"] == 86400
    assert 'validation_alias="ATP_AUTH_HMAC_MASTER_KEY_FILE"' in config
    assert "AuthHmacKeyRing" in hmac_keys and "_MINIMUM_ROTATION_OVERLAP" in hmac_keys
    assert "ATP_AUTH_HMAC_MASTER_KEY_FILE=" in env_example
    assert "ATP_JWT_KEY_RING_FILE=" in env_example
    assert "ATP_JWT_PRIVATE_KEY_FILE=" not in env_example


def test_auth_security_audit_contract_matches_sqlalchemy_and_v6() -> None:
    schema = yaml.safe_load(
        (AUTHORITY / "编码权威事实/DATABASE_DDL/database-schema.yaml").read_text(encoding="utf-8")
    )
    tables = {item["table_name"]: item for item in schema["tables"]}
    audit = tables["atp_auth_security_audit"]
    models = (ROOT / "services/api/src/platform_api/models.py").read_text(encoding="utf-8")
    v6 = (AUTHORITY / "编码权威事实/DATABASE_DDL/V6__p1_auth_governance_closure.sql").read_text(
        encoding="utf-8"
    )
    assert audit["object_id"] == "AUTH-OBJ-003"
    assert audit["delete_behavior"] == "APPEND_ONLY_UPDATE_DELETE_FORBIDDEN"
    assert '__tablename__ = "atp_auth_security_audit"' in models
    assert "trg_atp_auth_security_audit_no_update" in v6
    assert "trg_atp_auth_security_audit_no_delete" in v6


def test_idempotency_json_none_is_persisted_as_sql_null() -> None:
    models = (ROOT / "services/api/src/platform_api/models.py").read_text(encoding="utf-8")
    assert "mapped_column(JSON(none_as_null=True))" in models


def test_p1_migration_and_state_owner_alignment() -> None:
    schema = yaml.safe_load(
        (AUTHORITY / "编码权威事实/DATABASE_DDL/database-schema.yaml").read_text(encoding="utf-8")
    )
    owners = yaml.safe_load(
        (AUTHORITY / "编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.yaml").read_text(
            encoding="utf-8"
        )
    )
    gate = (ROOT / "tools/gates/auth_mysql_gate.py").read_text(encoding="utf-8")
    facts = derive_current_facts(ROOT)
    assert [item["name"] for item in discover_migrations(AUTHORITY)] == facts["migration"]["files"]
    assert len(schema["tables"]) == facts["database"]["table_count"]
    assert len(schema["table_classification"]["technical_table_names"]) == facts["database"]["technical_table_count"]
    auth_owners = owners["authentication_state_owners"]
    assert len(auth_owners) == 8
    assert any(item["semantic"] == "AUTH_SECURITY_AUDIT_IMMUTABILITY" for item in auth_owners)
    assert any(item["semantic"] == "SOURCE_RATE_LIMIT_WINDOW" for item in auth_owners)
    assert '"V7__p1_remaining_authentication_closure.sql"' in gate
    assert "docs/baseline" not in gate


def test_auth_implementation_status_matches_existing_implementation() -> None:
    contract = yaml.safe_load(
        (AUTHORITY / "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    design = yaml.safe_load((AUTHORITY / "编码权威事实/SYSTEM_DESIGN.yaml").read_text(encoding="utf-8"))
    assert contract["metadata"]["implementation_status_source"] == "SYSTEM_DESIGN.runtime_gate_contract.implementation_status"
    assert design["runtime_gate_contract"]["implementation_status"] == "IMPLEMENTED_PENDING_RUNTIME_VALIDATION"
    assert contract["metadata"]["deferred_product_decisions"] == 0
    for relative in (
        "services/api/src/platform_api/auth_service.py",
        "services/api/src/platform_api/auth_router.py",
        "services/api/src/platform_api/auth_hmac.py",
        "services/api/src/platform_api/rate_limit.py",
        "services/api/src/platform_api/user_admin_service.py",
        "services/api/src/platform_api/security.py",
        "services/api/src/platform_api/models.py",
        "apps/web/src/views/LoginView.vue",
        "apps/web/src/views/ChangePasswordView.vue",
        "apps/web/src/stores/session.ts",
    ):
        assert (ROOT / relative).is_file(), relative


def test_confirmed_p1_governance_items_have_no_placeholders_and_are_implemented() -> None:
    contract = yaml.safe_load(
        (AUTHORITY / "编码权威事实/AUTHENTICATION_CONTRACT/authentication-contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        "GOV-P1-002": "SYSTEM_GENERATED_ONE_TIME_TEMP_CREDENTIAL",
        "GOV-P1-003": "SOURCE_RATE_LIMIT_ENABLED_MYSQL84",
        "GOV-P1-005": "PASSWORD_CHANGE_REVOKES_REFRESH_SESSIONS_AND_REAUTHENTICATES",
    }
    assert contract["product_decision_placeholders"] == []
    decisions = {item["decision_id"]: item for item in contract["confirmed_product_decisions"]}
    assert set(decisions) == set(expected)
    for decision_id, selected_option in expected.items():
        assert decisions[decision_id]["selected_option"] == selected_option
        assert decisions[decision_id]["status"] == "CONFIRMED_IN_LIVING_AUTHORITY"

    traceability = (ROOT / "docs/implementation/p1-auth-rbac-traceability.md").read_text(
        encoding="utf-8"
    )
    for decision_id, selected_option in expected.items():
        assert decision_id in traceability
        assert selected_option in traceability
    assert "GOV_P1_002_003_005 = IMPLEMENTED_PENDING_RUNTIME_VALIDATION" in traceability

    hmac_ring = contract["auth_hmac_key_ring"]
    assert hmac_ring["configuration"] == "ATP_AUTH_HMAC_MASTER_KEY_FILE"
    assert hmac_ring["format"] == "STRICT_JSON_RING"
    service = (ROOT / "services/api/src/platform_api/auth_service.py").read_text(encoding="utf-8")
    router = (ROOT / "services/api/src/platform_api/auth_router.py").read_text(encoding="utf-8")
    generated = (ROOT / "apps/web/src/generated/client.ts").read_text(encoding="utf-8")
    assert "contract_version=2" in service or "contract_version = 2" in service
    assert 'alias="Idempotency-Key"' in router
    assert "change_current_user_password" in generated and "Promise<void>" in generated
