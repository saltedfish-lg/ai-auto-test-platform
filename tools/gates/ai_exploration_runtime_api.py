#!/usr/bin/env python3
"""Run the formal API assembly for isolated AI exploration acceptance."""

from __future__ import annotations

import uvicorn
from platform_api.app import create_app
from platform_api.config import ApiSettings


def main() -> int:
    settings = ApiSettings()
    app = create_app(settings)
    uvicorn.run(
        app,
        host=str(settings.host),
        port=settings.port,
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
