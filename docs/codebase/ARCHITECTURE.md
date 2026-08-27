# Architecture

## 1. Architectural Style

The repository is a modular layered monolith with two optional distributed edges: an MCP commerce-tool process and infrastructure services for Redis, MinIO and Milvus. LangGraph is the AI orchestration layer; the relational `AfterSalesService` is the authoritative enterprise after-sales state machine.

Primary constraints are tenant/user isolation, approval before sensitive AI writes, traceable evidence, idempotent financial operations and local deterministic fallback.

## 2. System Flow

```text
Vue console
  -> FastAPI request context + JWT/RBAC + tenant/customer scope
    -> LangGraph Supervisor or transactional application service
      -> trusted tool / repository / RAG / refund-gateway port
        -> SQLite/MySQL + Redis/Milvus/MinIO/MCP profile
          -> response, audit, status history, Outbox and notification
```

1. `app/main.py` validates settings and assembles repository, identity, after-sales, notification, knowledge, LLM, tools and graph.
2. API dependencies decode JWT against issuer/audience and re-resolve current database roles/permissions.
3. Chat requests enter prompt-injection detection, Supervisor routing and one of order/logistics/policy/refund specialist subgraphs.
4. Sensitive AI refund actions stop at `interrupt`; an approver resumes the same `thread_id` from a checkpoint.
5. Direct after-sales APIs use transactions, transition guards, optimistic version checks and idempotency records.
6. State changes write history, Outbox events and in-app notifications in the same transaction.

## 3. Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|---|---|---|---|
| API | Protocol conversion and authorization | SQL | `routers/*.py` |
| Graph | Agent decision/control flow | Payment truth | `orchestrator.py` |
| After-sales service | Seven case types and domain transitions | HTTP rendering | `after_sales.py` |
| Identity service | Tenant users, Argon2, lockout and RBAC | UI visibility | `identity.py` |
| Knowledge service | File lifecycle, versions and index rebuild | Agent routing | `knowledge.py` |
| Infrastructure | SQLAlchemy schema/repository | Page behavior | `enterprise_models.py` |
| Frontend | Role-aware console and API/SSE clients | Backend authorization | `App.vue`, `useConsole.ts` |

## 4. Reused Patterns

| Pattern | Where | Why it exists |
|---|---|---|
| Repository port/adapter | domain + infrastructure | SQL/in-memory substitution |
| Strategy/adapter | tools, LLM, RAG, refund gateway | Runtime substitution |
| State machine | LangGraph and `CASE_TRANSITIONS` | Legal transitions |
| Transactional unit of work | `Session.begin()` | Atomic writes |
| Idempotency | records and refund key | Safe retry |
| Optimistic locking | case `version` compare/update | Concurrent conflict detection |
| Outbox | case transaction | Reliable hand-off foundation |

## 5. Core State Machines

- Case: `submitted -> under_review -> approved/rejected`; approved branches to `processing` or `awaiting_customer_return`, then `awaiting_receipt -> processing -> completed`.
- Refund: `pending/failed -> succeeded|failed`, with attempt and event records.
- Return: `awaiting_shipment -> in_transit -> accepted|rejected`.
- AI approval: `pending` checkpoint -> approved/rejected resume.
- Knowledge: immutable version + review + index job + publication; deletion retires current records.

## 6. Known Architectural Risks

- Legacy Agent tables and the enterprise domain coexist; `after_sale_tickets` and `after_sale_cases` should eventually be unified.
- Outbox rows are produced but no checked-in worker dispatches them.
- Real payment providers implement the `RefundGateway` port outside the current repository; checked-in execution uses `SandboxRefundGateway`.
- Several core backend/frontend files exceed 500 lines.
- Overview metrics aggregate bounded legacy reads rather than enterprise/time-window analytics.

## 7. Evidence

- `app/main.py`, `app/graph/orchestrator.py`
- `app/services/after_sales.py`, `identity.py`, `knowledge.py`
- `app/infrastructure/enterprise_models.py`
- `frontend/src/App.vue`
