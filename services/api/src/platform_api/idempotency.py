"""V7 no-secret idempotency claim coordinator for authenticated commands."""

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
        storage_keys = self._keys.hex_digests(
            "idempotency-storage-key",
            framed("storage", principal_id, operation_id, raw_key),
        )
        fingerprints = self._keys.hex_digests(
            "idempotency-storage-key",
            framed("request", principal_id, operation_id) + request_payload,
        )
        now = utc_now()
        rows = list(
            db.scalars(
                select(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key.in_((raw_key, *storage_keys)))
                .order_by(IdempotencyRecord.idempotency_key)
                .with_for_update()
            )
        )
        existing = next((row for row in rows if row.expires_at > now), None)
        if existing is not None:
            self._validate(existing, principal_id, operation_id, fingerprints)
            if existing.response_status is None or existing.completed_at is None:
                raise PlatformError(
                    title="Concurrent idempotent request is incomplete",
                    detail="The idempotent command has not reached a terminal state.",
                    status=409,
                    code="AUTH_CONCURRENCY_CONFLICT",
                )
            return existing, True
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
            return record, True
        return record, False

    @staticmethod
    def complete(
        record: IdempotencyRecord,
        status: int,
        response_json: dict[str, object] | None,
    ) -> None:
        record.response_status = status
        record.response_json = response_json
        record.completed_at = utc_now()

    @staticmethod
    def _validate(
        record: IdempotencyRecord,
        principal_id: str,
        operation_id: str,
        fingerprints: tuple[str, ...],
    ) -> None:
        if (
            record.contract_version != 2
            or record.principal_id != principal_id
            or record.operation_id != operation_id
            or record.request_hash not in fingerprints
        ):
            raise PlatformError(
                title="Idempotency key conflict",
                detail="The idempotency key was reused with a different request.",
                status=409,
                code="AUTH_IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST",
            )
