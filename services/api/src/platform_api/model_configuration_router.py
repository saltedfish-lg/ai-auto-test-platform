"""FastAPI adapter for AI model configuration and platform default binding."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Path, Query, Request

from platform_api.auth_router import _audit_context, _bearer, _correlation_id
from platform_api.errors import PlatformError
from platform_api.model_configuration_schemas import (
    ClearCapabilityDefaultModelRequest,
    ClearCapabilityDefaultModelResponse,
    CreateModelConfigRequest,
    ModelConfigLifecycleRequest,
    ModelConfigListData,
    ModelConfigResponse,
    SetCapabilityDefaultModelRequest,
    SetCapabilityDefaultModelResponse,
    TestModelConfigConnectionRequest,
    TestModelConfigConnectionResponse,
    UpdateModelConfigRequest,
)
from platform_api.model_configuration_service import ModelConfigurationService

router = APIRouter(tags=["模型配置"])
ModelId = Annotated[str, Path(min_length=26, max_length=26)]


def _service(request: Request) -> ModelConfigurationService:
    service = getattr(request.app.state, "model_configuration_service", None)
    if not isinstance(service, ModelConfigurationService):
        raise PlatformError(
            title="Model configuration is unavailable",
            detail="The model configuration service has not been configured.",
            status=500,
            code="INTERNAL_ERROR",
        )
    return service


@router.get(
    "/api/v1/model-config",
    response_model=ModelConfigListData,
    response_model_exclude_none=True,
    operation_id="list_model_config",
)
def list_model_config(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> ModelConfigListData:
    return _service(request).list_model_configs(
        _bearer(authorization), page, page_size, _audit_context(request)
    )


@router.get(
    "/api/v1/model-config-review",
    response_model=ModelConfigListData,
    response_model_exclude_none=True,
    operation_id="list_model_config_reviews",
)
def list_model_config_reviews(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> ModelConfigListData:
    return _service(request).list_model_config_reviews(
        _bearer(authorization), page, page_size, _audit_context(request)
    )


@router.post(
    "/api/v1/model-config",
    status_code=201,
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="create_model_config",
)
def create_model_config(
    body: CreateModelConfigRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    data = _service(request).create_model_config(
        _bearer(authorization), body, idempotency_key, _audit_context(request)
    )
    return ModelConfigResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/model-config/{id}",
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="get_model_config",
)
def get_model_config(
    id: ModelId,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    data = _service(request).get_model_config(
        _bearer(authorization), id, _audit_context(request)
    )
    return ModelConfigResponse(data=data, correlation_id=_correlation_id(request))


@router.get(
    "/api/v1/model-config-review/{id}",
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="get_model_config_review",
)
def get_model_config_review(
    id: ModelId,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    data = _service(request).get_model_config_review(
        _bearer(authorization), id, _audit_context(request)
    )
    return ModelConfigResponse(data=data, correlation_id=_correlation_id(request))


@router.patch(
    "/api/v1/model-config/{id}",
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="update_model_config",
)
def update_model_config(
    id: ModelId,
    body: UpdateModelConfigRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    data = _service(request).update_model_config(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return ModelConfigResponse(data=data, correlation_id=_correlation_id(request))


def _transition(
    *,
    id: str,
    body: ModelConfigLifecycleRequest,
    request: Request,
    idempotency_key: str,
    authorization: str | None,
    action: str,
) -> ModelConfigResponse:
    data = _service(request).transition_model_config(
        _bearer(authorization),
        id,
        body,
        idempotency_key,
        _audit_context(request),
        action=action,
    )
    return ModelConfigResponse(data=data, correlation_id=_correlation_id(request))


@router.post(
    "/api/v1/model-config/{id}/submit-review",
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="submit_model_config_review",
)
def submit_model_config_review(
    id: ModelId,
    body: ModelConfigLifecycleRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    return _transition(
        id=id,
        body=body,
        request=request,
        idempotency_key=idempotency_key,
        authorization=authorization,
        action="submit_review",
    )


@router.post(
    "/api/v1/model-config/{id}/return-to-configuring",
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="return_model_config_to_configuring",
)
def return_model_config_to_configuring(
    id: ModelId,
    body: ModelConfigLifecycleRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    return _transition(
        id=id,
        body=body,
        request=request,
        idempotency_key=idempotency_key,
        authorization=authorization,
        action="return_to_configuring",
    )


@router.post(
    "/api/v1/model-config/{id}/activate",
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="activate_model_config",
)
def activate_model_config(
    id: ModelId,
    body: ModelConfigLifecycleRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    return _transition(
        id=id,
        body=body,
        request=request,
        idempotency_key=idempotency_key,
        authorization=authorization,
        action="activate",
    )


@router.post(
    "/api/v1/model-config/{id}/disable",
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="disable_model_config",
)
def disable_model_config(
    id: ModelId,
    body: ModelConfigLifecycleRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    return _transition(
        id=id,
        body=body,
        request=request,
        idempotency_key=idempotency_key,
        authorization=authorization,
        action="disable",
    )


@router.post(
    "/api/v1/model-config/{id}/recover",
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="recover_model_config",
)
def recover_model_config(
    id: ModelId,
    body: ModelConfigLifecycleRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    return _transition(
        id=id,
        body=body,
        request=request,
        idempotency_key=idempotency_key,
        authorization=authorization,
        action="recover",
    )


@router.post(
    "/api/v1/model-config/{id}/archive",
    response_model=ModelConfigResponse,
    response_model_exclude_none=True,
    operation_id="archive_model_config",
)
def archive_model_config(
    id: ModelId,
    body: ModelConfigLifecycleRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ModelConfigResponse:
    return _transition(
        id=id,
        body=body,
        request=request,
        idempotency_key=idempotency_key,
        authorization=authorization,
        action="archive",
    )


@router.post(
    "/api/v1/model-config/{id}/connection-test",
    response_model=TestModelConfigConnectionResponse,
    response_model_exclude_none=True,
    operation_id="test_model_config_connection",
)
def test_model_config_connection(
    id: ModelId,
    body: TestModelConfigConnectionRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> TestModelConfigConnectionResponse:
    data = _service(request).test_connection(
        _bearer(authorization), id, body, idempotency_key, _audit_context(request)
    )
    return TestModelConfigConnectionResponse(
        data=data, correlation_id=_correlation_id(request)
    )


@router.put(
    "/api/v1/model-capability-default/{capability_code}",
    response_model=SetCapabilityDefaultModelResponse,
    response_model_exclude_none=True,
    operation_id="set_capability_default_model",
)
def set_capability_default_model(
    capability_code: Annotated[str, Path(min_length=1, max_length=64)],
    body: SetCapabilityDefaultModelRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> SetCapabilityDefaultModelResponse:
    data = _service(request).set_capability_default(
        _bearer(authorization),
        capability_code,
        body,
        idempotency_key,
        _audit_context(request),
    )
    return SetCapabilityDefaultModelResponse(
        data=data, correlation_id=_correlation_id(request)
    )


@router.post(
    "/api/v1/model-capability-default/{capability_code}/clear",
    response_model=ClearCapabilityDefaultModelResponse,
    response_model_exclude_none=True,
    operation_id="clear_capability_default_model",
)
def clear_capability_default_model(
    capability_code: Annotated[str, Path(min_length=1, max_length=64)],
    body: ClearCapabilityDefaultModelRequest,
    request: Request,
    idempotency_key: str = Header(min_length=1, max_length=191, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> ClearCapabilityDefaultModelResponse:
    data = _service(request).clear_capability_default(
        _bearer(authorization),
        capability_code,
        body,
        idempotency_key,
        _audit_context(request),
    )
    return ClearCapabilityDefaultModelResponse(
        data=data, correlation_id=_correlation_id(request)
    )
