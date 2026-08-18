from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'validator'


import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/package_delivery.py"


def _module():
    spec = importlib.util.spec_from_file_location("_delivery_packaging", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_delivery_archive_excludes_runtime_cache_and_build_outputs(tmp_path: Path) -> None:
    repo = tmp_path / "项目"
    (repo / "src").mkdir(parents=True)
    (repo / "src/main.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / ".env.example").write_text("TOKEN_FILE=/path/to/example\n", encoding="utf-8")
    (repo / ".env.local").write_text("REAL_SECRET=must-not-ship\n", encoding="utf-8")
    for rel in (
        "src/__pycache__/main.cpython-312.pyc",
        "apps/web/dist/index.html",
        "test-results/failure.png",
        ".runtime/secret.json",
        "node_modules/pkg/index.js",
    ):
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("noise", encoding="utf-8")
    out = tmp_path / "delivery.zip"
    result = _module().create_archive(repo, out)
    assert result["status"] == "PASS"
    with zipfile.ZipFile(out) as archive:
        names = archive.namelist()
        assert "项目/src/main.py" in names
        assert "项目/.env.example" in names
        assert "项目/.env.local" not in names
        assert not any("__pycache__" in name or "/dist/" in name or "/test-results/" in name or "/.runtime/" in name for name in names)
        unicode_info = next(info for info in archive.infolist() if info.filename == "项目/src/main.py")
        assert unicode_info.flag_bits & 0x800


def test_delivery_verify_reports_unicode_filename_metadata_and_crc(tmp_path: Path) -> None:
    repo = tmp_path / '含中文仓库'
    authority = repo / 'specs/产品规则/规则.yaml'
    authority.parent.mkdir(parents=True)
    authority.write_text('rule: existing\n', encoding='utf-8')
    out = tmp_path / 'unicode-delivery.zip'
    module = _module()
    created = module.create_archive(repo, out)
    verified = module.verify_archive(out)
    assert created['status'] == 'PASS'
    assert verified['status'] == 'PASS'
    assert verified['unicode_entries_without_utf8_flag'] == []
    assert verified['crc_error'] is None
    assert verified['forbidden_entries'] == []
    with zipfile.ZipFile(out) as archive:
        info = next(i for i in archive.infolist() if i.filename.endswith('specs/产品规则/规则.yaml'))
        assert info.flag_bits & 0x800
        archive.extractall(tmp_path / 'python-extract')
    assert (tmp_path / 'python-extract/含中文仓库/specs/产品规则/规则.yaml').is_file()
