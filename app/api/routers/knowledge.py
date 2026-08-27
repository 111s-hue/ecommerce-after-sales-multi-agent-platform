from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile

from app.services.auth import Identity, current_identity, require_role

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/documents")
def knowledge_documents(
    request: Request, identity: Identity = Depends(current_identity)
) -> list[dict[str, Any]]:
    require_role(identity, "approver", "admin")
    return request.app.state.knowledge_service.list_governed_documents(identity.tenant_id)


@router.post("/documents", status_code=201)
async def upload_knowledge_document(
    request: Request,
    file: UploadFile = File(...),
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_role(identity, "admin")
    content = await file.read(request.app.state.settings.max_knowledge_upload_bytes + 1)
    if len(content) > request.app.state.settings.max_knowledge_upload_bytes:
        raise HTTPException(status_code=413, detail="知识文档超过上传大小限制")
    try:
        document = request.app.state.knowledge_service.publish_markdown(
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            filename=file.filename or "policy.md",
            content=content,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    request.app.state.after_sales_graph.knowledge_base = (
        request.app.state.knowledge_service.knowledge_base
    )
    request.app.state.repository.add_audit(
        thread_id=f"knowledge-{document['name']}",
        user_id=identity.user_id,
        action="knowledge.publish",
        resource=document["name"],
        outcome="success",
        detail=f"version={document.get('version_no', 1)}",
    )
    return document


@router.get("/documents/{filename}")
def preview_knowledge_document(
    filename: str,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_role(identity, "approver", "admin")
    try:
        return request.app.state.knowledge_service.read_document(filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="知识文档不存在") from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/documents/{filename}/download")
def download_knowledge_document(
    filename: str,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> Response:
    require_role(identity, "approver", "admin")
    try:
        document = request.app.state.knowledge_service.read_document(filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="知识文档不存在") from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=document["content"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document['name'])}"},
    )


@router.delete("/documents/{filename}")
def delete_knowledge_document(
    filename: str,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    require_role(identity, "admin")
    try:
        result = request.app.state.knowledge_service.delete_document(
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            filename=filename,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="知识文档不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.app.state.after_sales_graph.knowledge_base = (
        request.app.state.knowledge_service.knowledge_base
    )
    request.app.state.repository.add_audit(
        thread_id=f"knowledge-{filename}",
        user_id=identity.user_id,
        action="knowledge.delete",
        resource=filename,
        outcome="success",
        detail="文档已退役，历史版本保留",
    )
    return result


@router.post("/rebuild")
def rebuild_knowledge(
    request: Request, identity: Identity = Depends(current_identity)
) -> dict[str, int]:
    require_role(identity, "admin")
    chunks = request.app.state.knowledge_service.rebuild()
    request.app.state.after_sales_graph.knowledge_base = (
        request.app.state.knowledge_service.knowledge_base
    )
    request.app.state.repository.add_audit(
        thread_id="knowledge-rebuild",
        user_id=identity.user_id,
        action="knowledge.rebuild",
        resource="售后政策知识库",
        outcome="success",
        detail=f"chunks={chunks}",
    )
    return {"chunks": chunks}
