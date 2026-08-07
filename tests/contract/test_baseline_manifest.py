from pathlib import Path

from tools.verify_baseline import verify

ROOT = Path(__file__).resolve().parents[2]


def test_r4_1_manifest_and_current_navigation_are_consistent() -> None:
    report = verify()

    assert report["status"] == "PASS"
    assert report["manifest_entries"] == 718
    assert (ROOT / "docs" / "baseline" / "CURRENT").read_text(encoding="utf-8").strip() == "R4.1"


def test_top_level_responsibility_directories_are_not_python_packages() -> None:
    for directory in ("apps", "services", "workers", "runner", "packages", "tests", "tools"):
        assert not (ROOT / directory / "__init__.py").exists()
