# External Integrations

## 1. Integration Inventory

| System | Type | Purpose | Auth/config | Checked-in behavior | Evidence |
|---|---|---|---|---|---|
| SQLite / MySQL | DB | Operational truth and 78-table schema | SQLAlchemy URL | SQLite local; MySQL Compose/production | `config.py`, Compose |
| Redis Stack | state store | Recover LangGraph threads | Redis URL | Memory local; Redis optional | `graph/checkpoint.py` |
| Qwen/vLLM | HTTP API | Route, tool-call and synthesize | Bearer API key | Disabled fallback locally | `services/llm.py` |
| Milvus + etcd | vector/search DB | Hybrid policy retrieval | URI/token | hybrid-lite local; Milvus adapter/Compose | `milvus_store.py` |
| MinIO | S3 store | Policy source copy | access/secret key | Disabled local; enabled Compose | `knowledge.py` |
| MCP tool server | HTTP/MCP | Cross-process commerce tools | URL; no service identity | Local default; MCP Compose | MCP files |
| Refund provider | application port | Execute refund | provider-specific | Deterministic sandbox | `after_sales.py` |
| Nginx | proxy/static | SPA and `/api/` proxy | network boundary | Container implementation | `nginx.conf` |

## 2. Data Stores

| Store | Role | Access layer | Key risk |
|---|---|---|---|
| SQLite/MySQL | Business records | repository + services | Production startup rejects SQLite |
| Redis | Graph checkpoints | `CheckpointerHandle` | Enabled only by setting |
| Milvus | Policy retrieval | `MilvusHybridStore` | Requires separate service health |
| Local files/MinIO | Markdown source | `KnowledgeService` | Current builder still reads local files |
| JSON file | Evaluation report | monitoring route | Offline, not an online metrics store |

## 3. Secrets and Credentials

- Development examples contain non-production credentials.
- Production template uses replacement markers and startup validation.
- No external secret manager or automatic rotation is implemented.
- MCP currently has no trusted service-to-service identity/signature.

## 4. Reliability and Failure Behavior

- LLM calls have timeout, retry and deterministic fallback.
- Agent tool loops are bounded by `MAX_AGENT_STEPS`.
- Refund execution records attempts/events and returns the existing succeeded result.
- Case mutations write Outbox and notification rows atomically.
- Checked-in code lacks an Outbox worker, dead-letter workflow and real provider callback verifier.
- Readiness checks the relational database only.

## 5. Observability

- HTTP responses expose request ID and processing time.
- Agent nodes append trace entries; conversations/messages and audit persist.
- Refund attempts/events and case histories provide domain traceability.
- Missing: centralized logs/traces, Prometheus, dependency health matrix and wired model cost persistence.

## 6. Evidence

- `.env.example`, `.env.production.example`, `docker-compose.yml`
- `app/services/llm.py`, `rag.py`, `milvus_store.py`, `knowledge.py`
- `app/tools/mcp_client.py`, `app/services/after_sales.py`
