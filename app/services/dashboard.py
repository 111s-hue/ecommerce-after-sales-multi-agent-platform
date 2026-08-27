from __future__ import annotations

from typing import Any

from app.domain.repositories import SupportRepository


class DashboardService:
    """Builds operational read models without leaking persistence details into routes."""

    def __init__(self, repository: SupportRepository):
        self.repository = repository

    def summary(self) -> dict[str, Any]:
        conversations = self.repository.list_conversations(limit=500)
        approvals = self.repository.list_approvals(limit=500)
        audits = self.repository.list_audits(limit=500)
        tickets = self.repository.list_after_sales(limit=500)
        completed = sum(item.status == "completed" for item in conversations)
        automated = max(completed - len(tickets), 0)
        return {
            "conversations": len(conversations),
            "pending_approvals": sum(item.status == "pending" for item in approvals),
            "completed_conversations": completed,
            "after_sales": len(tickets),
            "refund_amount": round(sum(item.refundable_amount for item in tickets), 2),
            "tool_calls": sum(
                item.action.startswith(("get_", "check_", "create_")) for item in audits
            ),
            "blocked_requests": sum(item.outcome == "blocked" for item in audits),
            "automation_rate": round(automated / completed * 100, 1) if completed else 0.0,
        }
