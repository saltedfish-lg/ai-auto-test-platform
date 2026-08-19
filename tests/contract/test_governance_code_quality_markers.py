from __future__ import annotations

GOVERNANCE_TEST_GROUP = 'runtime-resilience'

from pathlib import Path

import pytest

from tools.governance.code_quality_gate import evaluate


def _profile(root: Path) -> None:
    profile = root / '.governance'
    profile.mkdir(exist_ok=True)
    (profile / 'technology.yaml').write_text(
        '''schema_version: 1
technology:
  languages:
    python:
      paths: ["**/*.py"]
      adapter: python
  adapters:
    python:
      checks: [no_unresolved_todo, python_syntax]
''',
        encoding='utf-8',
    )


@pytest.mark.parametrize('identifier', ['workspace.todo', 'domain.todo.route'])
def test_dotted_todo_product_identifier_is_not_a_finding(
    tmp_path: Path,
    identifier: str,
) -> None:
    _profile(tmp_path)
    path = tmp_path / 'x.py'
    path.write_text(f'route_name = {identifier!r}\n', encoding='utf-8')
    assert evaluate(tmp_path, ['x.py'])['status'] == 'PASS'


@pytest.mark.parametrize(
    'marker',
    [
        '# TO' + 'DO implement\n',
        '// TO' + 'DO implement\n',
        '-- TO' + 'DO implement\n',
        '- TO' + 'DO implement\n',
        'TO' + 'DO: implement\n',
        'FIX' + 'ME: repair\n',
    ],
)
def test_true_todo_and_fixme_markers_are_findings(
    tmp_path: Path,
    marker: str,
) -> None:
    _profile(tmp_path)
    path = tmp_path / 'x.py'
    path.write_text(marker, encoding='utf-8')
    result = evaluate(tmp_path, ['x.py'])
    assert result['status'] == 'FAIL'
    assert result['findings'][0]['path'] == 'x.py'
