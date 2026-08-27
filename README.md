# LangGraph 电商售后多智能体协同平台

一个面向电商售后的企业级 AI 协同平台：LangGraph Supervisor 编排订单、物流、政策和退款子图，Agentic RAG 提供条款级引用，敏感退款操作使用人工审批中断与检查点恢复。管理端覆盖运营总览、实时工作台、审批、业务台账、知识治理、审计与质量评测。

详细范围和验收标准见 [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md)。
系统分层、核心链路与工程边界见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，代码库结构与集成说明见 [docs/codebase](docs/codebase)。

## 技术栈

- Python 3.11、FastAPI、LangGraph、LangChain Core、MCP
- MySQL / SQLite、Redis Checkpointer、MinIO
- 生产检索：Milvus（BGE-M3 dense + 原生 BM25 sparse + RRF）；本地单测使用轻量内存后端，FAISS 仅保留为离线实验适配器
- Qwen / vLLM OpenAI-compatible API
- Vue 3、Element Plus、Vite、Docker Compose

## 工程架构

- `app/api/routers`：按认证、智能体运行、业务运营、知识治理和监控拆分的版本化 HTTP 接口。
- `app/services`：模型、知识、认证、运行时和运营读模型等应用服务。
- `app/domain`：业务实体与仓储端口，不依赖 Web 或数据库实现。
- `app/infrastructure`：SQLAlchemy、Milvus、MinIO、Redis 等基础设施适配器。
- `app/graph`：LangGraph 状态、检查点、Supervisor 与专业智能体子图。
- `frontend/src/views`：按业务域异步加载的管理端视图；`services` 和 `composables` 负责 API 与状态。

每个 HTTP 响应会返回 `X-Request-ID` 和 `X-Process-Time-Ms`，便于在网关、日志和 APM 中关联请求。更完整的边界与链路说明见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 本地启动

项目已经约定使用根目录下的 `venv`：

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m scripts.seed
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/docs`。前端开发：

```powershell
cd frontend
npm install
npm run dev
```

默认使用 SQLite、内存检查点和本地政策文档，所以不启动外部服务也能完成演示。演示账号为 `U1001`，订单为 `ORD-1001`、`ORD-1002`；`U2001` 的订单 `ORD-2001` 可用于越权测试。

默认 `AUTH_ENABLED=true`，账号必须从登录页进入；开发种子账号：

- 管理员：`admin / admin123`
- 审批人：`supervisor / supervisor123`
- 消费者：`U1001 / customer123`

## 真实模型与向量检索

1. 安装扩展依赖：`python -m pip install -r requirements-ai.txt`。
2. 在 `.env` 中设置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。
3. 将 `RAG_BACKEND` 设置为 `bge-faiss`，首次启动会加载 `BAAI/bge-m3`。

不配置模型服务时，系统仍使用确定性的模板生成器完成全部业务流程和自动化测试。

生产检索设置 `RAG_BACKEND=milvus`。服务会创建包含 `tenant_id` Partition Key、
稠密向量和 BM25 稀疏向量的 collection，并在查询时进行租户过滤与 RRF 融合。
该模式需要手动安装 `requirements-ai.txt` 并启动 Compose 中的 Milvus；
`hybrid-lite` 是默认的无外部依赖测试后端，`bge-faiss` 只用于离线实验和回归对照。

启用真实智能体：

```dotenv
LLM_ENABLED=true
LLM_BASE_URL=http://localhost:8001/v1
LLM_MODEL=Qwen/Qwen3-8B-Instruct
```

此时 Supervisor 使用结构化输出，专业 Agent 使用 OpenAI Tool Calling，最终回答由 Qwen 基于真实工具结果和政策证据生成。模型调用失败会在节点轨迹中记录降级来源。

## API 示例

```powershell
$body = @{ user_id = 'U1001'; thread_id = 'demo-1'; query = 'ORD-1001 想退款' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/chat -ContentType application/json -Body $body

$approval = @{ approved = $true; reviewer = '客服主管'; reason = '核验通过' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/approvals/demo-1 -ContentType application/json -Body $approval
```

SSE 接口为 `POST /api/v1/chat/stream`，会依次输出 accepted、graph 和 result 事件。

运营接口还包括：

- `GET /api/v1/orders`、`GET /api/v1/after-sales`：订单与售后工单台账，消费者身份自动收窄数据范围。
- `GET /api/v1/health/ready`：包含数据库检查的就绪探针。
- `GET /api/v1/system/info`：返回当前模型、检索、工具通道与环境信息（不包含密钥）。
- `GET /api/v1/metrics/summary`：控制台运营汇总。
- `POST /api/v1/after-sale-cases`：创建仅退款、退货退款、换货、补发、维修、补偿或申诉。
- `POST /api/v1/after-sale-cases/{id}/review`：写入审批记录并创建对应履约子单。
- `POST /api/v1/after-sale-cases/{id}/refunds/{refund_id}/execute`：通过支付网关适配器执行幂等退款。
- `GET/POST/PUT /api/v1/users`：组织内用户、角色与账号状态管理。

若 Windows 出现 `WinError 10013`，先确认使用显式回环地址 `--host 127.0.0.1`，再检查端口：

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 8000
netsh interface ipv4 show excludedportrange protocol=tcp
```

本项目已验证 8000 不在系统保留端口范围；不要为了处理该错误关闭防火墙或以管理员身份长期运行服务。

## MCP Server

```powershell
python -m app.mcp_server
```

默认以 Streamable HTTP 方式运行，暴露订单、物流、资格判断和售后单创建工具。生产环境应在网关层补充 OAuth/服务身份认证。

让 LangGraph 通过 MCP 跨进程调用工具：

```dotenv
TOOL_TRANSPORT=mcp
MCP_SERVER_URL=http://localhost:8002/mcp
```

需要分别启动 `python -m app.mcp_server` 和 FastAPI。Docker Compose 已默认采用这一模式。

## 测试和质量检查

```powershell
pytest
ruff check app tests scripts
python -m scripts.evaluate
```

评测结果写入 `data/evaluation/latest.json`，可在管理端“评测看板”查看。

## Docker Compose

```powershell
docker compose up --build
```

前端地址为 `http://localhost:8080`，API 文档为 `http://localhost:8000/docs`。Compose 使用 MySQL、Redis Stack、MinIO、etcd 和 Milvus，并启用 Redis 持久化检查点及 Milvus 混合检索。

Compose 文件是本地完整依赖栈。正式部署应复制 `.env.production.example`，替换所有 `REPLACE_ME`，先运行 `alembic upgrade head`，再启动应用；生产模式会拒绝 SQLite、演示数据、默认 JWT/MinIO 凭据、通配域名及超过 60 分钟的访问令牌，并拒绝数据库迁移版本落后于应用。
