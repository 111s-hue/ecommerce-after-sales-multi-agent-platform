from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatRequest(StrictRequest):
    user_id: str = Field(min_length=2, max_length=32)
    query: str = Field(min_length=1, max_length=2000)
    thread_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=64)
    target_agent: Literal["auto", "order", "logistics", "policy", "refund"] = "auto"


class ApprovalRequest(StrictRequest):
    approved: bool
    reviewer: str = Field(min_length=2, max_length=64)
    reason: str = Field(default="", max_length=500)


class ChatResponse(BaseModel):
    status: Literal["completed", "pending_approval"]
    thread_id: str
    intent: str | None = None
    response: str
    tool_results: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    evidence_level: str | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)
    interrupts: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class LoginRequest(StrictRequest):
    tenant_code: str = Field(
        default="community", min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$"
    )
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    role: str
    user_id: str
    tenant_id: str
    display_name: str
    permissions: list[str]
