from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/gates/auth_browser_gate.py"


def test_browser_gate_uses_current_project_playwright_revision_without_unsafe_fallback() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "chromium.executablePath()" in source
    assert "CURRENT_PLAYWRIGHT_BROWSER_NOT_INSTALLED" in source
    assert 'glob("ms-playwright/chromium-*' not in source
    assert "--no-sandbox" not in source
    assert 'browser_resolution = _validate_playwright_browser' in source
    assert "runtime_result_base" in source
    assert 'gate_source=Path(__file__)' in source
    assert "socket.create_connection" in source
    wait_for_vite = source.split("def _wait_for_vite", 1)[1].split("def _create_user", 1)[0]
    assert "_wait_for_port(port, process, timeout)" in wait_for_vite
    assert "read_text" not in wait_for_vite
