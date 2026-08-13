import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / ".agents/skills/ai-auto-test-platform-code-quality/scripts/comment_quality_gate.py"
SNAPSHOT = ROOT / ".agents/skills/ai-auto-test-platform-context-efficiency/scripts/workspace_snapshot.py"
CHECKPOINT = ROOT / ".agents/skills/ai-auto-test-platform-feature-orchestrator/scripts/task_checkpoint.py"


def _gate(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(GATE), "--root", str(repo), *args], text=True, capture_output=True, check=False)


def _snapshot(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SNAPSHOT), *args, "--root", str(repo)], text=True, capture_output=True, check=False)


def _checkpoint(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CHECKPOINT), *args, "--root", str(repo)], text=True, capture_output=True, check=False)


def _write_auth_file(repo: Path, *, reason: bool = False) -> Path:
    target = repo / "services/api/src/auth_service.py"; target.parent.mkdir(parents=True, exist_ok=True)
    comment = "    # 刷新令牌检测到重放时必须回滚同一事务，避免旧会话继续获得有效凭据。\n" if reason else ""
    target.write_text((
        "def historical_complex(db, token, user):\n"
        "    if not token: raise ValueError('missing')\n"
        "    if user.disabled: raise PermissionError('disabled')\n"
        "    if token.replayed: db.rollback(); raise RuntimeError('replay')\n"
        "    db.commit(); return token\n\n"
        "def changed_complex(db, token, user):\n" + comment +
        "    if not token: raise ValueError('missing')\n"
        "    if user.disabled: raise PermissionError('disabled')\n"
        "    if token.replayed: db.rollback(); raise RuntimeError('replay')\n"
        "    db.commit(); return token\n"
    ), encoding="utf-8")
    return target


def _mechanical_delta(repo: Path, tmp_path: Path, mutate, *, lifecycle_profile: str = "FULL") -> tuple[Path, Path]:
    authority = repo / "docs/authority"; authority.mkdir(parents=True, exist_ok=True)
    marker = authority / "rules.yaml"
    if not marker.exists():
        marker.write_text("value: stable\n", encoding="utf-8")
    checkpoint = tmp_path / "task.checkpoint.json"
    created = _checkpoint(
        repo, "init", "--out", str(checkpoint), "--task-id", "TASK-COMMENT-GATE",
        "--workspace-identity", "wid", "--authority-root", "docs/authority", "--pack-revision", "0",
        "--lifecycle-profile", lifecycle_profile,
    )
    assert created.returncode == 0, created.stdout + created.stderr
    start = tmp_path / "start.json"; delta = tmp_path / "delta.json"
    c = _snapshot(repo, "capture", "--out", str(start)); assert c.returncode == 0, c.stdout + c.stderr
    mutate()
    d = _snapshot(repo, "delta", "--start", str(start), "--out", str(delta)); assert d.returncode == 0, d.stdout + d.stderr
    return delta, checkpoint


def test_snapshot_v4_mechanically_derives_only_changed_symbol(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = _write_auth_file(repo)
    def mutate() -> None:
        text = target.read_text(encoding="utf-8").replace("def changed_complex(db, token, user):\n", "def changed_complex(db, token, user):\n    value = 1\n")
        target.write_text(text, encoding="utf-8")
    delta, checkpoint = _mechanical_delta(repo, tmp_path, mutate)
    payload = json.loads(delta.read_text())["task_delta"]
    assert payload["change_scope_provenance"] == "FILESYSTEM_SNAPSHOT_V4"
    assert payload["changed_symbols"]["services/api/src/auth_service.py"] == ["changed_complex"]
    assert "historical_complex" not in payload["changed_symbols"]["services/api/src/auth_service.py"]


def test_formal_comment_gate_only_consumes_mechanical_task_delta(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = _write_auth_file(repo)
    delta, checkpoint = _mechanical_delta(repo, tmp_path, lambda: target.write_text(target.read_text(encoding="utf-8").replace("db.commit(); return token\n", "db.commit(); value = 1; return token\n", 1), encoding="utf-8"))
    completed = _gate(repo, "--task-delta", str(delta), "--checkpoint", str(checkpoint)); assert completed.returncode == 2
    payload = json.loads(completed.stdout); assert payload["finding_count"] == 1; assert payload["findings"][0]["symbol"] == "historical_complex"
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["code_quality"]["comment_gate"] is None
    rejected = _gate(repo, "--changed-symbol", "services/api/src/auth_service.py::historical_complex")
    assert rejected.returncode == 4 and "MECHANICAL_TASK_DELTA_REQUIRED" in rejected.stdout



def test_local_formal_code_write_uses_lightweight_cp0_and_still_runs_comment_gate(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = _write_auth_file(repo, reason=True)
    def mutate() -> None:
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "def changed_complex(db, token, user):\n",
                "def changed_complex(db, token, user):\n    value = 1\n",
                1,
            ),
            encoding="utf-8",
        )
    delta, checkpoint = _mechanical_delta(repo, tmp_path, mutate, lifecycle_profile="LIGHTWEIGHT_LOCAL")
    cp_data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert cp_data["lifecycle_profile"] == "LIGHTWEIGHT_LOCAL"
    assert cp_data["current_stage"] == "TASK_INITIALIZED"
    completed = _gate(repo, "--task-delta", str(delta), "--checkpoint", str(checkpoint))
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["status"] == "PASS"
    cp_after = json.loads(checkpoint.read_text(encoding="utf-8"))
    attestation = cp_after["code_quality"]["comment_gate"]
    assert attestation["status"] == "PASS"
    assert attestation["generated_by"] == "comment_quality_gate"
    assert attestation["workspace_fingerprint"]
    completed_local = _checkpoint(repo, "local-complete", "--checkpoint", str(checkpoint), "--task-id", "TASK-COMMENT-GATE")
    assert completed_local.returncode == 0, completed_local.stdout + completed_local.stderr

def test_caller_cannot_mix_manual_scope_into_formal_mode(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = _write_auth_file(repo)
    delta, checkpoint = _mechanical_delta(repo, tmp_path, lambda: target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8"))
    completed = _gate(repo, "--task-delta", str(delta), "--checkpoint", str(checkpoint), "--changed-symbol", "services/api/src/auth_service.py::changed_complex")
    assert completed.returncode == 4 and "FORMAL_SCOPE_MUST_BE_MECHANICAL_ONLY" in completed.stdout


def test_simple_risk_keyword_symbol_is_not_misclassified(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = repo / "services/api/src/state_reader.py"; target.parent.mkdir(parents=True); target.write_text("def get_state(state):\n    return state\n", encoding="utf-8")
    completed = _gate(repo, "--diagnostic-scope", "--changed-symbol", "services/api/src/state_reader.py::get_state")
    assert completed.returncode == 0 and json.loads(completed.stdout)["status"] == "PASS"


def test_complex_symbol_requires_reason_comment_not_any_chinese(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = repo / "services/api/src/auth.py"; target.parent.mkdir(parents=True)
    target.write_text("def rotate(db, token, user):\n    # 状态\n    if not token: raise ValueError()\n    if user.disabled: raise PermissionError()\n    if token.replayed: db.rollback(); raise RuntimeError()\n    db.commit(); return token\n", encoding="utf-8")
    completed = _gate(repo, "--diagnostic-scope", "--changed-symbol", "services/api/src/auth.py::rotate")
    assert completed.returncode == 2 and json.loads(completed.stdout)["finding_count"] == 1


def test_complex_symbol_passes_with_chinese_reason_comment(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = repo / "services/api/src/auth.py"; target.parent.mkdir(parents=True)
    target.write_text("def rotate(db, token, user):\n    # 检测重放后必须回滚同一事务，避免旧会话继续获得有效凭据。\n    if not token: raise ValueError()\n    if user.disabled: raise PermissionError()\n    if token.replayed: db.rollback(); raise RuntimeError()\n    db.commit(); return token\n", encoding="utf-8")
    completed = _gate(repo, "--diagnostic-scope", "--changed-symbol", "services/api/src/auth.py::rotate")
    assert completed.returncode == 0


def test_generated_sources_are_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; generated = repo / "apps/web/src/generated/client.ts"; generated.parent.mkdir(parents=True); generated.write_text("export function getToken(state) { return state.token }\n", encoding="utf-8")
    completed = _gate(repo, "--diagnostic-scope", "--changed-range", "apps/web/src/generated/client.ts:1-1")
    assert completed.returncode == 0; assert any(x["reason"] == "GENERATED_OR_BUILD_OUTPUT" for x in json.loads(completed.stdout)["skipped"])


def test_implementers_explicitly_require_mechanical_comment_scope() -> None:
    for path in (ROOT / ".codex/agents/backend_implementer.toml", ROOT / ".codex/agents/frontend_implementer.toml"):
        text = path.read_text(encoding="utf-8")
        for token in ("ai-auto-test-platform-code-quality", "Implementation Standards Mode", "MUST_APPLY_CODE_QUALITY_IMPLEMENTATION_STANDARDS", "comment_quality_gate.py"):
            assert token in text


def test_web_changed_symbols_are_checked_independently(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = repo / "apps/web/src/auth/session.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "// 刷新令牌重放时必须撤销旧会话，避免失效凭据继续访问受保护资源。\n"
        "export async function rotateToken(client, token, state) {\n"
        "  if (!token) throw new Error('missing')\n"
        "  if (state.replayed) await client.rollback()\n"
        "  await client.refresh(token)\n"
        "  return client.commit()\n"
        "}\n\n"
        "export async function updateCredential(client, token, state) {\n"
        "  if (!token) throw new Error('missing')\n"
        "  if (state.replayed) await client.rollback()\n"
        "  await client.refresh(token)\n"
        "  return client.commit()\n"
        "}\n",
        encoding="utf-8",
    )
    completed = _gate(
        repo,
        "--diagnostic-scope",
        "--changed-symbol", "apps/web/src/auth/session.ts::rotateToken",
        "--changed-symbol", "apps/web/src/auth/session.ts::updateCredential",
    )
    assert completed.returncode == 2, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["finding_count"] == 1
    assert payload["findings"][0]["symbol"] == "updateCredential"


def test_web_symbol_lookup_uses_declaration_boundary_not_call_sites(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = repo / "apps/web/src/auth/session.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "export async function rotateToken(client, token, state) {\n"
        "  if (!token) throw new Error('missing')\n"
        "  if (state.replayed) await client.rollback()\n"
        "  await client.refresh(token)\n"
        "  return client.commit()\n"
        "}\n\n"
        "export function caller(client, token, state) {\n"
        "  // 调用方只负责触发刷新，避免在这里重复认证事务规则。\n"
        "  return rotateToken(client, token, state)\n"
        "}\n",
        encoding="utf-8",
    )
    completed = _gate(repo, "--diagnostic-scope", "--changed-symbol", "apps/web/src/auth/session.ts::rotateToken")
    assert completed.returncode == 2, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["finding_count"] == 1
    assert payload["findings"][0]["symbol"] == "rotateToken"


def test_web_reason_comment_inside_previous_symbol_cannot_satisfy_adjacent_symbol(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = repo / "apps/web/src/auth/session.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "export async function rotateToken(client, token, state) {\n"
        "  if (!token) throw new Error('missing')\n"
        "  if (state.replayed) await client.rollback()\n"
        "  // 这里必须回滚旧事务，避免失效会话继续访问受保护资源。\n"
        "  await client.refresh(token)\n"
        "  return client.commit()\n"
        "}\n"
        "export async function updateCredential(client, token, state) {\n"
        "  if (!token) throw new Error('missing')\n"
        "  if (state.replayed) await client.rollback()\n"
        "  await client.refresh(token)\n"
        "  return client.commit()\n"
        "}\n",
        encoding="utf-8",
    )
    completed = _gate(repo, "--diagnostic-scope", "--changed-symbol", "apps/web/src/auth/session.ts::updateCredential")
    assert completed.returncode == 2, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["finding_count"] == 1
    assert payload["findings"][0]["symbol"] == "updateCredential"


def test_web_contiguous_leading_reason_comment_is_owned_by_symbol(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = repo / "apps/web/src/auth/session.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "// 修改凭据前必须撤销旧刷新会话，避免旧凭据继续换取访问令牌。\n"
        "export async function updateCredential(client, token, state) {\n"
        "  if (!token) throw new Error('missing')\n"
        "  if (state.replayed) await client.rollback()\n"
        "  await client.refresh(token)\n"
        "  return client.commit()\n"
        "}\n",
        encoding="utf-8",
    )
    completed = _gate(repo, "--diagnostic-scope", "--changed-symbol", "apps/web/src/auth/session.ts::updateCredential")
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_forged_empty_task_delta_cannot_bypass_mechanical_scope(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = _write_auth_file(repo)
    delta, checkpoint = _mechanical_delta(
        repo, tmp_path,
        lambda: target.write_text(target.read_text(encoding="utf-8").replace("def changed_complex(db, token, user):\n", "def changed_complex(db, token, user):\n    value = 1\n"), encoding="utf-8"),
    )
    payload = json.loads(delta.read_text(encoding="utf-8"))
    payload["task_delta"] = {
        "status": "EMPTY", "reason_code": None, "read_error": None, "added": [], "removed": [], "modified": [],
        "task_delta_paths": [], "changed_symbols": {}, "changed_line_ranges": {}, "removed_symbols": {},
        "change_scope_provenance": "FILESYSTEM_SNAPSHOT_V4", "change_scope_digest": "forged", "delta_digest": "forged",
    }
    forged = tmp_path / "forged-delta.json"; forged.write_text(json.dumps(payload), encoding="utf-8")
    completed = _gate(repo, "--task-delta", str(forged), "--checkpoint", str(checkpoint))
    assert completed.returncode == 4
    assert "TASK_DELTA_RECOMPUTE_MISMATCH" in completed.stdout


def test_stale_task_delta_replay_is_rejected_after_new_workspace_change(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = _write_auth_file(repo, reason=True)
    delta, checkpoint = _mechanical_delta(
        repo, tmp_path,
        lambda: target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8"),
    )
    first = _gate(repo, "--task-delta", str(delta), "--checkpoint", str(checkpoint))
    assert first.returncode == 0, first.stdout + first.stderr
    target.write_text(target.read_text(encoding="utf-8") + "# later change\n", encoding="utf-8")
    replay = _gate(repo, "--task-delta", str(delta), "--checkpoint", str(checkpoint))
    assert replay.returncode == 4
    assert "TASK_DELTA_STALE_REPLAY" in replay.stdout


def test_formal_comment_gate_requires_checkpoint_bound_task_start(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = _write_auth_file(repo)
    delta, _checkpoint_path = _mechanical_delta(repo, tmp_path, lambda: target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8"))
    completed = _gate(repo, "--task-delta", str(delta))
    assert completed.returncode == 4
    assert "TASK_CHECKPOINT_REQUIRED_FOR_MECHANICAL_DELTA" in completed.stdout


def test_python_reason_comment_inside_previous_symbol_cannot_satisfy_adjacent_symbol(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = repo / "services/api/src/auth/session.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "def helper(db, token, user):\n"
        "    if not token:\n"
        "        raise ValueError()\n"
        "    # 为了避免旧事务状态泄漏，这里必须回滚并清理缓存。\n"
        "    db.rollback()\n"
        "    return user\n"
        "\n"
        "def refresh_token_session(db, token, user):\n"
        "    if not token:\n"
        "        raise ValueError()\n"
        "    if user.disabled:\n"
        "        raise PermissionError()\n"
        "    if token.replayed:\n"
        "        db.rollback()\n"
        "        raise RuntimeError()\n"
        "    db.commit()\n"
        "    return token\n",
        encoding="utf-8",
    )
    completed = _gate(repo, "--diagnostic-scope", "--changed-symbol", "services/api/src/auth/session.py::refresh_token_session")
    assert completed.returncode == 2, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["finding_count"] == 1
    assert payload["findings"][0]["symbol"] == "refresh_token_session"


def test_python_contiguous_same_indent_leading_reason_comment_is_owned_by_symbol(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target = repo / "services/api/src/auth/session.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# 刷新会话前必须校验重放状态，避免旧凭据继续换取访问令牌。\n"
        "def refresh_token_session(db, token, user):\n"
        "    if not token:\n"
        "        raise ValueError()\n"
        "    if user.disabled:\n"
        "        raise PermissionError()\n"
        "    if token.replayed:\n"
        "        db.rollback()\n"
        "        raise RuntimeError()\n"
        "    db.commit()\n"
        "    return token\n",
        encoding="utf-8",
    )
    completed = _gate(repo, "--diagnostic-scope", "--changed-symbol", "services/api/src/auth/session.py::refresh_token_session")
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_real_formal_gate_attestation_is_invalidated_by_post_gate_workspace_change(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = _write_auth_file(repo, reason=True)
    def mutate() -> None:
        target.write_text(target.read_text(encoding="utf-8").replace("def changed_complex(db, token, user):\n", "def changed_complex(db, token, user):\n    value = 1\n", 1), encoding="utf-8")
    delta, checkpoint = _mechanical_delta(repo, tmp_path, mutate, lifecycle_profile="LIGHTWEIGHT_LOCAL")
    passed = _gate(repo, "--task-delta", str(delta), "--checkpoint", str(checkpoint))
    assert passed.returncode == 0, passed.stdout + passed.stderr
    target.write_text(target.read_text(encoding="utf-8") + "\n# later change\n", encoding="utf-8")
    blocked = _checkpoint(repo, "local-complete", "--checkpoint", str(checkpoint), "--task-id", "TASK-COMMENT-GATE")
    assert blocked.returncode == 3
    assert json.loads(blocked.stdout)["status"] == "COMMENT_GATE_WORKSPACE_CHANGED_AFTER_PASS"


def test_real_full_gate_attestation_is_required_by_verification_stage(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; target = _write_auth_file(repo, reason=True)
    def mutate() -> None:
        target.write_text(target.read_text(encoding="utf-8").replace("def changed_complex(db, token, user):\n", "def changed_complex(db, token, user):\n    value = 1\n", 1), encoding="utf-8")
    delta, checkpoint = _mechanical_delta(repo, tmp_path, mutate, lifecycle_profile="FULL")
    for stage in ("CONTEXT_READY", "DECISIONS_READY", "IMPLEMENTATION_READY", "IMPLEMENTATION_COMPLETE"):
        advanced = _checkpoint(repo, "advance", "--checkpoint", str(checkpoint), "--task-id", "TASK-COMMENT-GATE", "--stage", stage, "--pack-revision", "1")
        assert advanced.returncode == 0, advanced.stdout + advanced.stderr
    blocked = _checkpoint(repo, "advance", "--checkpoint", str(checkpoint), "--task-id", "TASK-COMMENT-GATE", "--stage", "VERIFICATION_COMPLETE", "--pack-revision", "1")
    assert blocked.returncode == 3
    assert json.loads(blocked.stdout)["status"] == "COMMENT_GATE_ATTESTATION_MISSING"
    passed = _gate(repo, "--task-delta", str(delta), "--checkpoint", str(checkpoint))
    assert passed.returncode == 0, passed.stdout + passed.stderr
    verified = _checkpoint(repo, "advance", "--checkpoint", str(checkpoint), "--task-id", "TASK-COMMENT-GATE", "--stage", "VERIFICATION_COMPLETE", "--pack-revision", "1")
    assert verified.returncode == 0, verified.stdout + verified.stderr
    cp_data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert cp_data["stages"]["VERIFICATION_COMPLETE"]["evidence"]["comment_quality_gate"]["status"] == "COMMENT_GATE_PASS"
