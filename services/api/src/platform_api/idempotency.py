"""V7 no-secret idempotency state owner for authenticated commands."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from platform_api.auth_hmac import AuthHmacKeyRing
from platform_api.errors import PlatformError
from platform_api.models import IdempotencyRecord
from platform_api.security import utc_now


def framed(*values: str) -> bytes:
    encoded = [value.encode("utf-8") for value in values]
    return b"".join(len(value).to_bytes(4, "big") + value for value in encoded)


class IdempotencyCoordinator:
    """Claim the physical key before aggregate locks and preserve terminal projections."""

    def __init__(self, keys: AuthHmacKeyRing) -> None:
        self._keys = keys

    def claim(
        self,
        db: Session,
        principal_id: str,
        operation_id: str,
        raw_key: str,
        request_payload: bytes,
    ) -> tuple[IdempotencyRecord, bool]:
        """通用命令通过统一声明路径锁定物理键, 确保多实例竞争只产生一个副作用。"""
        storage_keys = self._keys.hex_digests(
            "idempotency-storage-key",
            framed("storage", principal_id, operation_id, raw_key),
        )
        fingerprints = self._keys.hex_digests(
            "idempotency-storage-key",
            framed("request", principal_id, operation_id) + request_payload,
        )
        return self._claim(db, principal_id, operation_id, raw_key, storage_keys, fingerprints)

    def claim_change_password(
        self,
        db: Session,
        principal_id: str,
        raw_key: str,
        current_password: str,
        new_password: str,
    ) -> tuple[IdempotencyRecord, bool]:
        """改密指纹使用独立HMAC域, 且兼容候选必须保持与既有V7记录完全一致。"""
        operation_id = "change_current_user_password"
        storage_keys = self._keys.hex_digests(
            "idempotency-storage-key",
            framed(principal_id, operation_id, raw_key),
        )
        fingerprints = self._keys.hex_digests(
            "change-password-fingerprint",
            framed(current_password, new_password),
        )
        return self._claim(
            db,
            principal_id,
            operation_id,
            raw_key,
            storage_keys,
            fingerprints,
            terminal_status=204,
        )

    def _claim(
        self,
        db: Session,
        principal_id: str,
        operation_id: str,
        raw_key: str,
        storage_keys: tuple[str, ...],
        fingerprints: tuple[str, ...],
        *,
        terminal_status: int | None = None,
    ) -> tuple[IdempotencyRecord, bool]:
        """声明、过期复用与终态重放集中在同一锁序, 确保并发请求只产生一次副作用。"""
        now = utc_now()
        candidate_keys = (raw_key, *storage_keys)
        existing_keys = tuple(
            db.scalars(
                select(IdempotencyRecord.idempotency_key).where(
                    IdempotencyRecord.idempotency_key.in_(candidate_keys)
                )
            )
        )
        rows: list[IdempotencyRecord]
        inserted_new = False
        if existing_keys:
            # 仅锁定已存在的唯一键记录。空结果上的``FOR UPDATE``会获取gap lock,
            # 两个首请求随后插入同一键时会互相等待并触发MySQL 1213死锁。
            rows = list(
                db.scalars(
                    select(IdempotencyRecord)
                    .where(IdempotencyRecord.idempotency_key.in_(existing_keys))
                    .order_by(IdempotencyRecord.idempotency_key)
                    .with_for_update()
                )
            )
        else:
            active_key = storage_keys[0]
            active_fingerprint = fingerprints[0]
            statement = mysql_insert(IdempotencyRecord).values(
                idempotency_key=active_key,
                contract_version=2,
                principal_id=principal_id,
                operation_id=operation_id,
                request_hash=active_fingerprint,
                response_status=None,
                response_json=None,
                completed_at=None,
                expires_at=now + timedelta(days=1),
            )
            # INSERT IGNORE的唯一键首先取得记录级竞争点。后到事务等待首事务提交;
            # rowcount=0表示读取竞争者终态, rowcount=1表示当前事务拥有首次执行权。
            result = db.execute(statement.prefix_with("IGNORE"))
            inserted_new = result.rowcount == 1
            materialized = db.scalar(
                select(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key == active_key)
                .with_for_update()
            )
            if materialized is None:
                raise RuntimeError("idempotency claim was not materialized")
            rows = [materialized]
        rows_by_key = {row.idempotency_key: row for row in rows}
        existing = next(
            (
                rows_by_key[key]
                for key in candidate_keys
                if key in rows_by_key and rows_by_key[key].expires_at > now
            ),
            None,
        )
        if existing is not None and not inserted_new:
            self._validate(existing, principal_id, operation_id, fingerprints)
            if existing.response_status is None or existing.completed_at is None:
                raise PlatformError(
                    title="Concurrent idempotent request is incomplete",
                    detail="The idempotent command has not reached a terminal state.",
                    status=409,
                    code="AUTH_CONCURRENCY_CONFLICT",
                )
            if terminal_status is not None and existing.response_status != terminal_status:
                raise self._conflict()
            return existing, True
        if inserted_new:
            return rows_by_key[storage_keys[0]], False
        active_key = storage_keys[0]
        active_fingerprint = fingerprints[0]
        expired = next(
            (
                row
                for row in rows
                if row.idempotency_key == active_key and row.contract_version == 2
            ),
            None,
        )
        if expired is not None:
            expired.principal_id = principal_id
            expired.operation_id = operation_id
            expired.request_hash = active_fingerprint
            expired.response_status = None
            expired.response_json = None
            expired.completed_at = None
            expired.expires_at = now + timedelta(days=1)
            return expired, False
        statement = mysql_insert(IdempotencyRecord).values(
            idempotency_key=active_key,
            contract_version=2,
            principal_id=principal_id,
            operation_id=operation_id,
            request_hash=active_fingerprint,
            response_status=None,
            response_json=None,
            completed_at=None,
            expires_at=now + timedelta(days=1),
        )
        db.execute(
            statement.on_duplicate_key_update(idempotency_key=IdempotencyRecord.idempotency_key)
        )
        record = db.scalar(
            select(IdempotencyRecord)
            .where(IdempotencyRecord.idempotency_key == active_key)
            .with_for_update()
        )
        if record is None:
            raise RuntimeError("idempotency claim was not materialized")
        self._validate(record, principal_id, operation_id, fingerprints)
        if record.response_status is not None and record.completed_at is not None:
            if terminal_status is not None and record.response_status != terminal_status:
                raise self._conflict()
            return record, True
        return record, False

    @staticmethod
    def complete(
        record: IdempotencyRecord,
        status: int,
        response_json: dict[str, object] | None,
    ) -> None:
        """终态投影与24小时保留期一并写入调用方事务, JSON空值保持SQL NULL。"""
        completed_at = utc_now()
        record.response_status = status
        record.response_json = response_json
        record.completed_at = completed_at
        record.expires_at = completed_at + timedelta(days=1)

    @staticmethod
    def _validate(
        record: IdempotencyRecord,
        principal_id: str,
        operation_id: str,
        fingerprints: tuple[str, ...],
    ) -> None:
        """物理记录必须匹配主体、操作与候选指纹, 避免轮换兼容扩大为跨请求重放。"""
        if (
            record.contract_version != 2
            or record.principal_id != principal_id
            or record.operation_id != operation_id
            or record.request_hash not in fingerprints
        ):
            raise IdempotencyCoordinator._conflict()

    @staticmethod
    def _conflict() -> PlatformError:
        return PlatformError(
            title="Idempotency key conflict",
            detail="The idempotency key was reused with a different request.",
            status=409,
            code="AUTH_IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST",
        )
