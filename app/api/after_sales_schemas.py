from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.api.schemas import StrictRequest

CaseType = Literal[
    "refund_only",
    "return_refund",
    "exchange",
    "reshipment",
    "repair",
    "compensation",
    "appeal",
]


class CreateAfterSaleRequest(StrictRequest):
    order_id: str = Field(min_length=2, max_length=32)
    customer_id: str = Field(min_length=2, max_length=36)
    case_type: CaseType
    reason_code: str | None = Field(default=None, max_length=64)
    reason: str = Field(min_length=2, max_length=2000)
    requested_amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class ReviewAfterSaleRequest(StrictRequest):
    approved: bool
    approved_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    reason: str = Field(default="", max_length=500)


class ReturnShipmentRequest(StrictRequest):
    carrier: str = Field(min_length=2, max_length=64)
    tracking_no: str = Field(min_length=4, max_length=128)


class ReturnInspectionRequest(StrictRequest):
    accepted: bool
    notes: str = Field(default="", max_length=2000)
    deduction_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)


class CompleteFulfillmentRequest(StrictRequest):
    notes: str = Field(default="", max_length=500)
