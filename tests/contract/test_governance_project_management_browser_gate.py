from __future__ import annotations

from tools.governance import required_gate_runner
from tools.governance.impact_scan import scan
from tools.governance.task_context import cleanup_task
from tests.contract.governance_test_support import ROOT


def _route_for(path: str, *conditions: str) -> str | None:
    route = required_gate_runner._acceptance_route(
        ROOT,
        {
            "affected_files": [path],
            "formal_gate_conditions": list(conditions),
            "domains": [],
        },
    )
    return None if route is None else str(route["route_id"])


def test_project_management_route_covers_environment_terminal_backend_frontend_and_ddl() -> None:
    assert _route_for("apps/web/src/views/EnvironmentsView.vue") == "project_management_browser_acceptance"
    assert _route_for("apps/web/src/views/BusinessTerminalsView.vue") == "project_management_browser_acceptance"
    assert _route_for("services/api/src/platform_api/environment_service.py") == "project_management_browser_acceptance"
    assert _route_for("services/api/src/platform_api/business_terminal_router.py") == "project_management_browser_acceptance"
    assert _route_for("services/api/src/platform_api/automation_asset_service.py") == "project_management_browser_acceptance"
    assert _route_for("docs/authority/编码权威事实/DATABASE_DDL/V12__environment_management_foundation.sql", "MIGRATION_OR_DATABASE_SCHEMA_CHANGED") == "project_management_browser_acceptance"
    assert _route_for("docs/authority/编码权威事实/DATABASE_DDL/V13__business_terminal_foundation.sql", "MIGRATION_OR_DATABASE_SCHEMA_CHANGED") == "project_management_browser_acceptance"


def test_project_route_does_not_capture_model_configuration_migration() -> None:
    assert _route_for(
        "docs/authority/编码权威事实/DATABASE_DDL/V10__ai_model_configuration_foundation.sql",
        "MODEL_CONFIGURATION_BROWSER_RUNTIME_CHANGED",
    ) == "model_configuration_browser_acceptance"


def test_canonical_project_ownership_wins_over_incidental_model_impact() -> None:
    task_id = "MULTI_ROUTE_PROJECT_OWNERSHIP_PROBE"
    try:
        context = scan(
            ROOT,
            task_id,
            "Runner Project acceptance closure with historical model impact",
            [
                "apps/web/src/stores/modelConfigurations.ts",
                "apps/web/e2e/project-management.spec.ts",
                "tools/gates/project_acceptance_runtime.py",
            ],
        )
        route = required_gate_runner._acceptance_route(ROOT, context)
        assert route is not None
        assert route["route_id"] == "project_management_browser_acceptance"
        required = set(context["required_gates"])
        assert "MODEL_CONFIGURATION_BROWSER_RUNTIME_GATE" not in required
        assert "REAL_ACCEPTANCE_GATE" in required
        assert "playwright_test" in required
        expected = ["python", "tools/gates/project_acceptance_runtime.py"]
        assert required_gate_runner.command_for_gate(
            ROOT, "REAL_ACCEPTANCE_GATE", context
        ) == expected
        assert required_gate_runner.command_for_gate(ROOT, "playwright_test", context) == expected
    finally:
        cleanup_task(ROOT, task_id)
