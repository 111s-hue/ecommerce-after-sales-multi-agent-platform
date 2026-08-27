# Codebase Concerns

## 1. Top Risks

| Severity | Concern | Evidence | Impact | Suggested action |
|---|---|---|---|---|
| high | Legacy ticket flow and enterprise case flow coexist | two table families | Two sources of truth | Route AI writes through enterprise service and migrate legacy rows |
| high | Outbox has producers but no worker | `outbox_events`, no worker entry | No external delivery/retry | Add worker, leasing, retry and dead-letter |
| high | Real refund provider is not checked in | `SandboxRefundGateway` | No real money movement | Add provider adapters, callbacks and reconciliation jobs |
| high | MCP has no service authentication | `app/mcp_server.py` | Network-trust dependency | mTLS/service JWT and signed user context |
| medium | Dashboard reads bounded legacy lists | `dashboard.py` | Inaccurate at scale | SQL/time-window read model |
| medium | Core files exceed 500 lines | scan metrics | Change risk | Split by bounded context/use case |
| medium | Distributed/E2E tests absent | test layout | Integration regressions | CI matrix and browser E2E |

## 2. Technical Debt

| Item | Why it exists | Risk if ignored | Suggested fix |
|---|---|---|---|
| legacy repository + memory adapter + seed | MVP compatibility | Coupling | Contract tests then domain repositories |
| 1,030-line enterprise schema | Central rollout | Conflicts | Split metadata by domain |
| 851-line after-sales service | State machine in one service | Hard extension | Separate commands/policies/query assembly |
| 504-line console composable | Single UI store | Coupling | Pinia/domain stores |
| Manual view switching | Fast delivery | No deep links | Use installed Vue Router |
| File-first knowledge runtime | Simple rebuild | Multi-instance risk | Object/version truth + async publication |

## 3. Security Concerns

| Risk | Current mitigation | Gap |
|---|---|---|
| Token theft | sessionStorage, expiry, DB re-resolution | No refresh rotation UI/MFA |
| Brute force | Argon2, lockout, login events | No IP rate limit |
| Resource access | tenant IDs, RBAC, customer scope | Legacy tables partly lack tenant IDs |
| Prompt injection | pre-tool guard, whitelist | Pattern guard is incomplete by nature |
| Audit tampering | read-only API | DB table not cryptographically chained |
| Dev secrets | production guards | Compose exposes dev credentials/ports |

## 4. Performance and Scaling

- Synchronous SQL/external calls occupy workers during slow dependencies.
- Knowledge rebuild is synchronous and full-index.
- Global search loads collections and filters client-side.
- Dashboard reads up to 500 rows per legacy collection and aggregates in Python.
- Enterprise case pagination exists; several legacy APIs only expose a limit.

## 5. Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe strategy |
|---|---|---|---|
| `after_sales.py` | many transitions | no Git history | transition matrix tests |
| `orchestrator.py` | routing+persistence+SSE | no history | graph snapshots, isolate persistence |
| `repository.py` | SQL+memory+seed | no history | repository contract tests |
| `useConsole.ts` | all actions/loaders | no history | extract one store at a time |
| knowledge publish | file/S3/DB/index | no history | durable jobs and rollback tests |

## 6. `[ASK USER]` Questions

1. [ASK USER] 实际团队人数、个人角色和开发周期是多少？
2. [ASK USER] 正式部署是否真的接入微信、支付宝或其他支付商户？
3. [ASK USER] 社区版是多商家共实例，还是单组织部署但保留租户字段？
4. [ASK USER] Outbox、Webhook、邮件/短信由本仓库还是部署平台负责？
5. [ASK USER] 生产规模、SLA、日工单量和模型规格是多少？

## 7. Intent vs. Reality

- 产品目标是可私有化企业售后平台；当前代码具备企业基线，但 `.env` 是轻依赖开发档。
- 关系模型有 78 张业务表；不少治理/质量/集成表是结构基础，在当前 SQLite 中为空。
- 核心售后状态机和沙箱退款已测试；真实商户支付、对账调度和回调验签不在仓库中。
- 知识发布记录版本/审核/索引/发布，但当前是管理员发布即审核，不是独立会签流程。
- Outbox 和投递表存在，后台投递 worker 不存在。
- 退货寄回/仓库验收有 API，前端尚无完整表单入口。

## 8. Evidence

- `docs/codebase/.codebase-scan.txt`
- `app/services/after_sales.py`, `dashboard.py`
- `app/infrastructure/enterprise_models.py`, `repository.py`
- `frontend/src/composables/useConsole.ts`
- `.env`, `docker-compose.yml`, `tests/`
