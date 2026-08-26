---
title: WebRetriever 交接给 Zcode — 2026-08-26（合规修复）
tags:
  - project
  - webretriever
  - handoff
date: '2026-08-26'
status: active
---

# WebRetriever Challenge — 交接（2026-08-26）

> 面向后续任何接手者：本文档为「现在的情况」入口。上一位交接档为 [[session-handoff-webretriever-to-claude-2026-08-25]]（本文档是其延续）。

---

## 0. 一句话现状（TL;DR）

- **WR-001 已推送合规版本 `17609f8`（main 分支）**：删除全部题目特判/预设跳转代码，对齐组委会 2026-08-26 公布的「有效成绩认定」标准（逐步交互 / 实时自主 / 来源合规 + 提交代码与运行轨迹人工复核）。
- 正式评测前**必须重新过官方冒烟测试**（规则：每次代码改动后、发起正式评测前需重过冒烟；8/25 通过的是更早的 `3d38d0c`，不再适用）。
- 待办事（用户侧）：① 提交群 `@WR-EvalBot 提交代码` 重过冒烟；② 8/27 10:00 窗口开后发「正式评测」锁定有效提交。
- 已知代价：sample5 基线可能 3/5 → 2/5（statcounter 75 题原先靠被删的深链 hook 拿分）。

---

## 1. 2026-08-26 发生了什么（时间线）

1. 组委会在比赛群发布「有效成绩认定」说明：三条件（① 逐步交互：从题目指定网址开始、每步基于当前页面推理，禁止绕开界面取数据/跳预设结果/遍历网站数据接口；② 实时自主：答案由 Agent 评测中自主产出，禁止预置/缓存；③ 来源合规：仅用题目指定目标网站，禁止外部搜索引擎）+ **提交代码与运行轨迹人工复核**。
2. 上午误改仓库：Zcode 先在 `D:\claude-work\webretriever`（老参考库，7 月底 DOM 方案）里做了合规修复。**该库不是提交库，origin 甚至指向官方仓库 `Mininglamp-AI/WebRetriever`，禁止 push**（推送=公开泄露方案）。
3. 读 Obsidian 才发现正式提交库是 `D:\claude-work\WR-001`（GitHub `hhhhhhhalf/WR-001` Private）。把相同合规修复同步到 WR-001，本地单任务实测通过后 commit `17609f8` 并 push 到 main。

## 2. WR-001 合规修复内容（commit `17609f8`）

| 删除项 | 文件 | 违规性质 |
|---|---|---|
| iFixit iPad Air 3 硬编码兜底整块（直跳 `zh.ifixit.com/Device/iPad_Air_3` + 代码点 Screen Replacement 链接 + 预置答案收尾，predict_length=0） | main.py | ①跳转预设结果 + ②答案预置代码 |
| Statcounter 深链 hook（解析任务地区+月份 → 直跳 `gs.statcounter.com/...#monthly-...` + expect_download CSV 注入） | main.py | ①跳转预设结果 + 绕开界面取数 |
| `is_ifixit_task` 特判（死循环提示"请点 Screen Replacement 链接"；到达指南页即注入预置 `finished(content='...')`） | main.py | ②题目级预置路径 |
| prompts 查询示例 "iPad Air 3 屏幕更换…" | prompts.py | 复核观感风险，改中性示例 |

**保留未动**（合规）：capture.json 网络请求记录（轨迹证据）；`_handle_download_as_text`（通用下载处理，execute_dom_action 内仍有合法调用）；prompts 中模型自主 goto/深链策略指导、DATA DOWNLOAD 点击指导（模型自行决策，符合逐步交互）；外搜黑名单（f4c7836 已有，合规红线）。

## 3. 验证证据

- `py_compile` 5 文件通过；`import main` 通过；残留扫描仅剩一条 SPA 注释（"如 statcounter"，非任务特判）。
- 实测（提交前同一工作区内容）：`WR-001/output/smoke_compliance_wr001/`，iFixit 样题 `status=SUCCESS`、16 步、全模型自主导航（搜索→点击→goto→滚动→多轮 finished 被答案门控拦截后收敛）、退出码 0。
- 老库 webretriever 相同改法另测：4 步 SUCCESS（并行验证）。

## 4. 正式评测关键规则（Obsidian 已有记录，重复确认）

- 提交方式：推 GitHub 私库 `hhhhhhhalf/WR-001` main + 提交群 `@WR-EvalBot`（Bot 拉仓库跑）。
- 窗口：8/27 10:00 — 9/2 23:59（北京）；每日 1 次（00:00 刷新）；每次全量 100 题；取最优成绩。
- 限制：≤100 步/题、≤4h、禁止 bash/curl、禁止外部搜索引擎、模型版本白名单（kimi-k2.6 ✅）。
- 评分：通过任务数÷总任务数；提交时间以发「正式评测」动作时刻为准；出有效结果即获荣誉证书。
- 额度过期：aixforge kimi-k2.6 约至 2026-09-24，覆盖窗口（发起前可再确认）。

## 5. 待办（接手者按优先级）

1. **[最高·用户侧]** 重过官方冒烟：提交群 `@WR-EvalBot 提交代码`，等 Bot 回复「冒烟测试通过，环境就绪！可以发起评测了」。
2. **[高·用户侧]** 8/27 10:00 发「正式评测」，先取保底分（锁荣誉证书），再按官方分数决定是否在 `17609f8` 上迭代（迭代需再重过冒烟）。
3. **[中]** 若后续优化 statcounter 类题：应走「模型自主 goto 深链 + DATA DOWNLOAD 点击」路线（现有 prompts 策略已支持），**不要恢复代码层深链 hook**（人工复核风险），注意老库 webretriever 中的提权手段勿回迁。

## 6. 用户新增长期要求（2026-08-26 用户原话，已写入用户级 AGENTS.md，所有 session 生效）

1. **工作区洁净**：原话「不要把你的脚本，还有任何跟结果不相关的内容，明文显示在工作区」。执行：临时调试脚本、stdout 明文日志、与结果无关的探针文件不留工作区；只保留结果产物（result.json / capture.json / trajectory / 官方要求落盘材料）。
2. **禁止未完即停**：原话「禁止你任务还没干完，就停下来。我提醒你，你才能继续接着去干」。执行：任务清单未清空不得结束回合；用户说「继续」= 责令把未完成工作干完。

## 7. 关联文档

- [[WebRetriever挑战赛-主索引]] — 项目唯一主文档（规则 10.x）
- [[session-handoff-webretriever-to-claude-2026-08-25]] — 上一份交接（3d38d0c 及之前的全部状态）
- [[session-handoff-webretriever-to-zcode-2026-08-24]] — 上上份交接（run 演进细节）

*交接时间：2026-08-26 · 接手上：Zcode*