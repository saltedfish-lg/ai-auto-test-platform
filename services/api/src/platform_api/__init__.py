"""P0 API process foundation without business routes."""

from platform_api.app import create_app
from platform_api.config import ApiSettings

__all__ = ["ApiSettings", "create_app"]
