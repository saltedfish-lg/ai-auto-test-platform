"""API command-line entrypoint."""

from __future__ import annotations

import argparse
import json

import uvicorn

from platform_api.app import create_app
from platform_api.config import ApiSettings
from platform_api.health import process_self_check


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Validate process assembly and exit.")
    args = parser.parse_args()
    settings = ApiSettings()
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


if __name__ == "__main__":
    raise SystemExit(main())
