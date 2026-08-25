from __future__ import annotations

GOVERNANCE_TEST_GROUP = "routing"

from pathlib import Path

import pytest
import yaml

from tools.gates import model_configuration_browser_gate
from tools.governance import required_gate_runner
from tools.governance.impact_scan import scan
from tools.governance.required_gate_runner import command_for_gate
from tools.governance.task_context import (
    cleanup_task,
    save_context,
    save_workspace_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
TASK_ID = "MODEL_CONFIGURATION_BROWSER_ROUTE_PROBE"


def test_model_configuration_browser_change_routes_only_to_its_runtime() -> None:
    try:
        context = scan(
            ROOT,
            TASK_ID,
            "修复 Model Configuration Browser Runtime Gate",
            ["apps/web/e2e/model-configuration.spec.ts"],
        )
        required = set(context["required_gates"])
        assert "MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE" in required
        assert "REAL_ACCEPTANCE_GATE" in required
        assert "playwright_test" in required
        expected = ["python", "tools/gates/model_configuration_browser_gate.py"]
        assert command_for_gate(ROOT, "MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE", context) == expected
        assert command_for_gate(ROOT, "REAL_ACCEPTANCE_GATE", context) == expected
        assert command_for_gate(ROOT, "playwright_test", context) == expected
    finally:
        cleanup_task(ROOT, TASK_ID)


@pytest.mark.parametrize(
    "affected_path",
    [
        "apps/web/e2e/model-configuration.spec.ts",
        "apps/web/src/views/ModelConfigurationsView.vue",
        "apps/web/src/stores/modelConfigurations.ts",
        "services/api/src/platform_api/model_configuration_service.py",
        "services/api/src/platform_api/model_configuration_router.py",
        "services/api/src/platform_api/model_configuration_schemas.py",
        "services/api/tests/test_model_configuration.py",
        "docs/authority/编码权威事实/DATABASE_DDL/V10__ai_model_configuration_foundation.sql",
        "tools/gates/model_configuration_browser_gate.py",
    ],
)
def test_model_capability_paths_require_and_route_to_dedicated_browser_gate(
    affected_path: str,
) -> None:
    task_id = f"MODEL_CONFIGURATION_ROUTE_{Path(affected_path).stem.upper()}"
    try:
        context = scan(ROOT, task_id, "验证模型配置专用验收路由", [affected_path])
        required = set(context["required_gates"])
        assert "MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE" in required
        assert "REAL_ACCEPTANCE_GATE" in required
        expected = ["python", "tools/gates/model_configuration_browser_gate.py"]
        assert command_for_gate(ROOT, "MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE", context) == expected
        assert command_for_gate(ROOT, "REAL_ACCEPTANCE_GATE", context) == expected
    finally:
        cleanup_task(ROOT, task_id)


def test_ambiguous_acceptance_routes_are_reported_structurally(tmp_path: Path) -> None:
    governance = tmp_path / ".governance"
    governance.mkdir()
    (governance / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "runtime": {
                    "task_acceptance_alias_gates": ["REAL_ACCEPTANCE_GATE"],
                    "task_acceptance_routes": [
                        {
                            "route_id": "auth",
                            "when_any_affected_paths": ["apps/web/e2e/auth.spec.ts"],
                            "command": ["python", "auth_gate.py"],
                        },
                        {
                            "route_id": "model",
                            "when_any_affected_paths": [
                                "apps/web/e2e/model-configuration.spec.ts"
                            ],
                            "command": ["python", "model_gate.py"],
                        },
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (governance / "gates.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "gates": {
                    "REAL_ACCEPTANCE_GATE": {
                        "command": ["python", "fallback.py"]
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    affected = [
        "apps/web/e2e/auth.spec.ts",
        "apps/web/e2e/model-configuration.spec.ts",
    ]
    for relative in affected:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("probe\n", encoding="utf-8")
    save_workspace_snapshot(tmp_path, "AMBIGUOUS_ACCEPTANCE")
    save_context(
        tmp_path,
        "AMBIGUOUS_ACCEPTANCE",
        {
            "task_id": "AMBIGUOUS_ACCEPTANCE",
            "required_gates": ["REAL_ACCEPTANCE_GATE"],
            "affected_files": affected,
            "relevant_tests": [],
            "final_reconciliation_status": "PASS",
            "actual_changed_files": [],
            "product_decision_status": "NOT_REQUIRED",
        },
    )
    report = required_gate_runner.run_required(tmp_path, "AMBIGUOUS_ACCEPTANCE")
    assert report["status"] == "BLOCKED"
    assert report["results"][0]["status"] == "BLOCKED"
    assert report["results"][0]["reason"] == "INVALID_GATE_CONFIGURATION"


def test_cleanup_steps_continue_and_report_only_safe_metadata() -> None:
    calls: list[str] = []
    errors: list[dict[str, str]] = []

    def fail() -> None:
        calls.append("failed")
        raise RuntimeError("secret-value-must-not-be-recorded")

    actions = [
        ("first", lambda: calls.append("first")),
        ("failing", fail),
        ("last", lambda: calls.append("last")),
    ]
    for resource, action in actions:
        model_configuration_browser_gate._cleanup_step(resource, action, errors)

    assert calls == ["first", "failed", "last"]
    assert errors == [{"resource": "failing", "error_type": "RuntimeError"}]
    assert "secret-value" not in str(errors)


def test_runtime_environment_removes_unrelated_e2e_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        model_configuration_browser_gate,
        "project_environment",
        lambda root: {
            "SAFE_SETTING": "kept",
            "ATP_AUTH_E2E_PASSWORD": "auth-secret",
            "ATP_PROJECT_E2E_PASSWORD": "project-secret",
            "ATP_MODEL_E2E_SECRET": "stale-model-secret",
            "PLAYWRIGHT_BASE_URL": "stale-url",
            "PLAYWRIGHT_CHROMIUM_EXECUTABLE": "approved-browser-override",
        },
    )
    assert model_configuration_browser_gate._isolated_runtime_environment() == {
        "SAFE_SETTING": "kept",
        "PLAYWRIGHT_CHROMIUM_EXECUTABLE": "approved-browser-override",
    }


def test_formal_catalog_and_profile_share_the_model_browser_capability() -> None:
    design = yaml.safe_load(
        (ROOT / "docs/authority/编码权威事实/SYSTEM_DESIGN.yaml").read_text(
            encoding="utf-8"
        )
    )
    gates = {
        item["gate_id"]: item for item in design["runtime_gate_catalog"]["gates"]
    }
    model_gate = gates["MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE"]
    assert model_gate == {
        "gate_id": "MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE",
        "scope": "AI_MODEL_CONFIGURATION",
        "command": "python tools/gates/model_configuration_browser_gate.py",
        "required_when": ["MODEL_CONFIGURATION_BROWSER_RUNTIME_CHANGED"],
    }

    profile = yaml.safe_load((ROOT / ".governance/gates.yaml").read_text(encoding="utf-8"))
    identity = profile["gates"]["MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE"][
        "execution_identity"
    ]
    assert identity == {"capability": "model_configuration_browser_acceptance"}


def test_model_browser_runner_is_isolated_secret_safe_and_scope_specific() -> None:
    runner = (ROOT / "tools/gates/model_configuration_browser_gate.py").read_text(
        encoding="utf-8"
    )
    assert 'GATE_ID = "MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE"' in runner
    assert '"PLAYWRIGHT_TEST_FILE": "model-configuration.spec.ts"' in runner
    assert '"ATP_PROJECT_E2E_CODE":' not in runner
    assert '"ATP_PROJECT_E2E_USERNAME":' not in runner
    assert "_new_database_name(\"model\")" in runner
    assert "_drop_isolated_database(database)" in runner
    assert 'startswith("model-configuration-browser-")' in runner
    assert '"runtime_secrets_removed": runtime_removed' in runner
    assert "browser_exit: int | None = None" in runner
    assert '"database": "PASS" if database_ready else "NOT_RUN"' in runner
    assert '"errors": cleanup_errors' in runner
    assert "ThreadingHTTPServer" in runner
    assert '"provider_secret":' not in runner

    spec = (ROOT / "apps/web/e2e/model-configuration.spec.ts").read_text(
        encoding="utf-8"
    )
    assert 'test("SUPER_ADMIN model configuration self-approval"' in spec
    assert "ATP_MODEL_E2E_SUPER_ADMIN_USERNAME" in spec
    assert "ATP_MODEL_E2E_SUPER_CONFIG_CODE" in spec
    assert "getByText(providerSecret" not in spec
    assert 'provider secret must never be rendered' in spec
    assert "expect(consoleErrors).toEqual" not in spec
    assert "expect(pageErrors).toEqual" not in spec
    assert 'consoleErrors.length, "browser console must have no unexpected errors"' in spec
    assert 'pageErrors.length, "browser page must have no runtime errors"' in spec
