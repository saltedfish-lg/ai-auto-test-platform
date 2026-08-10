"""R4.2 P1 platform API assembly."""

from platform_api.app import create_app
from platform_api.config import ApiSettings

__all__ = ["ApiSettings", "create_app"]
