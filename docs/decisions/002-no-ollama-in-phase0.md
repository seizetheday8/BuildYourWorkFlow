# 002 · Phase 0 不引入本地模型

## 决策

Phase 0 **不引入**本地小模型（Ollama），只调 DeepSeek API。

## 备选项

**引入 Ollama**
- 优点：早一步验证"本地路由"策略
- 缺点：增加环境复杂度，Phase 0 工期延长

**不引入（选中）**
- 优点：只调 DeepSeek API，简单；Phase 0 更快落地
- 缺点：Token 优化留 Phase 1

## 理由

1. Phase 0 目标是"跑通单 Agent + Token 日志"，不是"优化"
2. 本地路由是 Phase 1 的核心主题，早引入会分散注意力
3. Phase 0 结束时积累的 baseline Token 数据，
   正是 Phase 1 优化所需的对照

## 提出者

DS 提议，用户确认。

## 记录 commit

d25af81
