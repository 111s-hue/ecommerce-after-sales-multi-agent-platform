from typing import Any, Literal, TypedDict

Intent = Literal["order", "logistics", "policy", "refund", "safety", "fallback"]


class SupportState(TypedDict, total=False):
    thread_id: str
    user_id: str
    query: str
    target_agent: Literal["auto", "order", "logistics", "policy", "refund"]
    order_id: str | None
    intent: Intent
    route: str
    tool_results: dict[str, Any]
    evidence: list[dict[str, Any]]
    evidence_level: str
    pending_action: dict[str, Any] | None
    approved: bool
    reviewer: str
    response: str
    error: str
    trace: list[dict[str, str]]
