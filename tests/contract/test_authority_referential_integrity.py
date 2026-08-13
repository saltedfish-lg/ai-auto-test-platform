from __future__ import annotations

import json
from pathlib import Path

import yaml

from tools.authority_referential_integrity import check

ROOT = Path(__file__).resolve().parents[2]


def test_current_authority_has_no_dangling_rule_lifecycle_acceptance_or_data_asset_refs() -> None:
    counts, dangling = check(ROOT / "docs" / "authority")
    assert dangling == []
    assert counts["RULE"] > 0
    assert counts["LIFECYCLE"] > 0
    assert counts["DATA_ASSET"] > 0
    assert counts["ACCEPTANCE"] > 0


def test_referential_integrity_gate_rejects_structured_dangling_reference(tmp_path: Path) -> None:
    authority = tmp_path / "docs" / "authority"
    core = authority / "核心对象、业务规则与生命周期"
    data = authority / "数据安全、制品生命周期与验收基线"
    acceptance = authority / "编码权威事实" / "ACCEPTANCE_CLOSURE"
    core.mkdir(parents=True)
    data.mkdir(parents=True)
    acceptance.mkdir(parents=True)
    (core / "核心对象、业务规则与生命周期.yaml").write_text(
        yaml.safe_dump(
            {
                "business_rules": [{"rule_id": "BR-TEST-0001"}],
                "traceability_index": [{"target_type": "RULE", "target_id": "BR-TEST-MISSING"}],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (data / "数据安全、制品生命周期与验收基线.yaml").write_text(
        yaml.safe_dump({"data_assets": [{"data_asset_id": "DI-0001"}]}, allow_unicode=True),
        encoding="utf-8",
    )
    (acceptance / "acceptance-closure.json").write_text(
        json.dumps({"acceptance_closure": []}, ensure_ascii=False), encoding="utf-8"
    )
    _, dangling = check(authority)
    assert any(item["id"] == "BR-TEST-MISSING" and item["kind"] == "RULE" for item in dangling)


def test_obj_085_acceptance_retirement_is_complete_and_historical_count_is_provenance_only() -> None:
    payload = json.loads(
        (ROOT / "docs/authority/编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json").read_text(
            encoding="utf-8"
        )
    )
    provenance = payload["metadata"]["obj_085_retirement_provenance"]
    retired = set(provenance["retired_acceptance_ids"])
    active = {item["acceptance_id"] for item in payload["acceptance_closure"]}
    assert provenance["historical_pre_retirement_acceptance_count"] == 1691
    assert provenance["retired_acceptance_count"] == 14
    assert retired.isdisjoint(active)
    assert len(payload["acceptance_closure"]) == 1691 - 14
    assert provenance["current_count_source"] == "tools/current_facts.py#acceptance.count"


def test_referential_integrity_covers_all_current_data_asset_id_families(tmp_path: Path) -> None:
    authority = tmp_path / "docs" / "authority"
    core = authority / "核心对象、业务规则与生命周期"
    data = authority / "数据安全、制品生命周期与验收基线"
    acceptance = authority / "编码权威事实" / "ACCEPTANCE_CLOSURE"
    core.mkdir(parents=True)
    data.mkdir(parents=True)
    acceptance.mkdir(parents=True)
    (core / "核心对象、业务规则与生命周期.yaml").write_text(
        yaml.safe_dump(
            {
                "business_rules": [{"rule_id": "BR-TEST-0001"}],
                "references": [
                    {"target_id": "DA-EXT-999"},
                    {"data_item_id": "DI-R4-999-PK"},
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (data / "数据安全、制品生命周期与验收基线.yaml").write_text(
        yaml.safe_dump(
            {
                "data_assets": [
                    {"data_asset_id": "DI-0001"},
                    {"data_asset_id": "DA-EXT-001"},
                    {"data_asset_id": "DI-R4-084-PK"},
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (acceptance / "acceptance-closure.json").write_text(
        json.dumps({"acceptance_closure": []}, ensure_ascii=False), encoding="utf-8"
    )
    _, dangling = check(authority)
    ids = {(item["kind"], item["id"]) for item in dangling}
    assert ("DATA_ASSET", "DA-EXT-999") in ids
    assert ("DATA_ASSET", "DI-R4-999-PK") in ids


def test_referential_integrity_rejects_dangling_lifecycle_reference(tmp_path: Path) -> None:
    authority = tmp_path / "docs" / "authority"
    core = authority / "核心对象、业务规则与生命周期"
    data = authority / "数据安全、制品生命周期与验收基线"
    acceptance = authority / "编码权威事实" / "ACCEPTANCE_CLOSURE"
    core.mkdir(parents=True)
    data.mkdir(parents=True)
    acceptance.mkdir(parents=True)
    (core / "核心对象、业务规则与生命周期.yaml").write_text(
        yaml.safe_dump(
            {
                "business_rules": [{"rule_id": "BR-TEST-0001"}],
                "lifecycles": [{"lifecycle_id": "LC-001"}],
                "traceability_index": [{"target_type": "LIFECYCLE", "target_id": "LC-999"}],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (data / "数据安全、制品生命周期与验收基线.yaml").write_text(
        yaml.safe_dump({"data_assets": [{"data_asset_id": "DI-0001"}]}, allow_unicode=True),
        encoding="utf-8",
    )
    (acceptance / "acceptance-closure.json").write_text(
        json.dumps({"acceptance_closure": []}, ensure_ascii=False), encoding="utf-8"
    )
    _, dangling = check(authority)
    assert any(item["id"] == "LC-999" and item["kind"] == "LIFECYCLE" for item in dangling)
