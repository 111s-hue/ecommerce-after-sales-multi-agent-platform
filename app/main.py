from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import router
from app.config import get_settings
from app.graph.checkpoint import CheckpointerHandle
from app.graph.orchestrator import AfterSalesGraph
from app.infrastructure.repository import SQLAlchemySupportRepository
from app.services.after_sales import AfterSalesService
from app.services.identity import IdentityService
from app.services.knowledge import KnowledgeService
from app.services.llm import OpenAICompatibleLLM
from app.services.notifications import NotificationService
from app.tools.commerce import CommerceTools
from app.tools.mcp_client import MCPCommerceTools


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_for_startup()
    repository = SQLAlchemySupportRepository(settings.database_url)
    if settings.environment == "production":
        repository.assert_schema_revision("0003")
    else:
        repository.init_schema()
    if settings.seed_demo_data:
        repository.seed_demo_data()
    identity_service = IdentityService(repository.engine)
    if settings.seed_demo_data:
        identity_service.seed_development_identities()
    checkpointer = CheckpointerHandle(settings)
    knowledge_service = KnowledgeService(settings, repository.engine)
    tools = (
        MCPCommerceTools(settings.mcp_server_url, settings.llm_timeout_seconds)
        if settings.tool_transport == "mcp"
        else CommerceTools(repository)
    )
    app.state.repository = repository
    app.state.identity_service = identity_service
    app.state.after_sales_service = AfterSalesService(repository.engine)
    app.state.notification_service = NotificationService(repository.engine)
    app.state.settings = settings
    app.state.checkpointer = checkpointer
    app.state.knowledge_service = knowledge_service
    app.state.after_sales_graph = AfterSalesGraph(
        tools,
        knowledge_service.knowledge_base,
        checkpointer.saver,
        llm=OpenAICompatibleLLM(settings),
        repository=repository,
    )
    yield
    checkpointer.close()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="企业级电商售后多智能体协同平台 API",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", settings.request_id_header],
        expose_headers=[settings.request_id_header, "X-Process-Time-Ms"],
    )

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get(settings.request_id_header) or uuid4().hex
        request.state.request_id = request_id
        started_at = perf_counter()
        response = await call_next(request)
        response.headers[settings.request_id_header] = request_id
        response.headers["X-Process-Time-Ms"] = f"{(perf_counter() - started_at) * 1000:.2f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    application.include_router(router, prefix=settings.api_prefix)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "after-sales-agent"}

    return application


app = create_app()
