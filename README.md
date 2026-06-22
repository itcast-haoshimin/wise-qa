# Wise QA - AI Agent Center

基于微服务架构的AI智能体中心，提供课程推荐、购买、咨询、知识讲解等智能服务。

## 项目结构

| 模块 | 说明 | 技术栈 |
|------|------|--------|
| `agent-center-gateway` | API 网关，负责认证、限流、熔断、路由转发 | Spring Cloud Gateway, Nacos, Redis, JWT |
| `agent_center_mcp` | MCP (Model Context Protocol) 服务端，提供标准化工具调用接口 | Python, MCP, Nacos |
| `agent_center_a2a` | Agent-to-Agent 智能体服务，包含推荐/购买/咨询/知识讲解等多个 Agent | Python, OpenAI, Nacos, MCP |

## 架构图

```
客户端 → agent-center-gateway (Spring Cloud Gateway)
              │
              ├── 认证 (JWT RSA)
              ├── 限流 (Redis Rate Limiter)
              ├── 熔断 (Resilience4j Circuit Breaker)
              └── 路由 ↓
                    │
         ┌──────────┴──────────┐
         │                     │
  agent_center_a2a      agent_center_mcp
  (智能体服务)           (MCP工具服务)
         │
         └── RecommendAgent / BuyAgent / ConsultAgent / KnowledgeAgent
              │
              └── LLM (通义千问 Qwen3-Max)
```

## 各模块详情

### agent-center-gateway

Spring Cloud Gateway 微服务网关：
- JWT 认证过滤器 (RSA 非对称加密)
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

所有敏感配置均通过环境变量注入：

| 环境变量 | 说明 |
|----------|------|
| `NACOS_HOST` | Nacos 注册中心地址 |
| `NACOS_USERNAME` | Nacos 用户名 |
| `NACOS_PASSWORD` | Nacos 密码 |
| `NACOS_NAMESPACE` | Nacos 命名空间 |
| `REDIS_HOST` | Redis 地址 |
| `REDIS_PASSWORD` | Redis 密码 |
| `JWT_PUBLIC_KEY` | JWT RSA 公钥 |
| `ALIYUN_API_KEY` | 阿里云 API Key |
| `APP_HOST` | 应用 IP 地址 |
