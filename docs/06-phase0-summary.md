# 06 · Phase 0 总结

> Phase 0 目标：跑通单 Agent + 上下文管理的 CLI 工具，采集基线 Token 数据。
> **状态：已完成**（2026-09-23）

---

## 1. 交付物清单

| 类型 | 内容 |
|------|------|
| CLI 工具 | `harness run` / `harness stats` / `harness version` |
| 源码模块 | telemetry / llm / context / tools / agent / cli |
| 测试 | 39 个单元测试，全绿 |
| 日志 | JSONL 格式，按日期分文件 |
| 质量门禁 | pytest + ruff + mypy（strict）三项全过 |

---

## 2. 7 个 Round 回顾

| Round | 内容 | Commit |
|-------|------|--------|
| R1 | 项目脚手架 + TokenLogger | d830fc1 |
| R1.1 | ruff UP017 修复 | 63c5a6a |
| R2 | LLMClient（DeepSeek 封装） | dbcd4d5 |
| R3 | ContextManager（L1/L2/L3 分层） | 5433bef |
| R4 | Tools（文件 / 搜索 / 受限 shell） | b92fc5a |
| R5 | AgentLoop（ReAct 循环） | 4c108dd |
| R6 | CLI（run / stats / version） | 322d6d3 |
| R7 | 真实 API 跑通验证 | （手动，无 commit） |

---

## 3. 代码规模

- 源文件：15 个
- 测试文件：6 个
- 测试用例：39 个
- 依赖：pydantic / openai / pytest / ruff / mypy 等

---

## 4. R7 真实运行数据（Baseline）

**任务**：读文件 + 回答"这个函数做什么"

```
request_count:        2
total_input_tokens:   1245
total_output_tokens:  265
total_cost_usd:       0.000545
avg_latency_ms:       1964.5
```

**说明**：
- 2 次调用 = 第 1 次决定读文件 + 第 2 次基于文件内容回答
- 单任务成本约 ¥0.004
- 单次延迟约 2 秒

**这是 Phase 1 所有优化的对照基线。**

---

## 5. 关键设计决策

### 5.1 分层架构
- L1 System：系统 prompt + 工具定义，永不丢弃
- L2 Task：任务上下文，TTL 管理
- L3 History：对话历史，FIFO 优先丢弃

### 5.2 Token 记账
- 每次 LLM 调用自动记录：input / output / cache_hit / cache_miss
- 按 DeepSeek 定价区分 cache hit / miss，为后续优化保留数据基础
- JSONL 存储，按日期分文件，线程安全

### 5.3 工具安全模型
- 路径逃逸检查（resolve + relative_to）
- 覆盖写文件前自动备份
- Shell 白名单前缀匹配
- 输出截断（10K 字符）
- Shell 超时（30 秒）

### 5.4 Agent 循环
- ReAct 模式：LLM 决策 → 工具执行 → 观察追加
- 最大轮数保护（默认 10）
- 上下文预算保护（默认 32K tokens）
- tool_calls / tool 结果消息完整传递

---

## 6. 与 Phase 1 的接口

Phase 0 为 Phase 1 预留的扩展点：

| 扩展点 | Phase 1 用途 |
|--------|------------|
| ContextManager 分层 | 上下文压缩、生命周期清理 |
| LLMClient 的 logger 注入 | 语义缓存的命中记录 |
| TokenLog 的 cache 字段 | 缓存效果量化 |
| Tools 的模块化 | 新增工具（检索、执行等） |
| AgentLoop 的结构 | Supervisor-Worker 拆分 |

---

## 7. Phase 1 目标（预告）

- Supervisor-Worker 多 Agent 架构
- 语义缓存
- 上下文压缩策略
- Agent 间结构化通信协议
- 完整评测框架（对照 Phase 0 baseline）

---

*最后更新：Phase 0 完成 · v1.0*
