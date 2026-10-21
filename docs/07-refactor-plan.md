# 07 · 重构蓝图：Agent Harness 与 LLM 网关

> **状态**：定稿（暂停开发，待 Go 语言学习完毕后启动编码）。
> **背景**：彻底废弃基于 Git 状态源与人肉中转的旧协议，转向标准化的自主编排与成本治理。

## 1. 核心架构

项目分为三大核心模块：
1. **LLM Gateway（网关层）**：拦截所有 LLM 请求，负责计费、日志、限流，并基于预算动态路由（如 Pro 降级为 Flash）。
2. **Supervisor（编排层）**：基于 LangGraph，负责任务拆解、Worker 调度与结果聚合。
3. **Subagent Workers（执行层）**：通过 IPC / MCP 协议，将本地 CLI（如 CC-DS、Codex）封装为独立的跨进程执行节点。

## 2. 技术栈选型

- **网关层**：Python (FastAPI) -> 待 Go 语言学习完毕后用 Go 重写。
- **编排层**：Python + LangGraph。
- **通信协议**：MCP（Model Context Protocol）、A2A。
- **状态存储**：PostgreSQL（持久化状态机）、Redis（计量计数器与事件总线）。
- **可观测性**：OpenTelemetry。

## 3. Phase 2 开发路线图（待启动）

- **Milestone 1：Gateway MVP**
  - 使用 FastAPI 实现一个中间件代理，拦截 OpenAI 格式请求。
  - 复用 Phase 0 的 `TokenLog` 模块，将 input/output/cost 记录到 Redis 和本地 JSONL。
  - 实现基础的降级路由（识别 prompt 长度或预算余额，动态切换模型）。
- **Milestone 2：Supervisor 编排**
  - 基于 LangGraph 实现 Supervisor 节点，定义任务拆解逻辑。
  - 编写 1 个基础的 Code Worker（使用 MCP 协议暴露工具）。
- **Milestone 3：跨进程 Subagent 桥接**
  - 编写 IPC 桥接模块，使用 `subprocess` 或本地 Socket 唤醒本地运行的 Agent CLI。
  - 实现 Supervisor 对本地 Agent 的任务委派与流式结果接收。
- **Milestone 4：Go 重写网关（进阶）**
  - 待 Go 后端（Lesson 10）学完，使用 Go + Gin/Fiber 重写网关，提升高并发处理能力。

## 4. 简历映射（重构版）

> **BYWF · Agent Harness 与 LLM 成本治理基础设施**（个人项目）
> - 将自研协议重构为 **Supervisor 自主编排 + MCP/A2A 标准协议**架构，以 LangGraph 实现 Supervisor-Worker 动态路由，以 IPC/MCP 桥接本地 Agent。
> - 将 Token 计量与成本路由下沉为 **LLM Gateway 中间件**，基于 Redis 实现实时 Token 计数器与预算控制，实测降低 LLM 调用成本 **XX%**。
> - 状态层以 **PostgreSQL 持久化状态机、Redis Streams 作为事件总线**，替代 Git 高频同步。
