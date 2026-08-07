from pathlib import Path

from tools.openapi_client import GENERATED_FILES, _normalize_generated_files_to_lf


def test_normalize_generated_files_to_lf(tmp_path: Path) -> None:
    samples = {
        "types.ts": b"type A = string;\r\n\r\ntype B = number;\r\n",
        "client.ts": b"export const x = 1;\r\nexport const y = 2;\r",
        "generation-report.json": b'{\r\n  "types": 464\r\n}\r\n',
    }
    for name, content in samples.items():
        (tmp_path / name).write_bytes(content)

    _normalize_generated_files_to_lf(tmp_path)

    for name in GENERATED_FILES:
        content = (tmp_path / name).read_bytes()
        assert b"\r" not in content
        assert b"\n" in content
