from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from platform_api.bootstrap import AdminBootstrapService
from platform_api.models import AuthSecurityAudit, OutboxEvent, Role
from platform_api.security import PasswordService, new_ulid
from sqlalchemy.orm import Session, sessionmaker


class _BootstrapSession:
    def __init__(self, role: Role) -> None:
        self._role = role
        self._scalar_calls = 0
        self.added: list[object] = []

    def get(self, _model: object, _key: object) -> None:
        return None

    def scalar(self, _statement: object) -> object | None:
        self._scalar_calls += 1
        return None if self._scalar_calls == 1 else self._role

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    def flush(self) -> None:
        return None


class _BootstrapSessionFactory:
    def __init__(self, session: _BootstrapSession) -> None:
        self.session = session

    @contextmanager
    def begin(self) -> Iterator[_BootstrapSession]:
        yield self.session


def test_bootstrap_uses_one_canonical_correlation_for_outbox_and_audit() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    role = Role(
        role_id=new_ulid(),
        role_code="ROLE-SUPER-ADMIN",
        lifecycle_status="ACTIVE",
        display_name="Super admin",
        row_version=1,
        created_at=now,
        updated_at=now,
        created_by=None,
        updated_by=None,
        extension_json=None,
    )
    db = _BootstrapSession(role)
    factory = _BootstrapSessionFactory(db)
    service = AdminBootstrapService(
        cast(sessionmaker[Session], factory),
        PasswordService(),
    )
    supplied = "bootstrap-correlation-containing-a-secret"

    result = service.bootstrap("Bootstrap-Unit-Password-7", supplied)

    outbox_events = [value for value in db.added if isinstance(value, OutboxEvent)]
    audits = [value for value in db.added if isinstance(value, AuthSecurityAudit)]
    assert result.status == "INITIALIZED"
    assert len(outbox_events) == 3
    assert len(audits) == 1
    correlations = {cast(str, event.payload_json["correlation_id"]) for event in outbox_events}
    correlations.add(audits[0].correlation_id)
    assert len(correlations) == 1
    canonical = correlations.pop()
    assert canonical != supplied
    assert str(UUID(canonical)) == canonical
