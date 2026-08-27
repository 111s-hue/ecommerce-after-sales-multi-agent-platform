from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.api.after_sales_schemas import (
    CompleteFulfillmentRequest,
    CreateAfterSaleRequest,
    ReturnInspectionRequest,
    ReturnShipmentRequest,
    ReviewAfterSaleRequest,
)
from app.services.after_sales import (
    AfterSalesError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.services.auth import Identity, current_identity, require_permission

router = APIRouter(prefix="/after-sale-cases", tags=["after-sales"])


def _raise_api_error(exc: AfterSalesError) -> None:
    if isinstance(exc, NotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ConflictError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(exc, ValidationError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CreateAfterSaleRequest,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "after_sale.write")
    customer_id = identity.user_id if identity.role == "customer" else payload.customer_id
    try:
        return request.app.state.after_sales_service.create_case(
            tenant_id=identity.tenant_id,
            actor_id=identity.user_id,
            actor_role=identity.role,
            order_id=payload.order_id,
            customer_id=customer_id,
            case_type=payload.case_type,
            reason_code=payload.reason_code,
            reason=payload.reason,
            requested_amount=payload.requested_amount,
            priority=payload.priority,
            idempotency_key=idempotency_key,
        )
    except AfterSalesError as exc:
        _raise_api_error(exc)


@router.get("")
def list_cases(
    request: Request,
    customer_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    case_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "after_sale.read")
    trusted_customer = identity.user_id if identity.role == "customer" else customer_id
    return request.app.state.after_sales_service.list_cases(
        tenant_id=identity.tenant_id,
        customer_id=trusted_customer,
        status=status_filter,
        case_type=case_type,
        limit=limit,
        offset=offset,
    )


@router.get("/{case_id}")
def get_case(
    case_id: str,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "after_sale.read")
    try:
        return request.app.state.after_sales_service.get_case(
            tenant_id=identity.tenant_id,
            case_id=case_id,
            customer_id=identity.user_id if identity.role == "customer" else None,
        )
    except AfterSalesError as exc:
        _raise_api_error(exc)


@router.post("/{case_id}/review")
def review_case(
    case_id: str,
    payload: ReviewAfterSaleRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "approval.decide")
    try:
        return request.app.state.after_sales_service.review_case(
            tenant_id=identity.tenant_id,
            case_id=case_id,
            actor_id=identity.user_id,
            approved=payload.approved,
            approved_amount=payload.approved_amount,
            reason=payload.reason,
        )
    except AfterSalesError as exc:
        _raise_api_error(exc)


@router.post("/{case_id}/return-shipment")
def ship_return(
    case_id: str,
    payload: ReturnShipmentRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "after_sale.write")
    try:
        return request.app.state.after_sales_service.ship_return(
            tenant_id=identity.tenant_id,
            case_id=case_id,
            actor_id=identity.user_id,
            customer_id=identity.user_id if identity.role == "customer" else None,
            carrier=payload.carrier,
            tracking_no=payload.tracking_no,
        )
    except AfterSalesError as exc:
        _raise_api_error(exc)


@router.post("/{case_id}/return-inspection")
def inspect_return(
    case_id: str,
    payload: ReturnInspectionRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "after_sale.write")
    if identity.role == "customer":
        raise HTTPException(status_code=403, detail="客户账号不能执行入库验收")
    try:
        return request.app.state.after_sales_service.inspect_return(
            tenant_id=identity.tenant_id,
            case_id=case_id,
            actor_id=identity.user_id,
            accepted=payload.accepted,
            notes=payload.notes,
            deduction_amount=payload.deduction_amount,
        )
    except AfterSalesError as exc:
        _raise_api_error(exc)


@router.post("/{case_id}/refunds/{refund_id}/execute")
def execute_refund(
    case_id: str,
    refund_id: str,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "refund.execute")
    try:
        return request.app.state.after_sales_service.execute_refund(
            tenant_id=identity.tenant_id,
            case_id=case_id,
            refund_id=refund_id,
            actor_id=identity.user_id,
        )
    except AfterSalesError as exc:
        _raise_api_error(exc)


@router.post("/{case_id}/complete")
def complete_fulfillment(
    case_id: str,
    payload: CompleteFulfillmentRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_permission(identity, "after_sale.write")
    if identity.role == "customer":
        raise HTTPException(status_code=403, detail="客户账号不能完成内部履约")
    try:
        return request.app.state.after_sales_service.complete_fulfillment(
            tenant_id=identity.tenant_id,
            case_id=case_id,
            actor_id=identity.user_id,
            notes=payload.notes,
        )
    except AfterSalesError as exc:
        _raise_api_error(exc)
