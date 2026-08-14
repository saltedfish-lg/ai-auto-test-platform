from __future__ import annotations

import pytest
from platform_api.auth_schemas import (
    AuthenticationTokenResource,
    ChangePasswordRequest,
    CurrentUserResource,
    LoginRequest,
    OneTimeCredentialDeliveryResource,
    UserResource,
)
from platform_api.auth_service import AuthenticationResult
from platform_api.security import PasswordPolicyError, PasswordService, utc_now
from pydantic import ValidationError


@pytest.mark.parametrize(
    "password",
    [
        "纯中文密码十二位纯中文123",
        "AsciiLettersOnly\u0661\u0662\u0663",
    ],
)
def test_password_policy_requires_openapi_ascii_letter_and_digit_classes(password: str) -> None:
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="CurrentPassword123", new_password=password)
    with pytest.raises(PasswordPolicyError):
        PasswordService().validate(password, "operator")


def test_secret_bearing_dtos_hide_credentials_from_repr() -> None:
    password = "SentinelPassword123"
    access_token = "sentinel-access-token-" + ("x" * 32)
    refresh_token = "sentinel-refresh-token-" + ("y" * 32)
    temporary_password = "SentinelTemporary123"
    user = CurrentUserResource(
        user_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        username="operator",
        lifecycle_status="ACTIVE",
        roles=[],
        permissions=[],
        force_password_change=False,
    )
    now = utc_now()
    temporary_delivery = OneTimeCredentialDeliveryResource(
        user=UserResource(
            user_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            display_name="Operator",
            row_version=1,
            created_at=now,
            updated_at=now,
            lifecycle_status="ACTIVE",
        ),
        delivery_status="ISSUED",
        temporary_password=temporary_password,
    )

    values = (
        LoginRequest(username="operator", password=password),
        ChangePasswordRequest(current_password=password, new_password="NewPassword456"),
        AuthenticationTokenResource(
            access_token=access_token,
            expires_in=900,
            current_user=user,
        ),
        AuthenticationResult(
            access_token=access_token,
            refresh_token=refresh_token,
            current_user=user,
        ),
        temporary_delivery,
    )

    rendered = " ".join(repr(value) for value in values)
    assert password not in rendered
    assert access_token not in rendered
    assert refresh_token not in rendered
    assert temporary_password not in rendered
