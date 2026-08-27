# AfterFlow 企业级架构说明

## 设计目标

系统围绕四个不可妥协的边界构建：用户数据隔离、敏感写操作审批、AI 决策可追溯、外部依赖可降级。HTTP、应用服务、领域模型和基础设施适配器分层，前端按业务视图拆包，避免把业务规则继续堆积到路由或页面组件中。

## 请求链路

1. API 中间件生成或透传 `X-Request-ID`，记录请求耗时。
2. 认证依赖解析 JWT；消费者请求会被强制收窄到令牌中的用户身份。
3. Supervisor 识别意图、风险和缺失字段，并路由到白名单专业智能体。
4. 专业智能体调用订单、物流、政策或退款资格工具；所有业务结果来自可信工具，不从模型文本中提取身份。
5. 政策检索返回条款、来源、分数和证据等级；证据不足时转人工。
6. 退款写操作通过 LangGraph interrupt 暂停，审批后从同一 thread 检查点恢复。
7. 工单创建使用幂等键，避免恢复、重试或网络抖动造成重复写入。
8. 会话、消息、审批和工具调用进入持久化与审计链路。

## 模块边界

```text
Client
  -> API routers / auth scope / request context
    -> Agent runtime + operational read services
      -> Domain repository contract
        -> SQLAlchemy / MCP / Milvus / MinIO / Redis adapters
```

`app/domain` 不引用 FastAPI、SQLAlchemy 或 LangGraph。路由只完成协议转换、权限校验和错误映射；跨资源统计由 `DashboardService` 生成读模型。工具层仍是智能体访问业务数据的唯一入口。

## 前端架构

`App.vue` 只负责应用框架和视图切换；`useConsole` 管理会话状态与加载策略；`services/api.ts` 统一超时、令牌、请求 ID、错误提取和 SSE 解析。各业务页放在 `views` 中异步加载，Element Plus 仅注册实际使用的组件。

视觉语言以深海蓝灰表达控制与可信，以信号青绿表达自动执行，以琥珀色表达人工审批。运营总览中的协同链路是核心视觉和信息结构，不是装饰：它对应真实的 Supervisor、专业智能体、人工闸门和幂等执行阶段。

## 生产化建议

- 在 API 网关启用 TLS、限流、WAF、OAuth/OIDC，并将演示账号替换为企业身份源。
- 将 JWT 密钥、数据库密码和对象存储凭据迁移到密钥管理服务。
- 使用 Alembic 管理数据库迁移，并在生产环境设置 `SEED_DEMO_DATA=false`；后续可将启动期 `create_all` 迁移为独立发布任务。
- 接入 OpenTelemetry，将 request ID、thread ID、节点耗时、模型 token 和工具结果关联到统一 trace。
- 将审批任务接入企业消息系统，并设置超时、升级与撤回策略。
- 为知识发布增加版本、双人复核、灰度索引和回滚能力。
