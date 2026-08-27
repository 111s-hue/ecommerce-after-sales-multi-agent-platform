# Technology Stack

## 1. Runtime Summary

| Area | Value | Evidence |
|---|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn | `Dockerfile`, `requirements.txt`, `app/main.py` |
| Agent runtime | LangGraph 1.x, LangChain Core 1.x, MCP 1.x | `requirements.txt`, `app/graph/orchestrator.py`, `app/mcp_server.py` |
| Data access | SQLAlchemy 2.x, Alembic 1.x, PyMySQL; SQLite for local development | `requirements.txt`, `alembic.ini`, `app/infrastructure/` |
| Identity | PyJWT + Argon2 through `pwdlib` | `requirements.txt`, `app/services/auth.py`, `app/services/identity.py` |
| Frontend | Vue 3.5, TypeScript 5.9, Element Plus 2.10, Axios 1.11, Vite 7 | `frontend/package.json` |
| Package management | pip/requirements + npm/package-lock | `requirements*.txt`, `frontend/package-lock.json` |
| Containers | Python 3.11 slim backend; Node 22 build + Nginx 1.27 frontend | `Dockerfile`, `frontend/Dockerfile` |

## 2. Production Dependencies

| Dependency | Role | Runtime position |
|---|---|---|
| FastAPI / Pydantic | Versioned REST/SSE API, strict request DTOs and settings | API boundary |
| LangGraph | Supervisor graph, specialist subgraphs, interrupt/resume and checkpoints | AI orchestration |
| SQLAlchemy / Alembic | 78 business-table metadata and migration revisions `0001`–`0003` | Relational persistence |
| Qwen through OpenAI-compatible HTTP | Structured routing, bounded tool calling and response synthesis | Optional real LLM path |
| Milvus + BGE-M3 + BM25/RRF | Tenant-filtered production hybrid retrieval | Optional production RAG path |
| Redis Checkpointer | Recoverable LangGraph thread state | Compose/production profile |
| MinIO | Markdown source-object copy | Compose/production profile |
| MCP | Cross-process commerce tool transport | Compose profile |
| Element Plus | Console component system | Browser UI |

The checked-in `.env` runs SQLite, local tools, `hybrid-lite`, disabled LLM and disabled MinIO. `docker-compose.yml` switches to MySQL, Redis checkpoints, MCP, Milvus and MinIO. These are distinct runtime profiles.

## 3. Development Toolchain

| Tool | Purpose | Configuration |
|---|---|---|
| pytest 8.x | Backend unit and integration-style tests | `pyproject.toml`, `tests/` |
| Ruff | Python lint/import rules `E,F,I,B,UP`, line length 100 | `pyproject.toml` |
| Node test runner | Frontend permission/request-ID tests | `frontend/package.json` |
| vue-tsc + Vite | Strict TypeScript checking and production bundle | `frontend/tsconfig.json`, `frontend/vite.config.ts` |
| Docker Compose | Local full dependency topology and migration job | `docker-compose.yml` |

## 4. Key Commands

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m ruff check app tests scripts
.\venv\Scripts\python.exe -m alembic upgrade head
cd frontend; npm test; npm run build
docker compose up --build
```

## 5. Environment and Config

- Sources: `.env`, `.env.example`, `.env.production.example`, `app/config.py`, Compose environments.
- Sensitive variables: `JWT_SECRET`, `DATABASE_URL`, `LLM_API_KEY`, `MILVUS_TOKEN`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`.
- Production guard rejects disabled auth, demo seeding, SQLite, default/short JWT secrets, wildcard hosts/origins, long-lived access tokens and default MinIO credentials.
- Backend docs/OpenAPI are disabled in production mode.
- Node/browser support policy is not pinned beyond the Node 22 container image.

## 6. Evidence

- `requirements.txt`, `requirements-ai.txt`, `pyproject.toml`
- `frontend/package.json`, `frontend/tsconfig.json`
- `app/config.py`, `.env.production.example`
- `Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`
