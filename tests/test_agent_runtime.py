from app.config import Settings
from app.services.agent_runtime import ToolCallingRuntime, commerce_tool_specs
from app.services.llm import OpenAICompatibleLLM


class FakeToolCallingLLM(OpenAICompatibleLLM):
    def __init__(self):
        super().__init__(Settings(llm_enabled=True, max_agent_steps=2))
        self.turn = 0

    def chat(self, messages, *, tools=None, response_format=None):
        self.turn += 1
        if self.turn == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "get_order",
                            "arguments": {
                                "order_id": "ORD-1001",
                                "user_id": "ATTACKER",
                                "thread_id": "t1",
                            },
                        },
                    }
                ],
            }
        return {"role": "assistant", "content": "订单查询完成"}


def test_tool_calling_runtime_executes_model_selected_tool() -> None:
    runtime = ToolCallingRuntime(FakeToolCallingLLM(), max_steps=2)
    run = runtime.run(
        system="test",
        query="query order",
        tool_specs=commerce_tool_specs({"get_order"}),
        executors={"get_order": lambda **kwargs: {"order_id": kwargs["order_id"]}},
        fallback_calls=[],
    )

    assert run.answer == "订单查询完成"
    assert run.calls[0]["name"] == "get_order"
    assert run.calls[0]["result"]["order_id"] == "ORD-1001"
