from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.llm import OpenAICompatibleLLM


@dataclass
class AgentRun:
    answer: str
    calls: list[dict[str, Any]]


class ToolCallingRuntime:
    """Bounded ReAct-style loop for Qwen OpenAI-compatible tool calling."""

    def __init__(self, llm: OpenAICompatibleLLM, max_steps: int = 3):
        self.llm = llm
        self.max_steps = max_steps

    def run(
        self,
        *,
        system: str,
        query: str,
        tool_specs: list[dict[str, Any]],
        executors: dict[str, Callable[..., dict[str, Any]]],
        fallback_calls: list[tuple[str, dict[str, Any]]],
    ) -> AgentRun:
        if not self.llm.settings.llm_enabled:
            calls = self._execute(fallback_calls, executors)
            return AgentRun(answer="", calls=calls)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ]
        executed: list[dict[str, Any]] = []
        for _ in range(self.max_steps):
            message = self.llm.chat(messages, tools=tool_specs)
            tool_calls = self.llm.parse_tool_calls(message)
            messages.append(message)
            if not tool_calls:
                return AgentRun(answer=str(message.get("content") or ""), calls=executed)
            for call in tool_calls:
                if call.name not in executors:
                    result: dict[str, Any] = {"error": f"tool_not_allowed: {call.name}"}
                else:
                    try:
                        result = executors[call.name](**call.arguments)
                    except Exception as exc:  # tool errors are returned to the model for correction
                        result = {"error": str(exc)}
                executed.append({"name": call.name, "arguments": call.arguments, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
        final = self.llm.chat(messages)
        return AgentRun(answer=str(final.get("content") or ""), calls=executed)

    @staticmethod
    def _execute(
        plan: list[tuple[str, dict[str, Any]]],
        executors: dict[str, Callable[..., dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for name, arguments in plan:
            result = executors[name](**arguments)
            calls.append({"name": name, "arguments": arguments, "result": result})
        return calls


def commerce_tool_specs(allowed: set[str]) -> list[dict[str, Any]]:
    definitions = {
        "get_order": {
            "description": "查询当前用户本人的订单详情",
            "properties": {
                "order_id": {"type": "string"},
                "user_id": {"type": "string"},
                "thread_id": {"type": "string"},
            },
            "required": ["order_id", "user_id", "thread_id"],
        },
        "get_logistics": {
            "description": "查询当前用户本人的物流轨迹",
            "properties": {
                "order_id": {"type": "string"},
                "user_id": {"type": "string"},
                "thread_id": {"type": "string"},
            },
            "required": ["order_id", "user_id", "thread_id"],
        },
        "check_refund_eligibility": {
            "description": "根据订单状态、签收时间和政策判断退款资格",
            "properties": {
                "order_id": {"type": "string"},
                "user_id": {"type": "string"},
                "thread_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["order_id", "user_id", "thread_id", "reason"],
        },
    }
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": definition["description"],
                "parameters": {
                    "type": "object",
                    "properties": definition["properties"],
                    "required": definition["required"],
                    "additionalProperties": False,
                },
            },
        }
        for name, definition in definitions.items()
        if name in allowed
    ]
