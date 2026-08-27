# Testing Patterns

## 1. Test Stack and Commands

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m ruff check app tests scripts
cd frontend; npm test
cd frontend; npm run build
```

- Backend: pytest 8.x, FastAPI TestClient and standard asserts.
- Frontend: Node built-in test runner; vue-tsc and Vite verify types/build.

## 2. Test Layout

- `tests/conftest.py`: graph/repository fixtures.
- `test_graph.py`: routing, specialist selection, interrupt/resume, idempotency, scope, injection and SSE.
- `test_enterprise_after_sales.py`: case/refund/return/fulfillment flows.
- `test_api.py`: auth, HTTP scope, knowledge lifecycle, request IDs and refund API.
- Focused tests cover identity, knowledge, RAG, repository and tool runtime.
- `frontend/tests/` covers permission visibility and request-ID generation.

## 3. Scope Matrix

| Scope | Covered? | Typical target | Notes |
|---|---|---|---|
| Unit | yes | RAG, permission, identity, runtime | No threshold |
| Application integration | yes | FastAPI + temp SQLite + LangGraph | External services replaced |
| Domain lifecycle | yes | refund-only, return-refund, fulfillment | Not every failure branch |
| Browser E2E | no | login-to-business flow | Manual screenshots only |
| Infrastructure integration | no | MySQL/Redis/Milvus/MinIO/MCP | Needs CI matrix |
| Migration | partial manual | local DB at head | No automated rollback fixture |
| Performance/security | no | load/concurrency/DAST | Not configured |

## 4. Mocking and Isolation

- Tests use temporary SQLite or `InMemorySupportRepository`.
- LLM-disabled deterministic behavior removes model nondeterminism.
- Refund gateway defaults to deterministic sandbox.
- This proves code paths/contracts, not provider SLAs or distributed recovery.

## 5. Verified Signals (2026-08-22)

- Backend: 36 tests passed; one Starlette TestClient deprecation warning.
- Frontend: 6 tests passed.
- Ruff: passed.
- Vue production build: passed, 961 modules transformed.
- Alembic: local SQLite reports `0003 (head)`.

## 6. Evidence

- `pyproject.toml`, `frontend/package.json`
- `tests/`, `frontend/tests/`
- verification output from the current repository run on 2026-08-22
