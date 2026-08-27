import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.services.auth import Identity, current_identity, require_role
from app.services.dashboard import DashboardService

router = APIRouter(tags=["monitoring"])


@router.get("/system/info")
def system_info(request: Request, identity: Identity = Depends(current_identity)) -> dict[str, Any]:
    require_role(identity, "approver", "admin")
    settings = request.app.state.settings
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "llm": {"enabled": settings.llm_enabled, "model": settings.llm_model},
        "rag": {"backend": settings.rag_backend, "top_k": settings.rag_top_k},
        "tool_transport": settings.tool_transport,
        "auth_enabled": settings.auth_enabled,
    }


@router.get("/health/ready")
def readiness(request: Request) -> dict[str, Any]:
    try:
        database_ready = request.app.state.repository.healthcheck()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="数据库连接不可用") from exc
    return {"status": "ready", "checks": {"database": database_ready}}


@router.get("/metrics/summary")
def metric_summary(
    request: Request, identity: Identity = Depends(current_identity)
) -> dict[str, Any]:
    require_role(identity, "approver", "admin")
    return DashboardService(request.app.state.repository).summary()


@router.get("/metrics/evaluation")
def evaluation_report(
    request: Request, identity: Identity = Depends(current_identity)
) -> dict[str, Any]:
    require_role(identity, "admin")
    path = request.app.state.settings.evaluation_report_path
    if not path.exists():
        return {"status": "not_run", "message": "请先运行 python -m scripts.evaluate"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="评测报告暂时不可用") from exc
