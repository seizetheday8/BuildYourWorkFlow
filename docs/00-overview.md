# 方案总览

## 1. 项目定位

个人 AI 工作流系统，服务于两类用户：
- **直接用户**：我自己，每天用它写代码、省 Token。
- **求职叙事**：作为"后端工程 + AI Agent 工程化"的核心项目，对标游戏服务器 / Agent 方向岗位。

技术主线：**Harness 工程** —— 围绕模型运转的调度、上下文、状态、预算等基础设施。

## 2. 系统架构

### 2.1 分层设计

    ┌─────────────────────────────────────────────┐
    │           Go 控制平面 (Control Plane)         │
    │  任务路由 / 预算控制 / 状态持久化 / 可观测性    │
    └────────────────────┬────────────────────────┘
                         │ gRPC
    ┌────────────────────▼────────────────────────┐
    │        Python Agent 编排层 (Orchestration)    │
    │  Supervisor ──► Code / Research / Review     │
    │  上下文管理层：语义缓存 / 压缩 / 记忆          │
    │  Agent 间通信层：结构化消息 / 增量传递         │
    └─────────────────────────────────────────────┘

### 2.2 为什么 Go + Python 双语言

- **Go 控制平面**：高并发任务调度、强类型状态管理、低延迟分发。映射游戏服务器开发能力。
- **Python Agent 层**：LangGraph 生态成熟，LLM 工具链最全。
- **分界原则**：确定性系统控制不做 LLM 调用；LLM 调用不负责系统状态。

## 3. 分阶段规划

| 阶段 | 时间 | 目标 | 关键产出 |
|------|------|------|---------|
| Phase 0 | 第 1-4 周 | 单 Agent + 上下文管理 | CLI 工具、Token 日志 |
| Phase 1 | 第 5-10 周 | Supervisor-Worker 多 Agent | Handoff 机制、结构化通信 |
| Phase 2 | 第 11-16 周 | Go 控制平面 | 调度 + 预算 + gRPC |
| Phase 3 | 第 17-22 周 | 优化打磨 | 评测报告、开源 |

## 4. Token 优化五层策略

1. **本地路由**：小模型（Ollama）判断任务复杂度，简单查询本地处理。
2. **语义缓存**：Embedding 检索相似历史查询，命中直接返回。
3. **上下文分层压缩**：L1 系统层（固定）/ L2 任务层（按需）/ L3 历史层（生命周期清理）。
4. **Agent 间通信压缩**：结构化消息替代自然语言，只传工作产物。
5. **缓存感知的上下文布局**：保持 prefix 稳定，避免 KV cache 失效。

## 5. 量化评测方案

四组对照实验：

| 实验组 | 配置 | 测量指标 |
|--------|------|---------|
| Baseline | 单 Agent 全上下文 | tokens / latency / 完成率 |
| Exp-A | + 语义缓存 | hit rate / tokens saved |
| Exp-B | + 上下文压缩 | compression ratio / 质量变化 |
| Exp-C | + 结构化通信 | 通信 token 占比 / 端到端节省 |
| Exp-D | 全部叠加 | 综合节省率 |

核心指标：
- Token 节省率 = (Baseline - Optimized) / Baseline
- 缓存命中率 = hits / total
- 延迟降低比 = (Baseline P95 - Optimized P95) / Baseline P95
- 质量保持率 = Optimized 完成率 / Baseline 完成率

评测任务集：10 个真实编码任务，每个跑 3 次取平均，人工标注完成率。

## 6. 技术栈

- **Agent 编排**：Python + LangGraph
- **控制平面**：Go + gRPC
- **语义缓存**：ChromaDB / Qdrant
- **本地模型**：Ollama（Qwen 2.5 / Llama 3.2）
- **状态持久化**：PostgreSQL + Redis
- **可观测性**：Prometheus + Grafana
- **LLM API**：Anthropic / OpenAI / DeepSeek

## 7. 待决问题

- [ ] 仓库命名（当前 working title: Code Harness）
- [ ] Phase 0 第一个真实使用场景选定
- [ ] 本地路由的复杂度判定标准
- [ ] Go 控制平面是否先做 mock 版本