"""API command-line entrypoint."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from uuid import uuid4

import uvicorn

from platform_api.app import create_app
from platform_api.audit import AuthenticationAuditService
from platform_api.bootstrap import AdminBootstrapService
from platform_api.config import ApiSettings
from platform_api.database import create_database_engine, create_session_factory
from platform_api.health import process_self_check
from platform_api.keygen import generate_development_key_ring
from platform_api.security import PasswordService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Validate process assembly and exit.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("bootstrap-admin", help="Initialize the protected default admin.")
    key_parser = subparsers.add_parser(
        "generate-dev-rsa-keys", help="Generate non-overwriting local RS256 key files."
    )
    key_parser.add_argument("--output-directory", type=Path, default=Path(".runtime/secrets"))
    args = parser.parse_args()
    if args.command == "generate-dev-rsa-keys":
        key_ring = generate_development_key_ring(args.output_directory)
        print(
            json.dumps(
                {
                    "status": "CREATED",
                    "key_ring_file": str(key_ring.manifest_file),
                    "ring_version": key_ring.ring_version,
                    "active_signing_kid": key_ring.kid,
                    "algorithm": "RS256",
                }
            )
        )
        return 0
    settings = ApiSettings()
    if args.command == "bootstrap-admin":
        password = _read_bootstrap_password(settings)
        service = AdminBootstrapService(
            create_session_factory(create_database_engine(settings.database_url)),
            PasswordService(),
            AuthenticationAuditService(),
        )
        result = service.bootstrap(password, str(uuid4()))
        print(json.dumps(result.safe_dict(), ensure_ascii=False))
        return 0
    if args.check:
        create_app(settings)
        print(json.dumps(process_self_check(settings), ensure_ascii=False))
        return 0
    uvicorn.run(
        create_app(settings),
        host=str(settings.host),
        port=settings.port,
        log_config=None,
    )
    return 0


def _read_bootstrap_password(settings: ApiSettings) -> str:
    password_file = settings.bootstrap_admin_password_file
    if password_file is not None:
        password = password_file.read_text(encoding="utf-8").rstrip("\r\n")
        if not password:
            raise RuntimeError("bootstrap password file is empty")
        return password
    if not sys.stdin.isatty():
        raise RuntimeError("bootstrap-admin requires a TTY or ATP_BOOTSTRAP_ADMIN_PASSWORD_FILE")
    first = getpass.getpass("Initial admin password: ")
    second = getpass.getpass("Confirm initial admin password: ")
    if first != second:
        raise RuntimeError("password confirmation does not match")
    return first


if __name__ == "__main__":
    raise SystemExit(main())
