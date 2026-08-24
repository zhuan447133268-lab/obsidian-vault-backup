---
title: WebRetriever 交接文档 — 致 Zcode（2026-08-24）
tags:
  - webretriever
  - handoff
  - zcode
  - competition
status: active
---

# WebRetriever 交接文档 — 致 Zcode

> 本文档由 Claude Code 于 2026-08-24 编写，用于将 WebRetriever 正式评测前修复工作交接给 Zcode。请优先阅读本文档再继续改动。

---

## 1. 项目基本信息

| 项 | 内容 |
|---|---|
| 比赛 | 2026 WebRetriever Challenge |
| 团队 | 林木木 |
| GitHub 仓库 | `hhhhhhalf/WR-001`（Private） |
| 仓库本地路径 | `D:\claude-work\WR-001` |
| 提交群 | WR-001 林木木 |
| 评测 Bot | @WR-EvalBot |
| 当前主分支 commit | `6304f7e` |
| 模型 | `kimi-k2.6`（通过 0x7e.vip 网关，已加官方白名单） |
| 主方案 | DOM 文本方案（`--use_dom`） |

---

## 2. 当前已完成的工作

### 2.1 官方规则对齐

已读取官方 FAQ（桌面 `WebRetriever - Official FAQ.md`），关键规则同步到 Obsidian 主索引 [[WebRetriever挑战赛-主索引]] 第 10 章。

**核心规则：**

- 正式评测窗口：8月27日 10:00 — 9月2日 23:59（北京时间）
- 每日正式评测 1 次，00:00 刷新，每次全量 100 题
- 冒烟测试：8月27日前至少通过一次；每次代码改动后、正式评测前需重新通过
- 赛中 bot 反馈仅为「答案准确性」，最终成绩 = 轨迹正确性 + 答案正确性
- max steps ≤ 100，超过直接失败；总时长 ≤ 4 小时；单次模型调用 ≤ 3 分钟
- 禁止外部搜索引擎，只能用网站内搜索
- 直接 CDP 不合规，必须基于 Playwright 创建 CDP session
- 模型版本限制：`kimi-k2.6` 在允许列表内 ✅

### 2.2 已提交并 push 到 main 的修改（commit `6304f7e`）

1. **viewport 默认值改为 1920×1080**
   - 文件：`src/agent/web_controller.py`
   - 位置：`browser_window_size_width/height` 全局默认值、`launch` 模式 `new_context(viewport=...)`
   - 原因：与官方沙箱分辨率一致

2. **模型重试加指数退避**
   - 文件：`src/agent/agent.py`
   - 视觉模式：失败后等 1s → 2s → 4s
   - DOM 模式：失败后等 1s → 2s → 4s → 8s → 8s
   - 原因：避免 429/网络抖动时瞬间耗尽重试次数

### 2.3 冒烟测试状态

- ✅ 官方冒烟测试已通过（基于 commit `6304f7e`）
- 输出格式、CDP 连接、标签页清理、capture.json 均正常

---

## 3. 5 题批量本地测试结果（2026-08-24）

### 3.1 测试命令

```bash
cd D:\claude-work\WR-001
python src/agent/main.py --input D:/claude-work/webretriever/data/sample5.json --output test_results/sample5_20260824 --cdp_url http://localhost:9222 --use_dom
```

### 3.2 结果汇总

| 题号 | 网站 | 状态 | 步数 | 答案正确 | 主要问题 |
|---|---|---|---|---|---|
| 28 | rand.org | FAIL_NO_ANSWER | 1 | ❌ | 403 CloudFront 拦截 |
| 17 | shanghairanking.cn | SUCCESS | 11 | ❌ | 到目标页但数据未加载完就 finished |
| 86 | sam.gov | SUCCESS | 5 | ❌ | 搜索未执行完就 finished |
| 11 | catalog.mit.edu | SUCCESS | 3 | ❌ | 还没找到课程就 finished，输出格式混乱 |
| 75 | gs.statcounter.com | SUCCESS | 12 | ❌ | 读错数据点（87.34% vs 正确 0.6351） |

**答案正确率：0/5（0%）**

详细结果：`D:\claude-work\WR-001\test_results\sample5_20260824\summary.txt`

---

## 4. 当前最紧迫的问题

### 4.1 浏览器窗口实际只有 780×580（必须优先修）

**现象：**

```
Available screen size: 800x600
browserwindow size: 780x580
```

**原因：** 启动 Chrome 时没指定窗口大小，CDP 连接后代码读取的是实际窗口大小，导致 viewport 被设为 780×580。

**修复方法：** 启动 Chrome CDP 时强制窗口大小：

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  -ArgumentList "--remote-debugging-port=9222", `
                 "--window-size=1920,1080", `
                 "--user-data-dir=D:\claude-work\chrome-debug-profile", `
                 "--no-first-run", `
                 "--no-default-browser-check"
```

验证方法：

```bash
curl -s http://localhost:9222/json/version
```

运行测试后观察日志中的 `browserwindow size` 是否变为 1920×1080 左右。

### 4.2 模型过早调用 `finished()`（核心瓶颈）

**现象：** 多道题状态为 SUCCESS，但答案根本没拿到。模型把"下一步计划"当成了最终答案。

**典型错误答案：**

- "当前已进入哲学（010101）专业页面，但页面尚未显示院校数据，先等待动态排名和筛选控件加载。下一步等待页面更新。"
- "已进入 Contract Opportunities 搜索范围。下一步输入 `cybersecurity` 并提交搜索…"
- "我已定位到 2021–2022 学年的课程目录入口，下一步打开该年度网站并查找 6.006…"

**修复方向：**

1. **Prompt 层约束**（推荐先做这个）
   - 在 DOM prompt 中明确加入："如果你还没有拿到题目要求的最终答案，禁止调用 finished()。你只能在你已经读取到具体数值/名称/列表，并且确认这就是答案时，才调用 finished(content='答案')。"
   - 在 prompt 里给出 finished 的负面示例。

2. **代码层校验**（必须做）
   - 在 `src/agent/main.py` 的 `extract_agent_answer` 或保存结果前，检查答案是否包含"等待"、"下一步"、"先"、"还未"、"尚未"等关键词。
   - 如果包含，把状态从 SUCCESS 改为 FAIL_NO_ANSWER 或强制继续执行。

3. **动作层拦截**
   - 在 `web_controller.execute_dom_action` 处理 `finished(...)` 时，检查 content 是否为空或无效。
   - 如果无效，返回非 finished 状态，让 main.py 继续循环。

### 4.3 动态页面等待不足

**受影响题目：** shanghairanking.cn、sam.gov

**现象：** 页面 URL 正确，但数据是 AJAX/SPA 动态加载，模型没等数据出来就下一步或 finished。

**修复方向：**

1. 在 `web_controller.py` 增加通用等待函数，在关键操作后等待页面稳定：
   - 等待特定元素出现
   - 等待网络空闲
   - 等待 DOM 变化停止

2. 对 shanghairanking.cn 这类排名页，可以特化：
   - 等待表格/排名列表出现
   - 如果页面有 loading 动画，等待 loading 消失

### 4.4 答案读取错误

**受影响题目：** gs.statcounter.com

**现象：** 答案 87.34% 与标准答案 0.6351（63.51%）差距很大。

**可能原因：**

- 小 viewport 下数据点显示不全或重叠
- 模型读错了图表数据点
- 页面上有多个数据系列，模型选了错误的

**修复方向：**

1. 先修窗口大小问题，再看是否还出现。
2. 如果仍错，考虑对 statcounter 这类图表站点做特化：直接下载 CSV/数据表格而不是读图。

### 4.5 rand.org 403 拦截

**现象：** 首屏即 403 CloudFront。

**说明：** 这是网站风控/地区限制。比赛时组委会会尽量避免此类问题。本地测试可跳过或换题。

**建议：** 不优先修这个，除非比赛正式题包含 rand.org。

---

## 5. 关键代码文件说明

| 文件 | 作用 | 当前注意事项 |
|---|---|---|
| `src/agent/main.py` | 多进程调度、任务循环、结果保存 | 第 570 行 `total_steps = 100`；第 668-678 行新标签页处理；答案提取在第 807 行 |
| `src/agent/agent.py` | 模型调用、输出解析 | 第 697 行视觉模型 timeout=120s；第 840 行 DOM 模型 timeout=120s；已加指数退避 |
| `src/agent/web_controller.py` | 浏览器操控、CDP 连接、动作执行 | 第 43-44 行 viewport 默认值；第 82 行 launch 模式 viewport；第 220-243 行动态设置 viewport |
| `src/agent/dom_extractor.py` | DOM 元素提取、页面文本提取 | DOM 方案核心 |
| `src/agent/prompts.py` | Prompt 模板 | 如果要约束 finished 调用，主要改这里 |
| `config.json` | API 配置 | `api_base`、`api_key`、`api_model` |
| `environment.yml` | conda 依赖 | 已锁定版本 |

---

## 6. 本地测试标准流程

### 6.1 启动 Chrome CDP

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  -ArgumentList "--remote-debugging-port=9222", `
                 "--window-size=1920,1080", `
                 "--user-data-dir=D:\claude-work\chrome-debug-profile", `
                 "--no-first-run", `
                 "--no-default-browser-check"
```

### 6.2 检查 CDP 是否就绪

```bash
curl -s http://localhost:9222/json/version
```

### 6.3 运行 5 题测试

```bash
cd D:\claude-work\WR-001
python src/agent/main.py --input D:/claude-work/webretriever/data/sample5.json --output test_results/sample5_yourname --cdp_url http://localhost:9222 --use_dom
```

### 6.4 查看结果

```bash
python src/agent/main.py ... 2>&1 | tee test_results/sample5_yourname/run.log
```

结果文件：

- `test_results/sample5_yourname/<task_idx>_<task_id>/result.json`
- `test_results/sample5_yourname/<task_idx>_<task_id>/capture.json`
- `test_results/sample5_yourname/<task_idx>_<task_id>/trajectory/*.png`

### 6.5 结果分析脚本

已保存到 `D:\claude-work\WR-001\test_results\sample5_20260824\summary.txt`，可参考其格式重写。

---

## 7. 建议的修复优先级

### P0（必须修，影响最大）

1. **启动 Chrome 时强制 1920×1080 窗口**
2. **禁止模型在无答案时调用 finished**
   - 方案 A：改 prompt（快）
   - 方案 B：改 `extract_agent_answer` / 保存结果逻辑，过滤无效答案（稳）
   - 建议 A+B 同时做

### P1（重要，能显著提升正确率）

3. **动态页面等待**：在 click/type/goto 后等待数据加载，特别是 SPA
4. **答案有效性校验**：状态为 SUCCESS 但答案无效时，改为继续执行或 FAIL_NO_ANSWER

### P2（可选，针对特定网站）

5. statcounter 图表题：尝试下载 CSV 而不是读图
6. rand.org 403：本地测试可跳过；如比赛包含再处理

---

## 8. 已知坑与注意事项

1. **不要清空所有标签页**
   - 代码中已用 `context.pages[:-1]` 保留最后一个标签页。
   - 如果改标签页逻辑，务必保留至少一个 page。

2. **CDP 必须基于 Playwright**
   - 直接 CDP 操作不合规。当前代码使用 `page.context.new_cdp_session(page)`，符合规则。

3. **模型版本合规**
   - `kimi-k2.6` 在允许列表内。如换模型，需核对 FAQ 允许的版本。

4. **max_steps = 100**
   - 当前已设。不要改大。

5. **API Key 在私有仓库**
   - `config.json` 里有 API Key，私有仓库安全。push 时注意不要把本地调试配置覆盖。

6. **Windows fcntl 兼容**
   - 代码已做 `try: import fcntl` 兼容。本地调试不影响。

7. **冒烟测试每次代码改动后都要重新跑**
   - 在提交群发送：`@WR-EvalBot 提交代码`

---

## 9. 快速验证清单（每轮修改后）

- [ ] `python -m py_compile src/agent/agent.py src/agent/web_controller.py src/agent/main.py` 通过
- [ ] 本地单题/5题测试能跑完，result.json 非空
- [ ] 日志中 `browserwindow size` 接近 1920×1080
- [ ] 没有"清空所有标签页"导致浏览器关闭
- [ ] capture.json 非空
- [ ] 重新跑官方冒烟测试并通过
- [ ] push 到 main 前确认 `config.json` 是比赛配置

---

## 10. 关联文档

- [[WebRetriever挑战赛-主索引]] — 项目唯一主文档
- [[webretriever-official-faq-aligned-2026-08-24]] — 官方 FAQ 对齐记忆
- [[WebRetriever 协议 III 最终评测规则已确认]] — 评分规则
- [[webretriever-smoke-test-page-cleanup-fix-2026-08-24]] — 标签页清理修复记忆

---

*交接时间：2026-08-24*
*交接人：Claude Code*
*接手中：Zcode*
