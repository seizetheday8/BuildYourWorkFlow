# AGENTS.md

> 本文件是本地 AI Agent（CC / CX）进入项目时的**速查手册**。
> 详细协作规则见 [docs/04-collaboration.md](docs/04-collaboration.md)。
> 每次进入项目，先读本文件；涉及具体协作流程时，再读 04。

---

## 1. 项目一句话

个人 AI 工作流系统。目标是量化降低 Token 消耗与延迟。
技术栈：Go 控制平面 + Python Agent 编排层。

---

## 2. 四端速查

| 代号 | 端 | 职责 | 能否写仓库 |
|------|----|----|-----------|
| DS | DeepSeek 网页 | 架构、决策、文档主笔 | ❌ |
| CC | Claude Code + DeepSeek V4 | 主力编码、git、落盘 | ✅ 唯一 |
| GPT | ChatGPT 网页 | 红队审阅 | ❌ |
| CX | VSCode Codex | 验证、定位、局部实现 | ⚠️ 仅 tests/ 与仓库外 |

---

## 3. 硬规则（7 条）

1. **落盘唯一**：只有 CC 能 commit / push。其他端的输出经 CC 落盘。
2. **主笔唯一**：一份文档同一时间只有一端主笔（默认 DS）。
3. **verbatim 落盘**：CC 落盘必须逐字复制收到的内容，不得自行修改；
   发现错误只汇报，由 DS 裁决。
4. **commit message verbatim**：CC 必须逐字使用指令中的 commit message。
5. **审阅必须带 commit hash**：任何审阅请求附带精确 hash（至少 7 位）。
6. **文件所有权**：同一文件同一时间只有一个端编辑。
   - CC 主写 `src/`
   - CX 主写 `tests/` 与仓库外临时脚本
   - CX 改 `src/` 需要用户明确指令
7. **信息回流**：所有输出回流 DS，由 DS 裁决采纳/否决。
   本地端不自行采纳其他端意见。

---

## 4. 目录结构

    BuildYourWorkFlow/
    ├── AGENTS.md              # 本文件
    ├── README.md              # 门面
    ├── roadmap.md             # 里程碑与时间线
    ├── docs/
    │   ├── 00-overview.md     # 方案总览
    │   ├── 01-architecture.md # 架构详解（待建）
    │   ├── 02-token-strategy.md # Token 优化策略（待建）
    │   ├── 03-evaluation.md   # 评测方案（待建）
    │   └── 04-collaboration.md # 完整协作规则
    └── src/                   # 代码（Phase 0 时建）

---

## 5. 当前状态

- **Phase**：Phase 0 规划阶段
- **最新 commit**：见 `git log --oneline -1`
- **下一步**：见 [roadmap.md](roadmap.md)

---

## 6. 标准验证命令

> Phase 0 代码开始前为占位。代码落地后立即生效。

```bash
# 测试
uv run pytest -v

# Lint
uv run ruff check src/

# 类型检查
uv run mypy src/
```

**通过标准**：
- 所有测试绿
- `ruff` 无 error（warning 可接受）
- `mypy` 无 error

---

## 7. 任务交接格式

DS 给本地端派任务时，指令必须包含以下字段：

```text
【任务】
- 目标：<一句话>
- 负责端：CC / CX
- 允许修改文件：<具体路径或范围>
- 基准 commit：<hash>
- 验收条件：<可验证的标准>
- 禁止事项：<明确排除>
- 汇报格式：<要贴什么>
```

本地端收到指令后：
- 若字段缺失，**先汇报缺失**，不自行补充
- 若发现"基准 commit"与当前 HEAD 不一致，**停止并汇报**
- 完成后按"汇报格式"回报，不添油加醋

---

## 8. 重要文档

- [docs/00-overview.md](docs/00-overview.md) — 方案总览
- [docs/04-collaboration.md](docs/04-collaboration.md) — 完整协作规则
- [roadmap.md](roadmap.md) — 里程碑

---

*最后更新：Phase 0 规划阶段 · v0.2*
