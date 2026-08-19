from pathlib import Path

from tools.governance.code_quality_gate import evaluate


def _profile(root: Path) -> None:
    (root / '.governance').mkdir(exist_ok=True)
    (root / '.governance/technology.yaml').write_text('''schema_version: 1
technology:
  languages:
    python:
      paths: ["**/*.py"]
      adapter: python
  adapters:
    python:
      checks: [no_unresolved_todo, python_syntax]
''', encoding='utf-8')


def test_clean_small_file_passes(tmp_path: Path):
    _profile(tmp_path)
    p = tmp_path / 'x.py'; p.write_text('def ok():\n    return 1\n', encoding='utf-8')
    assert evaluate(tmp_path, ['x.py'])['status'] == 'PASS'


def test_todo_in_current_file_fails(tmp_path: Path):
    _profile(tmp_path)
    unresolved_marker = '# TO' + 'DO fix\ndef x():\n    pass\n'
    p = tmp_path / 'x.py'; p.write_text(unresolved_marker, encoding='utf-8')
    out = evaluate(tmp_path, ['x.py'])
    assert out['status'] == 'FAIL'
    assert out['findings'][0]['path'] == 'x.py'
