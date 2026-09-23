# 05 · Phase 0 规划

> Phase 0 目标：跑通单 Agent + 上下文管理的 CLI 工具，采集基线 Token 数据。
> 本文件为 Phase 0 的设计蓝图，代码实现按第 6 节顺序推进。

---

## 1. 目标与范围

### 1.1 Phase 0 明确要做的
- 单 Agent ReAct 循环（无多 Agent）
- 上下文分层管理（L1 系统 / L2 任务 / L3 历史）
- 文件读写 + 代码搜索 + 受限 shell 工具
- DeepSeek API 统一封装
- Token 日志（JSONL）+ `harness stats` 汇总命令
- 1 个真实使用场景跑通
- 10 个真实任务的基线数据采集

### 1.2 Phase 0 明确不做的
- 多 Agent（Supervisor-Worker）→ Phase 1
- 语义缓存 → Phase 1
- 本地小模型路由（Ollama）→ Phase 1
- Go 控制平面 → Phase 2
- 完整评测框架 → Phase 1

### 1.3 Phase 0 交付物
- 可运行的 `harness` CLI 工具
- Token JSONL 日志（`logs/tokens-YYYY-MM-DD.jsonl`）
- `harness stats` 汇总命令
- 基线数据（10 个真实任务的 Token / 延迟 / 完成度）

---

## 2. 场景定义

### 2.1 目标场景
在任意 Go 项目目录下，用自然语言描述一个代码任务，工具自动完成。

### 2.2 使用方式

```bash
cd <任意 Go 项目目录>
harness run "在 handlers/user.go 里加一个 GET /users/:id 的 handler"
```

工具以**当前目录**为工作区，不做全局路径猜测。

### 2.3 为什么选这个场景
- 有真实产出（写出的代码能直接编译、运行）
- 覆盖完整链路：检索代码 → 生成代码 → 应用到文件
- 与 Go 学习进度对齐（每天有真实需求）
- 与求职叙事（Go + Agent）直接一致

### 2.4 Phase 0 验证的 3 类任务
1. **单文件加功能**：在指定文件里加一个 handler / 函数
2. **加单元测试**：为指定函数生成测试
3. **解释调用链**：跨文件追踪一个函数的调用关系

三类任务覆盖：代码生成 / 测试生成 / 代码理解。

---

## 3. 模块清单

| 模块 | 职责 | 优先级 |
|------|------|--------|
| TokenLogger | Token 日志记录与聚合 | P0 |
| LLMClient | DeepSeek API 统一封装 | P0 |
| ContextManager | 上下文分层管理 | P0 |
| Tools | 文件 / 搜索 / shell 工具 | P0 |
| AgentLoop | ReAct 循环 | P0 |
| CLI | 命令行入口 + stats | P0 |

**六个模块都是 P0**——Phase 0 不引入 P1/P2 模块，避免分散。

---

## 4. 模块接口（设计契约）

> 接口签名在实现前定死。实现代码可以后续迭代，接口不变。

### 4.1 TokenLogger

```python
class TokenLogger:
    def __init__(self, log_dir: Path): ...
    def log(self, entry: TokenLog) -> None: ...
    def session_summary(self, session_id: str) -> dict: ...
    def task_summary(self, task_id: str) -> dict: ...
```

- 存储：JSONL，按日期分文件
- 并发安全：文件锁
- 聚合：从 JSONL 读回计算
- 详细字段见实现时的 `telemetry/schema.py`

### 4.2 LLMClient

```python
class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str): ...
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs,
    ) -> ChatResult: ...
```

- 内部用 `openai` SDK（DeepSeek 兼容 OpenAI 协议）
- 每次调用自动记录到 TokenLogger
- 不暴露流式（Phase 0 不做流式）

### 4.3 ContextManager

```python
class ContextManager:
    def add_system(self, content: str) -> None: ...
    def add_task(self, content: str, ttl_turns: int = 10) -> None: ...
    def add_history(self, role: str, content: str) -> None: ...
    def build(self, max_tokens: int) -> list[Message]: ...
    def compact(self) -> CompactReport: ...
```

- 三层结构：L1 系统 / L2 任务 / L3 历史
- `build` 时按优先级拼接，超 max_tokens 触发 `compact`
- `CompactReport` 记录压缩前后 token、被丢弃段落

### 4.4 Tools

```python
class Tools:
    def read_file(self, path: str) -> str: ...
    def write_file(self, path: str, content: str) -> WriteResult: ...
    def search_code(self, pattern: str, path: str = ".") -> list[Match]: ...
    def run_shell(self, cmd: str) -> ShellResult: ...  # 白名单
```

- `run_shell` 白名单：`go build` / `go test` / `go vet` / `ls` / `cat` / `git status`
- 白名单之外一律拒绝
- 所有写操作前先备份到 `.harness/backup/`

### 4.5 AgentLoop

```python
class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        context: ContextManager,
        tools: Tools,
        logger: TokenLogger,
    ): ...
    def run(self, user_input: str) -> LoopResult: ...
```

- ReAct 循环：思考 → 工具调用 → 观察 → 继续
- 最大轮数 10（防止失控）
- 每轮结束检查是否完成；超过最大轮数则强制退出
- 全部 LLM 调用经 TokenLogger 记录

### 4.6 CLI

```bash
harness run "<task description>"
harness stats [--session <id>] [--task <id>] [--date <YYYY-MM-DD>]
harness version
```

- `run`：执行任务，输出结果 + 本次 token 消耗
- `stats`：读 JSONL 聚合展示
- `version`：显示版本和当前配置的模型

---

## 5. 目录结构

    BuildYourWorkFlow/
    ├── AGENTS.md
    ├── README.md
    ├── roadmap.md
    ├── pyproject.toml
    ├── .env.example
    ├── docs/
    │   ├── 00-overview.md
    │   ├── 01-architecture.md      # 待建（Phase 1）
    │   ├── 02-token-strategy.md    # 待建（Phase 1）
    │   ├── 03-evaluation.md        # 待建（Phase 1）
    │   ├── 04-collaboration.md
    │   └── 05-phase0-plan.md       # 本文件
    ├── src/
    │   └── code_harness/
    │       ├── __init__.py
    │       ├── config.py
    │       ├── telemetry/
    │       │   ├── __init__.py
    │       │   ├── schema.py
    │       │   └── logger.py
    │       ├── llm/
    │       │   ├── __init__.py
    │       │   └── client.py
    │       ├── context/
    │       │   ├── __init__.py
    │       │   └── manager.py
    │       ├── tools/
    │       │   ├── __init__.py
    │       │   └── base.py
    │       ├── agent/
    │       │   ├── __init__.py
    │       │   └── loop.py
    │       └── cli/
    │           ├── __init__.py
    │           └── main.py
    ├── tests/
    │   ├── test_telemetry.py
    │   ├── test_llm.py
    │   ├── test_context.py
    │   ├── test_tools.py
    │   └── test_agent_loop.py
    └── logs/                       # 本地，gitignore

---

## 6. 开发顺序（Round 制）

每轮对应一次"DS 出内容 → CC 落盘 → 验收"闭环。

| Round | 内容 | 关键产出 | 验收信号 |
|-------|------|---------|---------|
| R1 | 项目脚手架 + TokenLogger | 能记录日志 | `test_telemetry.py` 全绿 |
| R2 | LLMClient | 能调 DeepSeek API | `test_llm.py` 全绿 + 真实调用成功 |
| R3 | ContextManager | 能构建 prompt | `test_context.py` 全绿 |
| R4 | Tools | 能读写文件、搜索、受限 shell | `test_tools.py` 全绿 |
| R5 | AgentLoop | 能跑一轮完整 ReAct | `test_agent_loop.py` 全绿（mock LLM） |
| R6 | CLI | 能用命令行 | 手动跑通 `harness run` + `harness stats` |
| R7 | 真实任务 + 基线采集 | 10 任务数据 | JSONL 数据完整，stats 可读 |

**每轮通过后才进下一轮。** 不并行，不跳步。

---

## 7. 基线数据采集

### 7.1 采集方法
Phase 0 代码全部跑通后，选择 10 个真实任务，做两组对照：

| 组 | 方法 | 记录项 |
|----|------|--------|
| 手动组 | 不用 harness，用 CC-DS 或 CX 直接对话完成 | token / 延迟 / 完成度 |
| 工具组 | 用 harness 完成相同任务 | 同上 |

### 7.2 采集指标
- `input_tokens` / `output_tokens`
- `latency_ms`（端到端）
- 是否完成（人工二值标注）
- 文件修改行数
- 需要几轮对话（工具组 = AgentLoop 轮数）

### 7.3 数据用途
- Phase 0 的产出证明（README / docs 引用）
- Phase 1 优化的对照基线

### 7.4 预期
Phase 0 的**工具组不一定比手动组省 Token**——这是正常的。
Phase 0 的价值是"建立可测的 baseline"，不是"已经省了"。
省，是 Phase 1 的事。

---

## 8. 待决问题

- [ ] `run_shell` 白名单最终清单（上面给的是初版）
- [ ] ContextManager 的 L3 清理策略：按轮数还是按 token 数？
- [ ] `harness stats` 输出格式：表格 / JSON / 两者都支持？
- [ ] 首次运行如何配置 API key：`.env` 还是交互式？
- [ ] 是否保留所有对话历史到 `.harness/history/`？

---

*最后更新：Phase 0 规划阶段 · v0.1*
