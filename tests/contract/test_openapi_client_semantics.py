from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATED_CLIENT = ROOT / "apps" / "web" / "src" / "generated" / "client.ts"
GENERATED_TYPES = ROOT / "apps" / "web" / "src" / "generated" / "types.ts"


def test_generated_client_preserves_bodyless_204_semantics() -> None:
    client = GENERATED_CLIENT.read_text(encoding="utf-8")

    assert "if (response.status === 204) return undefined as T;" in client
    assert (
        "async change_current_user_password(body: ChangePasswordRequest, "
        'options: RequiredHeaderOptions<"Idempotency-Key">): Promise<void>'
    ) in client
    assert "this.request<void>(path" in client


def test_generated_client_requires_declared_mandatory_headers() -> None:
    client = GENERATED_CLIENT.read_text(encoding="utf-8")

    assert "export type RequiredHeaderOptions<K extends string>" in client
    for operation in (
        "create_user",
        "reset_user_credential",
        "enable_user",
        "disable_user",
        "create_user_role_binding",
        "revoke_user_role_binding",
    ):
        method_start = client.index(f"async {operation}(")
        method_end = client.index("): Promise<", method_start)
        signature = client[method_start:method_end]
        assert 'RequiredHeaderOptions<"Idempotency-Key">' in signature


def test_generated_client_preserves_optional_closed_empty_request_bodies() -> None:
    client = GENERATED_CLIENT.read_text(encoding="utf-8")
    types = GENERATED_TYPES.read_text(encoding="utf-8")

    assert "export type AuthCookieActionRequest = Record<string, never>;" in types
    assert (
        "async refresh_platform_session(body?: AuthCookieActionRequest, "
        "options: RequestOptions = {}): Promise<AuthenticationResponse>"
    ) in client
    assert (
        "async logout_platform_user(body?: AuthCookieActionRequest, "
        "options: RequestOptions = {}): Promise<void>"
    ) in client
    assert "body === undefined ? {} : { body: JSON.stringify(body) }" in client


def test_generated_types_preserve_openapi_const_literals() -> None:
    types = GENERATED_TYPES.read_text(encoding="utf-8")

    resource_start = types.index("export type OneTimeCredentialDeliveryResource")
    resource_end = types.index("export type OneTimeCredentialDeliveryResponse", resource_start)
    assert "force_password_change: true;" in types[resource_start:resource_end]
