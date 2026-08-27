from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class MCPCommerceTools:
    """Sync facade used by LangGraph nodes; calls the standalone MCP tool service."""

    def __init__(self, server_url: str, timeout_seconds: float = 20):
        self.server_url = server_url
        self.timeout = timedelta(seconds=timeout_seconds)

    async def _call_async(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with streamable_http_client(self.server_url) as (read_stream, write_stream, _):
            async with ClientSession(
                read_stream, write_stream, read_timeout_seconds=self.timeout
            ) as session:
                await session.initialize()
                result = await session.call_tool(
                    name, arguments=arguments, read_timeout_seconds=self.timeout
                )
        if result.isError:
            text = " ".join(
                str(getattr(item, "text", "")) for item in result.content if hasattr(item, "text")
            )
            raise RuntimeError(text or f"MCP tool failed: {name}")
        structured = result.structuredContent
        if structured:
            if set(structured) == {"result"} and isinstance(structured["result"], dict):
                return structured["result"]
            return structured
        for item in result.content:
            text = getattr(item, "text", None)
            if text:
                parsed = json.loads(text)
                return parsed if isinstance(parsed, dict) else {"result": parsed}
        return {}

    def _call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return asyncio.run(self._call_async(name, arguments))

    def get_order(self, order_id: str, user_id: str, thread_id: str) -> dict[str, Any]:
        return self._call(
            "get_order", {"order_id": order_id, "user_id": user_id, "thread_id": thread_id}
        )

    def get_logistics(self, order_id: str, user_id: str, thread_id: str) -> dict[str, Any]:
        return self._call(
            "get_logistics",
            {"order_id": order_id, "user_id": user_id, "thread_id": thread_id},
        )

    def check_refund_eligibility(
        self, order_id: str, user_id: str, thread_id: str, reason: str
    ) -> dict[str, Any]:
        return self._call(
            "check_refund_eligibility",
            {
                "order_id": order_id,
                "user_id": user_id,
                "thread_id": thread_id,
                "reason": reason,
            },
        )

    def create_after_sale(
        self,
        *,
        order_id: str,
        user_id: str,
        thread_id: str,
        reason: str,
        refundable_amount: float,
        approved: bool,
        reviewer: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._call(
            "create_after_sale",
            {
                "order_id": order_id,
                "user_id": user_id,
                "thread_id": thread_id,
                "reason": reason,
                "refundable_amount": refundable_amount,
                "approved": approved,
                "reviewer": reviewer,
                "idempotency_key": idempotency_key,
            },
        )
