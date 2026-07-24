---
tags:
  - methodology
  - claude-code
  - loop-engineering
  - AI
title: Loop Engineering 循环工程
source: 公众号：数字生命卡兹克
url: 'https://mp.weixin.qq.com/s/omwt7d9BSFX7kotW9vo9bQ'
date: '2026-06-15'
---
## 概述

Loop Engineering（循环工程）是继 Prompt Engineering、Context Engineering、Harness Engineering 之后，AI 行业的第四个逐渐形成共识的 Engineering。由 Claude Code 创始人 Boris 和 OpenClaw 创始人 Peter 先后提出，Google 的 Addy Osmani 随后系统梳理。

**核心定义**：不再手动给 Agent 写提示词完成单次任务，而是设计自动循环，让 Agent 自动编排任务。你定义目标、验证条件、失败处理，然后放手，一切交给系统。

---

## Loop 的五个组件

### 1. 定时任务 / 触发器（心跳）

自动启动循环的机制，可以是定时跑、事件触发、或丢到 CI/CD 里。

Claude Code 支持的方式：
- `/loop` 命令按间隔自动执行
- `cron` 定时调度
- `Hook` 在 Agent 生命周期的特定节点自动触发
- 丢到 GitHub Actions 里，关掉电脑也在跑

### 2. 工作树隔离（Worktree）

同时跑多个 Agent 时，每个 Agent 有独立的工作空间，各干各的互不干扰，干完再合并。

### 3. 知识管理体系

AI 每次开新对话就丢失上下文。需要一整套方法沉淀、优化项目知识，让 Agent 每次启动时就已经知道项目。

三层结构：
- **CLAUDE.md**：全局规则和约束
- **跨会话记忆**：之前悬而未决的记录和文档路由
- **docs 体系**：完整知识和经验沉淀

关键点：因为 loop 自动跑时你不在场，知识必须干净。过期信息会让 Agent 基于错误前提做决策。CLAUDE.md 膨胀到几百行全是历史叙事，真正规则会被挤出去。

### 4. 连接器（MCP）

给 Agent 接上 GitHub、Linear、Slack、数据库等，让它在真实工作环境里干活。从发现问题到解决问题到通知人类，一条龙闭环。

### 5. 子 Agent 分工

做事的和检查的分开。写代码的 Agent 不能自己给自己打分（会对自己太宽容），必须有另一个 Agent 甚至用不同模型，专门检查前一个的输出。一个负责做，一个负责验。

---

## 核心能力：定义目标

Loop Engineering 的灵魂不是技术，是**管理能力**——把模糊意图翻译成**机器可验证的完成条件**。

### 对比示例

| ❌ 坏目标 | ✅ 好目标 |
|---|---|
| "把这个应用优化一下" | "`tsc --noEmit` 零报错，`npm run lint` 零违规，`test/auth` 全部通过" |
| "自动监控 AI 热点" | "浏览量 > 10 万算热点，每小时抓一次，按热度排序后推送" |

### `/goal` 命令的启示

同一个工具，同一个模型，区别只在于目标定义得好不好。

- 模糊目标 → Agent 要么提前停（自己觉得还行），要么一直改不停（不知道什么时候算完成）
- 精确目标 → 每轮跑验证，全过就停，没过继续，清清楚楚

---

## 目标定义四原则

### 1. 完成标准要能被机器验证
不能是"做好"，必须是"某个命令返回 0"、"某个条件成立"。

### 2. 边界条件跟完成标准一起定义
不仅要说什么算完成，还要说**不能怎么干**。防止古德哈特定律：Agent 为了通过测试直接删测试。

### 3. 要有失败的降级方案
Loop 跑挂了怎么办？不能无声无息地死掉。必须有兜底机制。

### 4. 目标要分层
大目标拆小目标，逐层验证。每一层有独立的完成标准和验证方式。

---

## 管理学视角

Loop Engineering 的核心竞争力不在工程，在管理。好的 Loop 三要素与管理学完全一致：

| 管理学 | Loop 对应 |
|---|---|
| 目标清晰 | 完成条件写得精准 |
| 资源充足 | Agent 配好 Skill、连接器、工作权限 |
| 反馈及时 | 每轮有独立检查器告诉 Agent 做得对不对 |

**古德哈特定律**：当一个衡量指标变成目标本身时，它就不再是好的衡量指标。Agent 比人类更擅长钻规则空子（比如为了测试通过直接删测试），所以边界条件（不能做什么）必须和完成标准一起定义。

---

## 四次 Engineering 跃迁

| 阶段 | 核心能力 | 对应学科 |
|---|---|---|
| Prompt Engineering | 语言表达 | 语言学 |
| Context Engineering | 信息筛选和组织 | 信息科学 |
| Harness Engineering | 系统设计和规则制定 | 控制论 |
| Loop Engineering | 目标定义和管理 | 管理学 |

---

## 来源

- 公众号：数字生命卡兹克
- 原文链接：https://mp.weixin.qq.com/s/omwt7d9BSFX7kotW9vo9bQ
- 洁癖 Skill 仓库：https://github.com/KKKKhazix/khazix-skills
