# Coding Conventions

## 1. Naming Rules

| Item | Rule | Example | Evidence |
|---|---|---|---|
| Python files | snake case | `after_sales.py` | `app/services/` |
| Python functions | snake case; private helper prefixed `_` | `_set_case_status` | `app/services/after_sales.py` |
| Python classes/types | PascalCase | `AfterSalesService` | same file |
| Vue files | PascalCase | `KnowledgeView.vue` | `frontend/src/views/` |
| TS functions/values | camelCase | `refreshCurrentView` | `useConsole.ts` |
| Env/constants | upper snake case | `RAG_BACKEND`, `CASE_TRANSITIONS` | `.env.example`, services |
| Relational tables | plural snake case | `refund_attempts` | `enterprise_models.py` |

## 2. Formatting and Linting

- Ruff targets Python 3.11, line length 100 and rules `E`, `F`, `I`, `B`, `UP`.
- TypeScript is strict; build executes `vue-tsc --noEmit` before Vite.
- There is no independent Python formatter or ESLint/Prettier configuration.

```powershell
.\venv\Scripts\python.exe -m ruff check app tests scripts
cd frontend; npm run build
```

## 3. Import and Module Conventions

- Python uses absolute `app.*` imports and Ruff import ordering.
- API routers are registered centrally.
- Vue pages are lazy imports; shared API/types/security code sits outside views.
- Frontend has no path aliases/barrel-export convention.

## 4. Error and Logging Conventions

- Request DTOs inherit `StrictRequest` and reject unknown fields.
- `AfterSalesError` subclasses map to 404/409/422/400 at the API boundary.
- Authentication and authorization failures are 401/403 `HTTPException`s.
- Every HTTP response carries request ID, elapsed time and security headers.
- Business audit is persisted, but no unified structured logger/OpenTelemetry pipeline exists.
- APIs return controlled Chinese error detail; future adapter errors must remain redacted.

## 5. Persistence Conventions

- Enterprise tables carry `tenant_id`; money uses `NUMERIC(18,2)`.
- Public records use UUID-like IDs; business numbers use time plus random suffix.
- Mutating after-sales use cases run inside SQLAlchemy transactions.
- Case transitions append history and increment `version`.
- Idempotent create requests compare a request hash before returning a stored response.

## 6. Testing Conventions

- Backend: `tests/test_*.py`, fixtures in `tests/conftest.py`, temporary SQLite or memory repository.
- Frontend: `frontend/tests/*.test.ts`, Node built-in test runner.
- External LLM/vector/payment services are isolated by deterministic fallbacks/adapters.
- No coverage threshold is configured.

## 7. Evidence

- `pyproject.toml`, `frontend/tsconfig.json`
- `app/api/schemas.py`, `app/api/routers/after_sales.py`
- `app/services/after_sales.py`
- `tests/conftest.py`, `frontend/tests/`
