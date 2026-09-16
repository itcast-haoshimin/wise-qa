# Wise QA - AI Agent Center

基于微服务架构的 AI 智能体中心（天机 AI 助手），提供课程推荐、购买、咨询、知识讲解等智能服务。

整体采用「网关统一接入 + 核心智能体中心编排 + 下游 MCP / A2A 服务」的分层架构：

- `agent-center-gateway` 负责认证、限流、熔断与路由；
- `agent_center` 是核心智能体中心服务，负责意图识别、多智能体编排、会话管理与 SSE 流式输出；
- `agent_center_mcp` 与 `agent_center_a2a` 分别作为 MCP 工具服务与 A2A 智能体服务，被核心服务调用。

## 项目结构

| 模块 | 说明 | 技术栈 |
|------|------|--------|
| `agent_center` | **核心智能体中心服务**：意图识别、多智能体编排、会话管理、MCP/A2A 调用、SSE 流式输出 | Python, FastAPI, LangChain/LangGraph, Nacos, Redis, MySQL, PostgreSQL |
| `agent-center-gateway` | API 网关，负责认证、限流、熔断、路由转发 | Spring Cloud Gateway, Nacos, Redis, JWT |
| `agent_center_mcp` | MCP (Model Context Protocol) 服务端，提供标准化工具调用接口 | Python, MCP, Nacos |
| `agent_center_a2a` | Agent-to-Agent 智能体服务，包含推荐/购买/咨询/知识讲解等多个 Agent | Python, OpenAI, Nacos, MCP |

## 架构图

```
客户端
  │
  ▼
agent-center-gateway (Spring Cloud Gateway)   认证(JWT RSA) / 限流(Redis) / 熔断(Resilience4j)
  │  转发时携带 header: request-from = agent-center-gateway
  ▼
agent_center (核心智能体中心 · FastAPI :18089 · Nacos 注册名 agent-center)
  │
  ├── 意图识别与多智能体编排 (LangGraph StateGraph)
  │      START → intent_agent → 条件路由 → 子智能体 → END
  │          ├── RecommendAgent  课程推荐
  │          ├── BuyAgent        课程购买
  │          ├── ConsultAgent    课程咨询
  │          ├── KnowledgeAgent  知识讲解
  │          └── UnknownAgent    兜底
  │
  ├── MCP 客户端 ──► agent_center_mcp (:18099)     MCP 工具服务
  │                     ├── query_course_by_id     课程查询
  │                     └── pre_place_order        预下单
  │
  └── A2A 客户端 ──► agent_center_a2a (:3601~3605)  A2A 智能体服务

  LLM: 通义千问 Qwen3-Max（OpenAI 兼容接口，dashscope）
```

## 模块详情

### agent_center（核心智能体中心服务）

核心服务，基于 FastAPI 对外提供 HTTP 接口，内部使用 LangGraph 进行意图识别与多智能体编排，通过 MCP / A2A 协议调用下游服务，并以 SSE 流式返回结果。

#### 智能体类型

`agent/Agents.py` 中通过 `agentId` 注册了三类智能体：

| agentId | 类 | 说明 | 会话持久化 |
|---------|-----|------|-----------|
| `1001` | `RouterAgent` | 路由智能体：意图识别 + 多智能体编排 | 是（Postgres Checkpointer） |
| `1002` | `TextAgent` | 通用文本智能体：随问随答，无状态 | 否 |
| `1003` | `TJA2AAgent` | 基于 A2A 协议调用下游智能体服务 | 是（Postgres Checkpointer） |

#### 意图识别与子智能体（RouterAgent 的 LangGraph 节点）

`RouterAgent` 构建 LangGraph `StateGraph`，流程为 `START → intent_agent → 条件路由 → 子智能体 → END`，意图到节点的映射定义在 `agent/tianji/nodes/` 与 `common/Common.py` 的 `INTENT_TO_AGENT` 中：

| 节点 | 类 | 意图 | 挂载工具 | 说明 |
|------|-----|------|---------|------|
| `intent_agent` | `IntentAgent` | — | 无 | 识别用户意图（RECOMMEND / BUY / CONSULT / KNOWLEDGE / UNKNOWN） |
| `recommend_agent` | `RecommendAgent` | `RECOMMEND` | `query_course_by_id` | 课程推荐 |
| `buy_agent` | `BuyAgent` | `BUY` | `pre_place_order` | 课程购买 |
| `consult_agent` | `ConsultAgent` | `CONSULT` | `query_course_by_id` | 课程信息咨询（注入当前时间） |
| `knowledge_agent` | `KnowledgeAgent` | `KNOWLEDGE` | 无 | IT 知识讲解 |
| `unknown_agent` | `UnknownAgent` | `UNKNOWN` | 无 | 未知意图兜底 |

#### 工具

下游工具通过 MCP 客户端（`agent/mcp/MCPService.py`）动态加载，工具内部再通过 HTTP 调用业务系统网关：

| 工具名 | 说明 | 目标接口 |
|--------|------|---------|
| `query_course_by_id` | 根据课程 ID 查询课程详情 | `GET /cs/courses/baseInfo/{courseId}` |
| `pre_place_order` | 课程预下单 | `GET /ts/orders/prePlaceOrder?courseIds=` |

#### SSE 事件协议

对话接口以 `text/event-stream` 流式返回，事件结构为 `{ "eventType": <int>, "eventData": <data> }`：

| eventType | 含义 |
|-----------|------|
| `1001` | 文本内容（LLM 流式输出） |
| `1002` | 流结束（STOP_EVENT） |
| `1003` | 工具执行结果（如 `courseInfo_xxx`、`prePlaceOrder`） |
| `2001` | 错误信息 |
| `404` | 智能体不存在（agentId 无效） |

#### HTTP 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/auth/token` | 校验 `app_key` / `app_secret`，签发 JWT |
| `POST` | `/session` | 创建会话（返回会话 VO 与随机示例） |
| `GET` | `/session/hot` | 获取随机示例 |
| `GET` | `/session/history` | 查询历史会话（按当天/30天/1年/1年以上分组） |
| `PUT` | `/session/history` | 更新会话标题 |
| `DELETE` | `/session/history` | 删除会话 |
| `GET` | `/session/{agent_id}/{user_id}/{session_id}` | 查询会话详情 |
| `POST` | `/chat` | 流式对话（SSE） |
| `POST` | `/chat/stop` | 停止指定会话的输出 |

> 除 `/auth/token`、`/docs`、`/openapi.json` 外，所有接口均需通过 `RequestFilter` 中间件校验：请求头 `request-from` 必须为 `agent-center-gateway`，且 `token` 必须为合法 JWT。

#### 目录结构

```
agent_center/
├── main.py                  # 服务入口（uvicorn 异步启动）
├── application.yml          # 本地配置（端口/DB/Redis/Nacos/LLM/Agent 等）
├── environment.yml          # conda 环境依赖（Python 3.13）
├── sql/agent_center.sql     # 数据库建表脚本
├── web/                     # Web 层（FastAPI）
│   ├── WebApp.py            # 应用装配、Nacos 注册/注销、生命周期
│   ├── RequestFilter.py     # JWT + 请求来源校验中间件
│   └── routers/             # auth / chat / session 路由
├── agent/                   # 智能体层
│   ├── Agents.py            # agentId → 智能体实例注册表
│   ├── BaseAgent.py         # 智能体抽象基类、SSE 工具、Redis 停止标记
│   ├── tianji/              # 路由智能体 + 节点智能体 + 工具
│   ├── mcp/                 # MCP 客户端封装
│   └── tja2a/               # A2A 客户端封装
├── dao/                     # 数据访问层（AppDAO / ChatSessionDAO / pojo）
├── config/                  # 配置与连接管理（Nacos/Redis/DB/连接池/ID/日志）
├── common/                  # 配置 key 常量
├── util/                    # JWT / HTTP / JSON / YAML 等工具
└── vo/                      # 视图对象（SessionVO / Example）
```

#### 数据存储

- **MySQL**（库 `agent_center`）：`app_info`（应用信息，用于签发 token）、`chat_session`（会话表）；
- **PostgreSQL**：LangGraph Checkpointer 会话状态（多轮对话记忆）；
- **Redis**：会话停止标记等会话控制。

#### 启动流程

1. 初始化 PostgreSQL 异步连接池；
2. 初始化所有智能体（各自 `init()`：检查 checkpointer 表、构建 LangGraph、加载 A2A AgentCard）；
3. 注册服务到 Nacos；
4. 关闭时注销 Nacos、关闭连接池、销毁智能体。

### agent-center-gateway

Spring Cloud Gateway 微服务网关：
- JWT 认证过滤器（RSA 非对称加密）
- Redis 令牌桶限流
- Resilience4j 熔断降级
- Nacos 服务注册与配置管理

### agent_center_mcp

基于 MCP 协议的工具服务：
- 课程查询工具
- 预下单工具
- 通过 HTTP Streamable 方式暴露 MCP 端点

### agent_center_a2a

多智能体协作服务：
- **RecommendAgent**: 课程推荐
- **BuyAgent**: 课程下单购买
- **ConsultAgent**: 课程信息咨询
- **KnowledgeAgent**: IT 知识讲解
- **UnknownAgent**: 通用问题兜底

## 配置说明

核心服务的配置来源包括：本地 `application.yml`、Nacos 配置中心，以及环境变量（如 LLM API Key）。

> 敏感配置（数据库密码、JWT 密钥等）已改为 `${ENV_VAR}` 占位符引用环境变量。请复制 `agent_center/.env.example` 为 `agent_center/.env` 并填入真实值，服务启动时会自动加载该文件。

| 配置项 | 说明 |
|--------|------|
| `server.port` / `server.host` | 服务监听端口（默认 18089）与地址 |
| `db.url` | MySQL 连接 URL（`agent_center` 库） |
| `jwt.private_key` / `jwt.public_key` | JWT RSA 私钥 / 公钥 |
| `jwt.expire_hours` | Token 有效期（小时） |
| `ai.openai.model` | LLM 模型（默认 `qwen3-max`） |
| `ai.openai.api-key` | LLM API Key（环境变量 `ALIYUN_API_KEY`） |
| `ai.openai.base-url` | LLM 接口地址（dashscope OpenAI 兼容模式） |
| `ai.agent.checkpointer.postgres.url` | LangGraph 会话记忆的 PostgreSQL 连接 URL |
| `redis.host` / `redis.port` / `redis.password` | Redis 连接配置 |
| `nacos.server-addr` | Nacos 注册中心地址 |
| `nacos.discovery.name` | 服务注册名（`agent-center`） |
| `a2a.servers` | 下游 A2A 服务地址列表 |
| `mcp-servers` | 下游 MCP 服务配置 |
