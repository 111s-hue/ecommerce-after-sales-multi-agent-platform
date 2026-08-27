from __future__ import annotations

import json
import re
from collections.abc import Callable, Generator
from datetime import datetime
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.config import Settings
from app.domain.repositories import SupportRepository
from app.graph.state import SupportState
from app.services.agent_runtime import ToolCallingRuntime, commerce_tool_specs
from app.services.llm import OpenAICompatibleLLM, SupervisorDecision
from app.services.rag import PolicyKnowledgeBase
from app.services.security import detect_prompt_injection

ORDER_PATTERN = re.compile(r"ORD-\d{4,}", re.IGNORECASE)


def _trace(state: SupportState, node: str, message: str) -> list[dict[str, str]]:
    return [
        *state.get("trace", []),
        {"node": node, "message": message, "at": datetime.now().isoformat(timespec="seconds")},
    ]


def _extract_order_id(query: str) -> str | None:
    match = ORDER_PATTERN.search(query)
    return match.group(0).upper() if match else None


def _specialist_subgraph(name: str, node: Callable[[SupportState], dict[str, Any]]) -> Any:
    graph = StateGraph(SupportState)
    graph.add_node(name, node)
    graph.add_edge(START, name)
    graph.add_edge(name, END)
    return graph.compile()


class AfterSalesGraph:
    def __init__(
        self,
        tools: Any,
        knowledge_base: PolicyKnowledgeBase,
        checkpointer: Any,
        *,
        llm: OpenAICompatibleLLM | None = None,
        repository: SupportRepository | None = None,
    ):
        self.tools = tools
        self.repository = repository or getattr(tools, "repository", None)
        self.knowledge_base = knowledge_base
        self.llm = llm or OpenAICompatibleLLM(Settings(llm_enabled=False))
        self.runtime = ToolCallingRuntime(self.llm, self.llm.settings.max_agent_steps)
        self.graph = self._build(checkpointer)

    @staticmethod
    def _heuristic_decision(query: str) -> SupervisorDecision:
        order_id = _extract_order_id(query)
        if any(word in query for word in ("退款", "退货", "换货", "售后")):
            intent = "refund" if order_id else "policy"
        elif any(word in query for word in ("物流", "快递", "到哪", "配送", "签收")):
            intent = "logistics"
        elif any(word in query for word in ("政策", "规则", "时效", "运费", "条件")):
            intent = "policy"
        elif any(word in query for word in ("订单", "支付", "商品", "状态")):
            intent = "order"
        else:
            intent = "fallback"
        return SupervisorDecision(
            intent=intent,
            order_id=order_id,
            risk_level="medium" if intent == "refund" else "low",
            missing_fields=["order_id"]
            if intent in {"order", "logistics"} and not order_id
            else [],
            reason="deterministic fallback router",
        )

    def _supervisor(self, state: SupportState) -> dict[str, Any]:
        query = state["query"]
        target_agent = state.get("target_agent", "auto")
        if detect_prompt_injection(query):
            decision = SupervisorDecision(
                intent="safety",
                order_id=_extract_order_id(query),
                risk_level="high",
                reason="prompt injection guard",
            )
            source = "security_guard"
        elif target_agent != "auto":
            decision = SupervisorDecision(
                intent=target_agent,
                order_id=_extract_order_id(query),
                risk_level="medium" if target_agent == "refund" else "low",
                missing_fields=["order_id"]
                if target_agent in {"order", "logistics", "refund"}
                and not _extract_order_id(query)
                else [],
                reason="operator selected specialist agent",
            )
            source = "operator_selected"
        elif self.llm.settings.llm_enabled:
            try:
                decision = self.llm.route(query)
                source = "qwen_structured_output"
            except Exception as exc:
                decision = self._heuristic_decision(query)
                source = f"fallback_after_llm_error:{type(exc).__name__}"
        else:
            decision = self._heuristic_decision(query)
            source = "deterministic_offline"
        return {
            "intent": decision.intent,
            "route": decision.intent,
            "order_id": decision.order_id or _extract_order_id(query),
            "tool_results": {
                **state.get("tool_results", {}),
                "supervisor_decision": decision.model_dump(),
            },
            "trace": _trace(
                state,
                "supervisor",
                f"route={decision.intent}; risk={decision.risk_level}; source={source}",
            ),
        }

    @staticmethod
    def _route(state: SupportState) -> str:
        return state.get("route", "fallback")

    def _run_tool_agent(
        self,
        state: SupportState,
        *,
        allowed: set[str],
        fallback_calls: list[tuple[str, dict[str, Any]]],
        system: str,
    ) -> tuple[dict[str, Any], str]:
        trusted = fallback_calls[0][1] if fallback_calls else {}

        def secure_executor(name: str):
            function = getattr(self.tools, name)

            def execute(**arguments):
                # Identity and resource scope come from trusted graph state, never model output.
                for field in ("user_id", "thread_id", "order_id"):
                    if field in trusted:
                        arguments[field] = trusted[field]
                if "reason" in trusted:
                    arguments["reason"] = trusted["reason"]
                return function(**arguments)

            return execute

        executors = {name: secure_executor(name) for name in allowed}
        run = self.runtime.run(
            system=system,
            query=state["query"],
            tool_specs=commerce_tool_specs(allowed),
            executors=executors,
            fallback_calls=fallback_calls,
        )
        if not run.calls:
            return {}, run.answer
        last = run.calls[-1]["result"]
        if "error" in last:
            raise RuntimeError(last["error"])
        return {"agent_calls": run.calls, "result": last}, run.answer

    def _order_agent(self, state: SupportState) -> dict[str, Any]:
        order_id = state.get("order_id")
        if not order_id:
            return {
                "response": "请提供订单号，例如 ORD-1001，我会继续为你查询。",
                "trace": _trace(state, "order_agent", "missing order_id"),
            }
        arguments = {
            "order_id": order_id,
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
        }
        try:
            agent, model_answer = self._run_tool_agent(
                state,
                allowed={"get_order"},
                fallback_calls=[("get_order", arguments)],
                system="你是订单 Agent。必须调用 get_order，不能猜测订单数据。",
            )
            order = agent["result"]
            fallback = (
                f"订单 {order_id}：{order['product_name']}，金额 ¥{order['amount']:.2f}，"
                f"当前状态为 {order['status']}。"
            )
            return {
                "tool_results": {**state.get("tool_results", {}), "order": order, **agent},
                "response": model_answer or fallback,
                "trace": _trace(state, "order_agent", "tool calling completed: get_order"),
            }
        except (PermissionError, RuntimeError) as exc:
            return self._tool_error(state, "order_agent", exc)

    def _logistics_agent(self, state: SupportState) -> dict[str, Any]:
        order_id = state.get("order_id")
        if not order_id:
            return {
                "response": "请提供需要查询物流的订单号，例如 ORD-1002。",
                "trace": _trace(state, "logistics_agent", "missing order_id"),
            }
        arguments = {
            "order_id": order_id,
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
        }
        try:
            agent, model_answer = self._run_tool_agent(
                state,
                allowed={"get_logistics"},
                fallback_calls=[("get_logistics", arguments)],
                system="你是物流 Agent。必须调用 get_logistics，不能承诺未确认的物流结果。",
            )
            logistics = agent["result"]
            fallback = (
                f"订单 {order_id} 由{logistics['carrier']}承运，当前状态："
                f"{logistics['status']}；最新进展：{logistics['latest_event']}。"
            )
            return {
                "tool_results": {
                    **state.get("tool_results", {}),
                    "logistics": logistics,
                    **agent,
                },
                "response": model_answer or fallback,
                "trace": _trace(state, "logistics_agent", "tool calling completed: get_logistics"),
            }
        except (PermissionError, RuntimeError) as exc:
            return self._tool_error(state, "logistics_agent", exc)

    @staticmethod
    def _tool_error(state: SupportState, node: str, exc: Exception) -> dict[str, Any]:
        return {
            "error": str(exc),
            "response": str(exc),
            "trace": _trace(state, node, f"tool error: {type(exc).__name__}"),
        }

    def _policy_agent(self, state: SupportState) -> dict[str, Any]:
        evidence = self.knowledge_base.search(state["query"], top_k=4)
        evidence_dicts = [item.model_dump() for item in evidence]
        level = "high" if evidence and evidence[0].score >= 0.15 else "low"
        if not evidence:
            fallback = "当前知识库没有找到足够证据，已建议转人工客服核验。"
        else:
            top = evidence[0]
            fallback = f"根据《{top.section}》：{top.content} 引用：{top.source}#{top.section}。"
            if level == "low":
                fallback += " 当前证据置信度较低，建议由人工客服复核。"
        response = self.llm.synthesize(
            query=state["query"], context={"evidence": evidence_dicts}, fallback=fallback
        )
        return {
            "evidence": evidence_dicts,
            "evidence_level": level,
            "response": response,
            "trace": _trace(state, "policy_agent", f"retrieved {len(evidence)} policy chunks"),
        }

    def _refund_agent(self, state: SupportState) -> dict[str, Any]:
        order_id = state.get("order_id")
        if not order_id:
            return {
                "response": "请先提供要申请售后的订单号，例如 ORD-1001。",
                "pending_action": None,
                "trace": _trace(state, "refund_agent", "missing order_id"),
            }
        arguments = {
            "order_id": order_id,
            "user_id": state["user_id"],
            "thread_id": state["thread_id"],
            "reason": state["query"],
        }
        try:
            agent, _ = self._run_tool_agent(
                state,
                allowed={"check_refund_eligibility"},
                fallback_calls=[("check_refund_eligibility", arguments)],
                system=(
                    "你是退款风控 Agent。必须调用 check_refund_eligibility。"
                    "只判断资格，不得直接创建工单或承诺退款。"
                ),
            )
            eligibility = agent["result"]
        except (PermissionError, RuntimeError) as exc:
            error = self._tool_error(state, "refund_agent", exc)
            return {**error, "pending_action": None}
        tool_results = {
            **state.get("tool_results", {}),
            "refund_eligibility": eligibility,
            "agent_calls": agent["agent_calls"],
        }
        if not eligibility["eligible"]:
            return {
                "tool_results": tool_results,
                "response": f"暂不符合自动退款条件：{eligibility['reason']}。可转人工复核。",
                "pending_action": None,
                "trace": _trace(state, "refund_agent", "refund risk check rejected"),
            }
        pending = {
            "type": "create_after_sale",
            "order_id": order_id,
            "reason": state["query"],
            "refundable_amount": eligibility["refundable_amount"],
            "policy_reference": eligibility["policy_reference"],
        }
        return {
            "tool_results": tool_results,
            "pending_action": pending,
            "response": "退款资格校验通过，等待人工审批后创建售后工单。",
            "trace": _trace(state, "refund_agent", "risk check passed; approval required"),
        }

    @staticmethod
    def _after_refund(state: SupportState) -> str:
        return "approval" if state.get("pending_action") else "final"

    def _approval(self, state: SupportState) -> dict[str, Any]:
        action = state.get("pending_action") or {}
        if self.repository:
            self.repository.upsert_approval(
                thread_id=state["thread_id"],
                user_id=state["user_id"],
                order_id=str(action.get("order_id", "unknown")),
                action=str(action.get("type", "unknown")),
                amount=float(action.get("refundable_amount", 0)),
                payload_json=json.dumps(action, ensure_ascii=False),
            )
        decision = interrupt(
            {
                "type": "refund_approval",
                "thread_id": state["thread_id"],
                "user_id": state["user_id"],
                "action": action,
                "message": "请人工核验退款资格、金额和用户身份。",
            }
        )
        approved = bool(decision.get("approved"))
        reviewer = str(decision.get("reviewer") or "unknown")
        reason = str(decision.get("reason") or "")
        if self.repository:
            self.repository.decide_approval(
                thread_id=state["thread_id"],
                approved=approved,
                reviewer=reviewer,
                reason=reason,
            )
            self.repository.add_audit(
                thread_id=state["thread_id"],
                user_id=state["user_id"],
                action="refund_approval",
                resource=state.get("order_id") or "unknown",
                outcome="approved" if approved else "rejected",
                detail=f"reviewer={reviewer}; reason={reason}",
            )
        if not approved:
            return {
                "approved": False,
                "reviewer": reviewer,
                "pending_action": None,
                "response": f"退款申请未获批准。审批意见：{reason or '未填写'}。",
                "trace": _trace(state, "approval", f"rejected by {reviewer}"),
            }
        return {
            "approved": True,
            "reviewer": reviewer,
            "trace": _trace(state, "approval", f"approved by {reviewer}"),
        }

    @staticmethod
    def _after_approval(state: SupportState) -> str:
        return "execute" if state.get("approved") else "final"

    def _execute_refund(self, state: SupportState) -> dict[str, Any]:
        action = state["pending_action"]
        idempotency_key = f"refund:{state['thread_id']}:{action['order_id']}"
        ticket = self.tools.create_after_sale(
            order_id=action["order_id"],
            user_id=state["user_id"],
            thread_id=state["thread_id"],
            reason=action["reason"],
            refundable_amount=action["refundable_amount"],
            approved=True,
            reviewer=state["reviewer"],
            idempotency_key=idempotency_key,
        )
        return {
            "tool_results": {**state.get("tool_results", {}), "after_sale_ticket": ticket},
            "pending_action": None,
            "response": (
                f"审批已通过，售后工单 {ticket['ticket_id']} 创建成功，"
                f"预计退款金额 ¥{ticket['refundable_amount']:.2f}。"
            ),
            "trace": _trace(state, "execute_refund", "idempotent write completed"),
        }

    def _safety(self, state: SupportState) -> dict[str, Any]:
        if self.repository:
            self.repository.add_audit(
                thread_id=state["thread_id"],
                user_id=state["user_id"],
                action="prompt_injection_guard",
                resource=state.get("order_id") or "conversation",
                outcome="blocked",
                detail="request stopped before tool execution",
            )
        return {
            "response": "检测到可能的提示注入或越权指令。本次请求已停止，可改为描述具体订单问题。",
            "error": "prompt_injection_blocked",
            "trace": _trace(state, "safety", "request blocked before tool execution"),
        }

    @staticmethod
    def _fallback(state: SupportState) -> dict[str, Any]:
        return {
            "response": "我可以协助查询订单、物流、退换货政策或发起售后。请描述问题并提供订单号。",
            "trace": _trace(state, "fallback", "no supported intent found"),
        }

    def _final(self, state: SupportState) -> dict[str, Any]:
        response = state.get("response", "")
        if not state.get("error") and state.get("intent") not in {"policy", "fallback"}:
            response = self.llm.synthesize(
                query=state["query"],
                context={
                    "tool_results": state.get("tool_results", {}),
                    "evidence": state.get("evidence", []),
                },
                fallback=response,
            )
        return {"response": response, "trace": _trace(state, "final", "answer finalized")}

    def _build(self, checkpointer: Any) -> Any:
        graph = StateGraph(SupportState)
        graph.add_node("supervisor", self._supervisor)
        graph.add_node("order", _specialist_subgraph("order_agent", self._order_agent))
        graph.add_node("logistics", _specialist_subgraph("logistics_agent", self._logistics_agent))
        graph.add_node("policy", _specialist_subgraph("policy_agent", self._policy_agent))
        graph.add_node("refund", _specialist_subgraph("refund_agent", self._refund_agent))
        graph.add_node("safety", self._safety)
        graph.add_node("fallback", self._fallback)
        graph.add_node("approval", self._approval)
        graph.add_node("execute", self._execute_refund)
        graph.add_node("final", self._final)
        graph.add_edge(START, "supervisor")
        graph.add_conditional_edges(
            "supervisor",
            self._route,
            {
                name: name
                for name in ("order", "logistics", "policy", "refund", "safety", "fallback")
            },
        )
        for name in ("order", "logistics", "policy", "safety", "fallback"):
            graph.add_edge(name, "final")
        graph.add_conditional_edges(
            "refund", self._after_refund, {"approval": "approval", "final": "final"}
        )
        graph.add_conditional_edges(
            "approval", self._after_approval, {"execute": "execute", "final": "final"}
        )
        graph.add_edge("execute", "final")
        graph.add_edge("final", END)
        return graph.compile(checkpointer=checkpointer)

    @staticmethod
    def _serialize_interrupts(result: dict[str, Any]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for item in result.get("__interrupt__", ()):
            value = getattr(item, "value", item)
            serialized.append(value if isinstance(value, dict) else {"value": str(value)})
        return serialized

    def _start_run(self, thread_id: str, user_id: str, query: str) -> None:
        if not self.repository:
            return
        self.repository.upsert_conversation(
            thread_id=thread_id,
            user_id=user_id,
            title=query[:80],
            status="running",
            intent=None,
        )
        self.repository.add_message(thread_id=thread_id, role="user", content=query)

    def _persist_result(self, result: dict[str, Any]) -> None:
        if not self.repository:
            return
        self.repository.upsert_conversation(
            thread_id=result["thread_id"],
            user_id=result.get("user_id", "unknown"),
            title=result.get("query", "售后会话")[:80],
            status=result["status"],
            intent=result.get("intent"),
        )
        self.repository.add_message(
            thread_id=result["thread_id"],
            role="assistant",
            content=result.get("response", ""),
            metadata_json=json.dumps(
                {"status": result["status"], "intent": result.get("intent")},
                ensure_ascii=False,
            ),
        )

    def invoke(
        self, *, thread_id: str, user_id: str, query: str, target_agent: str = "auto"
    ) -> dict[str, Any]:
        self._start_run(thread_id, user_id, query)
        config = {"configurable": {"thread_id": thread_id}}
        result = self.graph.invoke(
            {
                "thread_id": thread_id,
                "user_id": user_id,
                "query": query,
                "target_agent": target_agent,
                "trace": [],
                "tool_results": {},
                "evidence": [],
            },
            config=config,
        )
        payload = self._result_payload(thread_id, result)
        self._persist_result(payload)
        return payload

    def stream(
        self, *, thread_id: str, user_id: str, query: str, target_agent: str = "auto"
    ) -> Generator[dict[str, Any], None, None]:
        self._start_run(thread_id, user_id, query)
        config = {"configurable": {"thread_id": thread_id}}
        state: dict[str, Any] = {
            "thread_id": thread_id,
            "user_id": user_id,
            "query": query,
            "target_agent": target_agent,
            "trace": [],
            "tool_results": {},
            "evidence": [],
        }
        interrupts: list[dict[str, Any]] = []
        yield {"event": "accepted", "data": {"thread_id": thread_id}}
        for update in self.graph.stream(state, config=config, stream_mode="updates"):
            if "__interrupt__" in update:
                serialized = self._serialize_interrupts(update)
                interrupts.extend(serialized)
                yield {"event": "interrupt", "data": {"interrupts": serialized}}
                continue
            for node, values in update.items():
                if isinstance(values, dict):
                    state.update(values)
                yield {
                    "event": "node",
                    "data": {
                        "node": node,
                        "response": values.get("response") if isinstance(values, dict) else None,
                        "trace": values.get("trace", [])[-1:] if isinstance(values, dict) else [],
                    },
                }
        if interrupts:
            state["__interrupt__"] = tuple(interrupts)
        payload = self._result_payload(thread_id, state)
        self._persist_result(payload)
        yield {"event": "result", "data": payload}

    def resume(
        self, *, thread_id: str, approved: bool, reviewer: str, reason: str = ""
    ) -> dict[str, Any]:
        config = {"configurable": {"thread_id": thread_id}}
        result = self.graph.invoke(
            Command(resume={"approved": approved, "reviewer": reviewer, "reason": reason}),
            config=config,
        )
        payload = self._result_payload(thread_id, result)
        self._persist_result(payload)
        return payload

    def _result_payload(self, thread_id: str, result: dict[str, Any]) -> dict[str, Any]:
        interrupts = self._serialize_interrupts(result)
        return {
            "status": "pending_approval" if interrupts else "completed",
            "thread_id": thread_id,
            "user_id": result.get("user_id"),
            "query": result.get("query", ""),
            "intent": result.get("intent"),
            "response": result.get("response", ""),
            "tool_results": result.get("tool_results", {}),
            "evidence": result.get("evidence", []),
            "evidence_level": result.get("evidence_level"),
            "trace": result.get("trace", []),
            "interrupts": interrupts,
            "error": result.get("error"),
        }
