from __future__ import annotations

import pytest

from platform_api.errors import PlatformError
from platform_api.user_admin_router import router
from platform_api.user_admin_service import _parse_user_filter


def test_list_user_runtime_route_is_registered() -> None:
    operations = {
        (method, route.path, route.operation_id)
        for route in router.routes
        for method in route.methods or set()
    }
    assert ("GET", "/api/v1/user", "list_user") in operations


def test_user_directory_filter_is_bounded_to_declared_fields() -> None:
    assert _parse_user_filter("lifecycle_status=ACTIVE") == {"lifecycle_status": "ACTIVE"}
    assert _parse_user_filter("username=operator01") == {"username": "operator01"}
    with pytest.raises(PlatformError) as error:
        _parse_user_filter("project_id=01M00000000000000000000000")
    assert error.value.status == 400
    assert error.value.code == "AUTH_REQUEST_VALIDATION_FAILED"
