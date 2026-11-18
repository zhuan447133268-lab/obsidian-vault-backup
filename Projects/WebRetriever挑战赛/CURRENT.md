---
title: WebRetriever挑战赛 · 当前状态
date: '2026-11-17'
status: active
tags: [project, webretriever, current-state]
---
# WebRetriever挑战赛 · 当前状态（CURRENT）

> **接手入口，一屏内**。交接时**先覆写本文件**，再写长 handoff。
> 最后更新：2026-11-17（依据 8-31 最新交接；主索引文件 10-15 有零星改动，接手时扫一眼顶部）。失效条件：下次交接未覆写本文件。

## 现在在哪
正式评测窗口（8/27–9/2）已过，官方提交已发。当前挂起的是**本地 benchmark**：18 题跑至第 10 题 `t_apple_rev2024` 在 investor.apple.com **hang 住中断**，已评分 9 题 **7/9 PASS**（fact 6/7、ranking 1/2）。待决策：先修渲染等待 hang，还是继续跑剩余题。

仓库 `D:\claude-work\WR-001`。历史代码参考 `D:\claude-work\webretriever`。模型通道已从 0x7e.vip 换 **aixforge**（kimi-k2.6 不变）。

## 下一步（最多三件）
1. 修渲染等待 hang：`t_apple_rev2024` 与 task_idx=5（Bitcoin 历史最高价年份）会触发，当前靠 `benchmark_tasks_skip_stuck.json`（18 题）绕过——查根因而不是继续删题。
2. 决定是否跑完剩余 9 题；评分脚本在 GBK 控制台要加 `PYTHONIOENCODING=utf-8`。
3. 用户长期在验证 **Kimi K2.6 视觉模型在 iFixit 页面上的 agent 效果**，交接档写在仓库侧 `handoff_to_workbuddy.md`（不在本库），接手前先确认那份是否更新。

## 红线（别踩）
- **禁止外搜**（google/bing/baidu/duckduckgo 等），违规是 disqualify、不只是丢分。
- 答案泄漏拦截（动作 JSON / 计划文本 / 放弃语）**别绕过**——否则假成功刷分。
- 巨型文本页闸门（>400KB 截断）别删，删了某题 goto 大 CSV 会卡死整个 task。每题上限 100 步，不要改大。

## 现行入口
- [[2026-08-31 本地benchmark交接-待workbuddy接手]] — **最新交接**，含 hang 分析与已评分明细。
- [[WebRetriever挑战赛-主索引]] — 唯一主文档，顶部有最新交接指针。
- [[session-handoff-webretriever-to-claude-2026-08-25]] — 提交前状态（⚠️ 已被 8-26 / 8-31 交接替代，仅作历史）。
