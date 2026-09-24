# 003 · Token 观测提供 CLI

## 决策

Token 日志**存 JSONL + 提供 `harness stats` CLI 命令**。

## 备选项

**A · 只存 JSONL**
- 优点：最简
- 缺点：日常看不到"今天花了多少"

**B · 存 JSONL + CLI stats（选中）**
- 优点：日常可用 + 简历叙事 + baseline 对照
- 缺点：实现成本略高

## 理由

1. 建立 baseline：Phase 1 优化的对照基数
2. 日常可用性：用户每天需要知道 Token 消耗
3. 简历叙事：可展示的子系统
4. 实现成本低（读 JSONL + 聚合）

## 提出者

DS 提议，用户确认。

## 记录 commit

d25af81
322d6d3（CLI 实现）
