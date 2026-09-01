---
title: 2026-08-31 WebRetriever 本地 benchmark 交接
date: '2026-08-31'
tags:
  - webretriever
  - benchmark
  - handoff
  - workbuddy
---
# 2026-08-31 WebRetriever 本地 benchmark 交接

> **状态**：当前 benchmark 因第 10 题 hang 住已中断，已评分 9 题（7/9 PASS）。
> **下一步**：由 workbuddy 接手，决策是继续跑剩余题目，还是先修渲染等待 hang 的问题。

---

## 1. 背景：本次要验证的代码

用户要求用**最新代码**跑本地 benchmark。最新代码包含以下关键 commit（按用户说法）：

| commit | 作用 | 类型 |
|---|---|---|
| `b2861d5` | DOM 覆盖度提升：page_text 1000→4000、tables 2→3/rows 4→15、content blocks 4→6、truncation 900→1200、element text 60→80 | 涨分 |
| `61a75e8` | worker 内部 Event self-healing、SOFT_FINISH_STEP 70→50 | 保分 |
| `28018bc` | 本地 benchmark + weak-match scorer | 给方向 |
| `1e63e6e` | NameError 修复：TASK_TIMEOUT_SECONDS/GLOBAL_BUDGET_SECONDS 移到 module 级别 | 让它们能跑 |
| `c178d0c` | 评分优化：false-giveup threshold 8→15、soft finish、answer nudges | 涨分（本次之前已 push） |

仓库本地路径：`D:\claude-work\WR-001`

---

## 2. 本地 benchmark 数据集

原始数据集由 workbuddy 创建：

- `D:\claude-work\WR-001\data\benchmark_tasks.json` — 20 题
- `D:\claude-work\WR-001\data\benchmark_answers.json` — 答案
- `D:\claude-work\WR-001\data\benchmark_tasks_no_olympics.json` — 19 题（过滤掉 task_idx=0 olympics.com 金牌榜题）
- `D:\claude-work\WR-001\data\benchmark_tasks_skip_stuck.json` — 18 题（再去掉 task_idx=5 Bitcoin 历史最高价年份题）

过滤原因：这两道题在当前代码下会触发**渲染等待 hang**（详见第 6 节）。

---

## 3. 运行的命令

```bash
# 运行 benchmark（当前正在跑的是 18 题过滤版）
cd D:\claude-work\WR-001
python src/agent/main.py --input data/benchmark_tasks_skip_stuck.json --output test_results/benchmark_run_skip_stuck --cdp_url launch

# 评分
python tools/benchmark_score.py test_results/benchmark_run_skip_stuck
```

> **注意**：Windows 控制台默认 GBK 编码，直接运行评分脚本会报 `UnicodeEncodeError: 'gbk' codec can't encode character '\u010d'`。需要加环境变量：
> ```bash
> PYTHONIOENCODING=utf-8 python tools/benchmark_score.py test_results/benchmark_run_skip_stuck
> ```

---

## 4. 当前运行结果

### 4.1 进度

- **总任务数**：18
- **已完成**：9
- **中断时正在跑**：第 10 题 `t_apple_rev2024`（苹果公司 2024 财年总营收）
- **中断原因**：该题在 investor.apple.com 上疑似 hang 住（详见第 6 节）

### 4.2 已完成的 9 题评分

| 状态 | 题号 | 任务 | 预期答案 | 实际答案 | 备注 |
|---|---|---|---|---|---|
| ✅ PASS | t_f500_rev1 | 财富 500 强营收第一 | 沃尔玛 / Walmart | 沃尔玛（Walmart） | |
| ✅ PASS | t_euro2024_champion | 欧洲杯冠军 | 西班牙 / Spain | 西班牙（Spain） | |
| ✅ PASS | t_wc2022_champion | 世界杯冠军 | 阿根廷 / Argentina | 阿根廷 | |
| ✅ PASS | t_oscar96_bp | 奥斯卡最佳影片 | 奥本海默 / Oppenheimer | Oppenheimer（奥本海默） | |
| ✅ PASS | t_tdf2024_winner | 环法冠军 | 塔德伊·波加查 / Tadej Pogačar | 2024年环法自行车赛总冠军是 Tadej Pogačar... | |
| ❌ FAIL | t_india_pop2024 | 印度 2024 人口 | 14.5 亿 / 1450935791 | 页面信息框显示 2023 年人口为 1,422,026,528（约 14.22 亿） | 数据年份/精度问题，不是找错页面 |
| ❌ FAIL | t_tokyo_largest_city | 全球人口最多城市 | 东京 / Tokyo | 雅加达（Jakarta），人口约 41,913,860 | 答案错误 |
| ✅ PASS | t_everest_height | 珠峰海拔 | 8848.86 米 | 珠穆朗玛峰的海拔高度是 8,848.86 米 | |
| ✅ PASS | t_forbes_richest2026 | 2026 全球首富 | 埃隆·马斯克 / Elon Musk | 2026 年全球首富是 Elon Musk... | |

**总体：7/9 = 78%**

按类型画像：
- fact：6/7 = 86%
- ranking：1/2 = 50%

完整评分报告已写入：`D:\claude-work\WR-001\test_results\benchmark_run_skip_stuck\BENCHMARK_REPORT.md`

---

## 5. 观察到的模式

1. **维基百科类事实题非常稳**：5 题里核心答案都对（印度人口那题是年份/精度问题）。
2. **新代码对重动态网站有抵抗力**：Forbes（291 个请求）、Fortune（83 个请求）都成功过掉。
3. **ranking 类题目容易翻车**：财富 500 强过了，但全球人口最多城市答错为雅加达。
4. ** investor.apple.com 类动态页容易 hang**：和 olympics.com、bitcoin 搜索页类似。

---

## 6. 渲染等待 hang 问题（关键阻塞）

### 6.1 已确认会 hang 的题目

| 题目 | 网站 | 现象 |
|---|---|---|
| t_olympics_gold1 | olympics.com | 点击金牌榜表头排序后，等待渲染完成时卡住 |
| t_btc_ath_year | wikipedia.org 搜索 Bitcoin 后的结果页 | 搜索提交后等待渲染时卡住 |
| t_apple_rev2024 | investor.apple.com | 在 investor 页面多次点击/滚动后卡住 |

### 6.2 共同症状

- 进程还活着（PID 存在）
- CPU 占用降到 0
- 日志长时间（>3 分钟）不输出
- 不是 API 超时（API 超时会报 502/timeout 并自动重试）

### 6.3 初步判断

问题出在 `wait_for_rendering_complete`（或类似逻辑）缺少一个**硬超时**。当页面是动态渲染、SPA 或表格排序时，等待条件可能永远不满足，导致无限等待。

### 6.4 建议修复方向

- 给 `wait_for_rendering_complete` 增加一个绝对时间上限（例如 10-15 秒）
- 超过上限后强制返回当前页面状态，让 agent 继续决策
- 如果连续多次等待超时，触发浏览器 reset 或换策略

相关文件：`src/agent/web_controller.py`、`src/agent/agent.py`

---

## 7. 待 workbuddy 决策

1. **是否继续跑剩余 8 题？**
   - 选项 A：跳过苹果题，再建一个 `benchmark_tasks_skip_stuck_and_apple.json`（17 题），把剩余题目跑完。
   - 选项 B：先修渲染等待 hang，再全量重跑 18 题或 20 题。
   - 选项 C：不跑了，基于当前 9 题结果评估是否需要继续优化代码。

2. **是否需要修印度人口/城市人口这类 ranking/fact 题的精度？**
   - 印度人口：agent 取到 2023 年数据，预期 2024 年；可能需要 prompt 里强调"最新/2024 年"。
   - 城市人口：agent 答雅加达，可能和 Wikipedia 列表口径有关。

3. **是否需要把本地 benchmark 跑通流程化？**
   - 当前命令需要手动处理编码问题、手动过滤 hang 题，建议脚本化。

---

## 8. 关键文件路径速查

```
D:\claude-work\WR-001\src\agent\agent.py              # 模型交互 + 动作解析
D:\claude-work\WR-001\src\agent\web_controller.py      # 浏览器操控 + 渲染等待
D:\claude-work\WR-001\src\agent\main.py               # 多进程调度
D:\claude-work\WR-001\tools\benchmark_score.py        # 评分脚本
D:\claude-work\WR-001\data\benchmark_tasks.json       # 原始 20 题
D:\claude-work\WR-001\data\benchmark_tasks_skip_stuck.json  # 18 题过滤版
D:\claude-work\WR-001\test_results\benchmark_run_skip_stuck  # 当前运行结果
D:\claude-work\WR-001\test_results\benchmark_run_skip_stuck\BENCHMARK_REPORT.md  # 评分报告
```

---

## 9. 本次操作时间线

- 16:24 — 启动 18 题 benchmark run
- 16:26 — 遇到 API 502 Bad Gateway，自动重试后恢复
- 16:28~16:49 — 快速完成前 9 题
- 16:49 — 进入第 10 题苹果营收
- 17:02 — 苹果题最后一条日志，之后 3 分钟无输出
- 17:05 — 判断 hang 住，中断 benchmark
- 17:06 — 完成 9 题评分，结果 7/9 PASS

---

## 10. 关联笔记

- [[WebRetriever挑战赛-主索引]]
- [[webretriever-2026-08-31-day2-7-push-c178d0c]] — Day2-7 提分改动
- [[webretriever-2026-08-30-timeout-fix-smoke-passed]] — 超时修复官方冒烟通过
- [[webretriever-2026-08-30-three-review-fixes-landed]] — 评审问题修复

---

## 11. workbuddy 接手处理（2026-08-31 17:20）

### 11.1 渲染等待 hang：根因确认 + 已修复

交接第 6 节的"初步判断"方向正确，但**具体位置需要修正**——不是"缺少硬超时"这么简单，而是一个**假保护**：

- `wait_for_rendering_complete`（`src/agent/web_controller.py`）用 `page.evaluate()` 返回 **Promise** 做"滚动高度稳定"检测，外层包了 `_with_action_timeout(page, 5000, ...)` 看似有 5s 兜底。
- 但 `_with_action_timeout` 的实现是临时下调 `context.set_default_timeout()`，而 **Playwright 的 `evaluate()` 不受 default timeout 约束**（default timeout 只作用于 action / navigation / `wait_for_*`）。→ **这个兜底对 evaluate 完全无效。**
- 于是：页面主线程卡顿、或等待期间执行上下文被销毁时，Promise 永不 resolve，`evaluate` 无限阻塞 → 整个 worker 挂死。完美对应三条症状（进程活着、CPU 0、无日志、非 API 超时）。
- **全仓 grep 确认：这是唯一的 `new Promise`，即唯一一处无界等待**，其余 `evaluate` 均为同步 JS。位置与观测到的 3 例 hang 完全吻合。

**修复（commit `02a34a7`）**：把该检测从 `evaluate + Promise` 改为 `page.wait_for_function(polling=200, timeout=3000)`——超时由 Playwright **客户端侧强制**，必定抛 `TimeoutError`，从而保证整个函数有界。

修复后 `wait_for_rendering_complete` 全部调用均有界：30s(load) / 10s(domcontentloaded) / 3s(高度稳定) / 5s(有内容) + 外层兜底 5s。

**行为影响（回归风险评估）**：健康页面几乎不变（原逻辑 100ms×最多6次≈600ms；现 200ms 轮询、连续两次高度一致即返回≈200–400ms）。动态/卡死页面最多等 3s 后跳过该检测继续，不再挂死。**对已通过的题无负面影响，只把"挂死=0 分"变成"继续尝试"。**

### 11.2 第 7 节三项待办的决策

| 待办 | 决策 | 理由 |
|---|---|---|
| **7.1** 继续跑剩余题 / 先修 hang / 不跑了 | **先修 hang（已完成）→ 再跑全量 20 题验证** | 见 11.1。修完后必须跑**全量 20 题（含原先被过滤的 olympics / bitcoin / apple）**，这才是验证修复是否生效的唯一方式——若这 3 题现在能跑完，即证修复有效 |
| **7.2** 修 ranking/fact 精度（印度人口年份、城市人口答错） | **不做（推迟）** | 仅 2/9 个噪声点，且都是英文 Wikipedia 域；官方题是中文排名/趋势 + 重 JS 站。盲改 prompt 有回归风险且无法度量收益。hang 修复影响**所有**题型，收益远大于调这两个点 |
| **7.3** benchmark 流程化 | **已做** | 新增 `tools/run_benchmark.py`：一键跑 agent + 评分，子进程强制 `PYTHONIOENCODING=utf-8`（解决 Windows GBK `UnicodeEncodeError`）。用法见下 |

### 11.3 ⚠️ 最重要的校准：benchmark 78% 不能外推官方

**7/9 = 78% 与官方 2/100 的鸿沟，说明基准集系统性偏简单、且域不同**：

- 基准集 = 8 题 Wikipedia（静态、英文、干净）+ 12 题真实站；已完成的 9 题多为 Wikipedia/事实题。
- 官方题 = 中文事实/排名/趋势 + 重 JS 动态站（maoyan、stats.gov.cn 类），答案在表格/图表里。

→ **基准集的定位必须是「回归检测 + 找机械性 bug」，不是「官方分数预测器」。** 它这次的最大价值正是发现了 hang 这个真 bug。后续迭代**不要**以"benchmark 涨到 X%"为目标，那是自我安慰。

### 11.4 更新后的命令

```bash
cd D:\claude-work\WR-001

# 一键跑全量 20 题（验证 hang 修复，含原先卡死的 olympics/bitcoin/apple）
python tools/run_benchmark.py --input data/benchmark_tasks.json --output test_results/benchmark_full

# 只评分（不重跑 agent）
python tools/run_benchmark.py --score-only test_results/benchmark_full
```

### 11.5 待用户执行（9/1 前）

1. `git push origin main`（当前 ahead 1 = `02a34a7`）。
2. 群内 `@WR-EvalBot 提交代码` → 冒烟须 3/3（验证 hang 修复未破坏构建）。
3. 本地跑全量 20 题基准，确认原先 3 道 hang 题现在能完成 → 佐证修复生效。
4. 冒烟过 → `@WR-EvalBot 开始评测`（剩 9/1、9/2 两次，取最优）。
