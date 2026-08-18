
GOVERNANCE_TEST_GROUP = 'validator'

import tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
EXPECTED={
 "default_coder":"workspace-write",
 "architecture_reviewer":"read-only",
 "product_sovereignty_reviewer":"read-only",
 "code_quality_reviewer":"read-only",
}
def test_project_custom_agents_are_four_and_permission_scoped():
 loaded={}
 for path in sorted((ROOT/".codex/agents").glob("*.toml")):
  d=tomllib.loads(path.read_text(encoding="utf-8")); assert d["name"] and d["description"] and d["developer_instructions"]; loaded[d["name"]]=d["sandbox_mode"]
 assert loaded==EXPECTED
