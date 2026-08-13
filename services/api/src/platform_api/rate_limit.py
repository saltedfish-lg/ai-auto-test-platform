"""Shared MySQL source-rate limiting and trusted-proxy source resolution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.audit import AuditContext, AuthenticationAuditService
from platform_api.auth_hmac import AuthHmacKeyRing
from platform_api.errors import PlatformError
from platform_api.models import AuthSourceRateLimit
from platform_api.security import utc_now

IpAddress = IPv4Address | IPv6Address
IpNetwork = IPv4Network | IPv6Network
_LIMITS = {"login_platform_user": 60, "refresh_platform_session": 300}


def resolve_source_ip(
    direct_peer: str,
    forwarded: str | None,
    x_forwarded_for: str | None,
    trusted_networks: tuple[IpNetwork, ...],
) -> str:
    """Resolve one canonical source while treating forwarding headers as untrusted input."""
    peer = _parse_ip(direct_peer)
    if peer is None:
        # ASGI servers provide an IP; an invalid transport value is collapsed to a
        # single non-spoofable bucket instead of trusting a caller-controlled header.
        peer = ip_address("0.0.0.0")
    if not _trusted(peer, trusted_networks):
        return peer.compressed
    chain = _forwarded_chain(forwarded) if forwarded else None
    if chain is None and not forwarded and x_forwarded_for:
        chain = _xff_chain(x_forwarded_for)
    if not chain:
        return peer.compressed
    for candidate in reversed([*chain, peer]):
        if not _trusted(candidate, trusted_networks):
            return candidate.compressed
    return chain[0].compressed


def _trusted(value: IpAddress, networks: tuple[IpNetwork, ...]) -> bool:
    return any(value.version == network.version and value in network for network in networks)


def _parse_ip(value: str) -> IpAddress | None:
    candidate = value.strip()
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.rsplit(":", 1)[0]
    try:
        return ip_address(candidate)
    except ValueError:
        return None


def _forwarded_chain(value: str) -> list[IpAddress] | None:
    result: list[IpAddress] = []
    for element in value.split(","):
        parameters = [item.strip() for item in element.split(";")]
        raw_for = next(
            (item[4:] for item in parameters if item.casefold().startswith("for=")), None
        )
        if raw_for is None:
            return None
        candidate = raw_for.strip().strip('"')
        parsed = _parse_ip(candidate)
        if parsed is None:
            return None
        result.append(parsed)
    return result


def _xff_chain(value: str) -> list[IpAddress] | None:
    result: list[IpAddress] = []
    for item in value.split(","):
        parsed = _parse_ip(item)
        if parsed is None:
            return None
        result.append(parsed)
    return result


class AuthenticationRateLimitService:
    """Consume a fixed-window source permit in an independent short transaction."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        keys: AuthHmacKeyRing,
        audit: AuthenticationAuditService,
    ) -> None:
        self._factory = factory
        self._keys = keys
        self._audit = audit

    def consume(self, operation_id: str, source_ip: str, audit_context: AuditContext) -> None:
        limit = _LIMITS[operation_id]
        now = utc_now()
        epoch_seconds = int(now.replace(tzinfo=UTC).timestamp())
        window = datetime.fromtimestamp(epoch_seconds // 300 * 300, UTC).replace(tzinfo=None)
        expires = window + timedelta(seconds=300)
        digests = self._keys.digests("source-rate-limit", source_ip.encode("ascii"))
        active_digest = digests[0]
        try:
            with self._factory.begin() as db:
                existing_digest = db.scalar(
                    select(AuthSourceRateLimit.source_key_hash)
                    .where(
                        AuthSourceRateLimit.source_key_hash.in_(digests),
                        AuthSourceRateLimit.operation_id == operation_id,
                        AuthSourceRateLimit.window_started_at == window,
                    )
                    .order_by(AuthSourceRateLimit.source_key_hash)
                    .limit(1)
                )
                row = None
                if existing_digest is not None:
                    # 不存在行上的范围锁会让不同来源的并发首次请求形成gap-lock死锁;
                    # 先做一致性读选定轮换兼容摘要, 再只锁定完整主键对应的单行.
                    row = db.scalar(
                        select(AuthSourceRateLimit)
                        .where(
                            AuthSourceRateLimit.source_key_hash == existing_digest,
                            AuthSourceRateLimit.operation_id == operation_id,
                            AuthSourceRateLimit.window_started_at == window,
                        )
                        .with_for_update()
                    )
                if row is None:
                    statement = mysql_insert(AuthSourceRateLimit).values(
                        source_key_hash=active_digest,
                        operation_id=operation_id,
                        window_started_at=window,
                        request_count=1,
                        expires_at=expires,
                        row_version=0,
                    )
                    statement = statement.on_duplicate_key_update(
                        request_count=func.least(
                            AuthSourceRateLimit.request_count + 1,
                            limit + 1,
                        ),
                        row_version=AuthSourceRateLimit.row_version + 1,
                    )
                    db.execute(statement)
                    row = db.scalar(
                        select(AuthSourceRateLimit)
                        .where(
                            AuthSourceRateLimit.source_key_hash == active_digest,
                            AuthSourceRateLimit.operation_id == operation_id,
                            AuthSourceRateLimit.window_started_at == window,
                        )
                        .with_for_update()
                    )
                    if row is None:
                        raise RuntimeError("source rate-limit row was not materialized")
                else:
                    row.request_count = min(limit + 1, row.request_count + 1)
                    row.row_version += 1
                count = row.request_count
                if count > limit:
                    self._audit.append(
                        db,
                        audit_context,
                        action=(
                            "LOGIN_FAILED"
                            if operation_id == "login_platform_user"
                            else "REFRESH_FAILED"
                        ),
                        operation_id=operation_id,
                        result_code="AUTH_SOURCE_RATE_LIMITED",
                    )
        except (SQLAlchemyError, RuntimeError) as error:
            raise PlatformError(
                title="Authentication rate-limit state unavailable",
                detail=(
                    "Authentication cannot continue because shared rate-limit state is unavailable."
                ),
                status=503,
                code="AUTH_RATE_LIMIT_STATE_UNAVAILABLE",
            ) from error
        if count > limit:
            retry_after = max(1, min(300, int((expires - now).total_seconds()) + 1))
            raise PlatformError(
                title="Authentication source rate limited",
                detail="Too many authentication requests were received from this source.",
                status=429,
                code="AUTH_SOURCE_RATE_LIMITED",
                headers={"Retry-After": str(retry_after)},
            )
