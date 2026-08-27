# Codebase Structure

## 1. Top-Level Map

| Path | Purpose | Evidence |
|---|---|---|
| `app/api/` | HTTP routers, auth dependencies and DTOs | `app/api/routes.py` |
| `app/domain/` | Framework-independent Pydantic entities and repository protocol | `app/domain/models.py`, `repositories.py` |
| `app/graph/` | LangGraph state, Supervisor, specialist subgraphs and checkpoint selection | `app/graph/orchestrator.py` |
| `app/services/` | Identity, after-sales, LLM, RAG, knowledge, notification and dashboard use cases | `app/services/` |
| `app/infrastructure/` | SQLAlchemy base, 78-table metadata and legacy repository adapter | `app/infrastructure/` |
| `app/tools/` | Trusted commerce tools and MCP client adapter | `app/tools/` |
| `frontend/src/views/` | Eight console pages | `frontend/src/App.vue` |
| `frontend/src/composables/` | Console state, data loading and user actions | `useConsole.ts` |
| `migrations/` | Alembic baseline, enterprise schema and order enrichment | `migrations/versions/` |
| `tests/`, `frontend/tests/` | Backend and frontend automated tests | test files |
| `scripts/` | Seed and offline evaluation entry points | `scripts/seed.py`, `evaluate.py` |
| `data/` | Local SQLite, policies and evaluation report | `.env.example` |
| `docs/` | Architecture, codebase map and project guide | Markdown files |

## 2. Entry Points

- FastAPI: `app/main.py` exports `app = create_app()`.
- MCP tool process: `python -m app.mcp_server`.
- Frontend: `frontend/src/main.ts`; Nginx proxies `/api/` to the backend.
- Database release: `python -m alembic upgrade head`; Compose has a dedicated `migrate` service.
- Operations scripts: `python -m scripts.seed`, `python -m scripts.evaluate`.

## 3. Module Boundaries

| Boundary | What belongs here | What must not be here |
|---|---|---|
| API | HTTP validation, auth/scope, status mapping | SQL and state-transition rules |
| Domain | Business value models and persistence port | FastAPI, SQLAlchemy, browser concerns |
| Graph | AI decision flow, tool selection, interrupt/resume, trace | Authoritative payment/refund state machine |
| Services | Transactional use cases and external-capability wrappers | View markup |
| Infrastructure | ORM metadata, database and service adapters | HTTP presentation |
| Tools | Narrow AI-callable operations with trusted identity overrides | Model-supplied authorization |
| Frontend | Navigation, presentation and API interaction | Authorization truth or financial consistency |

## 4. Frontend View Map

| View | Main responsibility |
|---|---|
| `LoginView.vue` | Tenant account login |
| `OverviewView.vue` | Operational summary and collaboration topology |
| `WorkbenchView.vue` | Specialist selection, SSE trace and approval result |
| `ApprovalsView.vue` | Pending LangGraph approval decisions |
| `OperationsView.vue` | Orders and enterprise after-sales cases |
| `ConversationsView.vue` | Conversation list |
| `KnowledgeView.vue` | Upload, preview, download, retire and rebuild |
| `AuditView.vue` / `InsightsView.vue` | Audit and offline evaluation/summary |

## 5. Naming and Organization

- Python: `snake_case.py`, `snake_case()` and `PascalCase` classes.
- Vue components/views: `PascalCase.vue`; TypeScript functions use `camelCase`.
- Python imports use `app.*`; frontend imports are relative.
- Router modules are aggregated in `app/api/routes.py`; views are lazy-loaded from `App.vue`.

## 6. Evidence

- `docs/codebase/.codebase-scan.txt`
- `app/main.py`, `app/api/routes.py`
- `frontend/src/App.vue`, `frontend/src/composables/useConsole.ts`
- `docker-compose.yml`
