from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/gates/web_ui_business_semantics_gate.py"
spec = importlib.util.spec_from_file_location("web_ui_business_semantics_gate", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_current_web_has_no_editable_relation_ids_or_raw_status_text() -> None:
    assert module.collect_violations() == []
