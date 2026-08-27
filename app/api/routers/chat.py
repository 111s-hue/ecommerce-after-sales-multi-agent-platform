import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from app.api.dependencies import enforce_customer_scope
from app.api.schemas import ChatRequest, ChatResponse
from app.services.auth import Identity, current_identity

router = APIRouter(tags=["agent-runtime"])


def _sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {data}\n\n"


def _trusted_user_id(request: Request, payload: ChatRequest, identity: Identity) -> str:
    value = enforce_customer_scope(request, identity, payload.user_id)
    if value is None:
        raise HTTPException(status_code=400, detail="缺少用户标识")
    return value


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    user_id = _trusted_user_id(request, payload, identity)
    return request.app.state.after_sales_graph.invoke(
        thread_id=payload.thread_id,
        user_id=user_id,
        query=payload.query,
        target_agent=payload.target_agent,
    )


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> StreamingResponse:
    user_id = _trusted_user_id(request, payload, identity)

    async def generate():
        stream = request.app.state.after_sales_graph.stream(
            thread_id=payload.thread_id,
            user_id=user_id,
            query=payload.query,
            target_agent=payload.target_agent,
        )
        async for item in iterate_in_threadpool(stream):
            if await request.is_disconnected():
                break
            yield _sse(item["event"], item["data"])

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
