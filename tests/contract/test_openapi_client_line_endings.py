import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest

from tools.openapi_client import GENERATED_FILES, _normalize_generated_files_to_lf


@pytest.fixture
def runtime_path() -> Iterator[Path]:
    runtime_root = (Path.cwd() / "tests" / "contract" / ".runtime").resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    directory = runtime_root / f"lf-normalization-{secrets.token_hex(8)}"
    directory.mkdir(exist_ok=False)
    try:
        yield directory
    finally:
        for child in directory.iterdir():
            child.unlink()
        directory.rmdir()


def test_normalize_generated_files_to_lf(runtime_path: Path) -> None:
    samples = {
        "types.ts": b"type A = string;\r\n\r\ntype B = number;\r\n",
        "client.ts": b"export const x = 1;\r\nexport const y = 2;\r",
        "generation-report.json": b'{\r\n  "types": 464\r\n}\r\n',
    }
    for name, content in samples.items():
        (runtime_path / name).write_bytes(content)

    _normalize_generated_files_to_lf(runtime_path)

    for name in GENERATED_FILES:
        content = (runtime_path / name).read_bytes()
        assert b"\r" not in content
        assert b"\n" in content
