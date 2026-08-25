---
title: WebRetriever 交接给 Claude Code — 2026-08-25
tags:
  - project
  - webretriever
  - handoff
date: '2026-08-25'
status: active
---

# WebRetriever Challenge — 交接（2026-08-25）

> 面向后续接手的 Claude Code：本文档为「现在的情况」唯一入口，零背景可直接上手。
> 上一位接手者是 ZCode（2026-08-24 交接档见 `session-handoff-webretriever-to-zcode-2026-08-24.md`，本文件是其延续/替代）。

---

## 0. 一句话现状（TL;DR）

- 代码**已全部修复并 push 到 main**（`f4c7836`），官方评测可直接拉取。
- 模型通道已换 **aixforge 网关**（原 0x7e.vip 额度用尽），`kimi-k2.6` 不变，**全部验证 0 API 错误**。
- 本地 5 题样本验证：**3/5 答对、4/5 行为正确、0 假成功**（假成功 = SUCCESS 但答案是废话/计划的泄漏，已三重拦截）。
- 唯一还没做的事：**评测窗口内（8/27 10:00—9/2 23:59 北京时间）在提交群发 `@WR-EvalBot 提交代码`**——这是群聊操作，只能在用户侧发起。
- 2026-08-25 追加两处行为修复（过早放弃门槛统一词表 + <2 步必拦；下载数据注入块优先读取），TDD 9/9 通过，passport 单题复跑验证闭环；**已 push `3d38d0c`**。

---

## 1. 项目事实速查

| 项 | 内容 |
|---|---|
| 比赛 | 2026 WebRetriever Challenge |
| 团队 / 提交群 | 林木木 / WR-001 林木木 |
| 评测 Bot | @WR-EvalBot（提交群内 `@WR-EvalBot 提交代码`） |
| 仓库 | `hhhhhhhalf/WR-001`（GitHub Private） |
| 本地路径 | `D:\claude-work\WR-001` |
| 评测窗口 | 2026-08-27 10:00 — 2026-09-02 23:59（北京时间） |
| 当前 main | `3d38d0c`（2026-08-25 push，`f4c7836..3d38d0c`；前一个 `f4c7836` 为 2026-08-24 18:40 push） |
| 官方样题数据 | `D:\claude-work\webretriever\data\`（sample5.json 5 题、protocol3_sample15.json 15 题、example_tasks.json） |

## 2. 关键配置（config.json，仓库内）

| 字段 | 当前值 | 说明 |
|---|---|---|
| `api_base` | `https://api.aixforge.com/v1` | **2026-08-24 更换**：0x7e.vip 额度用尽（401「该令牌额度已用尽」） |
| `api_key` | 见文件本身 | 明文不写入本档；来源 = 桌面 `kimi-2.6新key.md` 第一行（aixforge 令牌，51 字符 sk- 开头） |
| `api_model` | `kimi-k2.6` | 允许列表内，合规性不受网关影响 |
| `use_dom` | `true` | DOM 文本方案（本队选定赛制） |

- aixforge 上 `kimi-k2.6` 实测可用；注意探测时 `kimi-k2.5` 报「额度不足 $0.000000」——额度疑似按模型分组，**只用 kimi-k2.6**。
- 风险提醒：评测环境用提交的 config.json，**key 必须在评测全程有额度**；评测沙箱出网访问 `api.aixforge.com` 未实测（0x7e.vip 同性质此前可用，低风险但未验证）。

## 3. 运行方式（本地复现一切）

```bash
# 1) 先起 CDP Chrome（headless，强制 1920×1080）
powershell -ExecutionPolicy Bypass -File scripts/restart_cdp_chrome.ps1

# 2) 跑官方 5 题样本（这就是"官方冒烟"）
cd D:\claude-work\WR-001
python src/agent/main.py --input D:/claude-work/webretriever/data/sample5.json \
  --output test_results/<run名> --cdp_url http://localhost:9222 --use_dom
```

- 单题调试：从 sample5.json / protocol3_sample15.json 里抽单条 task 写成单题 json 再跑（参考 `D:\claude-work\single_mit.json`）。
- 结果落盘：`<output>/<task_idx>_<task_id>/result.json` + `capture.json` + `trajectory/*.png`（1920×1080 实测）；`logs/summary.json` 汇总。
- 每题上限 100 步（官方规则，代码 total_steps=100，不要改大）。

## 4. 当前代码状态（3d38d0c = f4c7836 + 1 commit）

commit `f4c7836`「fix(agent): 赛前修复全量落地」包含（+404/-57，6 文件）：

| 文件 | 改动 |
|---|---|
| `src/agent/web_controller.py` | finished 三重拦截（动作 JSON 泄漏、计划文本、放弃语）；`_is_giveup_answer`/`_is_valid_final_answer`；外搜引擎黑名单（google/bing/baidu/duckduckgo 等，合规红线）；离屏点击防护；下载注入 `_handle_download_as_text`；`_wait_page_settled` |
| `src/agent/main.py` | 无条件页面文本注入；早放弃门限 <8 步（403/拒绝访问页直接放行）；Status 归一化到官方枚举（SUCCESS/FAIL/FAIL_SCROLLDOWN/FAIL_SAVE_SCREENSHOT_ERROR，自定义 FAIL_AGENT_GIVEUP/FAIL_NO_ANSWER/FAIL_LOOP 落盘为 FAIL）；新标签页去重；statcounter 深链 hook（CSV 下载注入） |
| `src/agent/dom_extractor.py` | 页面文本管线重构（下载注入置顶 → 12 块标题遍历 → 表格 → 正文块兑底）；**巨型文本页闸门**（>400KB 直接截断返回，防 CSV 全量渲染卡死） |
| `src/agent/prompts.py` | OBSERVE FIRST / 数据下载 / 读页面文本 / sam sfm 参数深链 / 禁止外搜 |
| `scripts/restart_cdp_chrome.ps1` | CDP Chrome 启动脚本（1920×1080） |
| `config.json` | api_base/api_key 换 aixforge |

commit `3d38d0c`「fix(agent): 过早放弃门槛统一词表+<2步必拦，下载数据注入块优先读取」（+111/-10，5 文件，2026-08-25 push）：

| 文件 | 改动 |
|---|---|
| `src/agent/web_controller.py` | 新增纯函数 `should_block_premature_giveup`（<2 有效步任何页面都拦；≥2 步且页面确为 403/封锁才放行） |
| `src/agent/main.py` | 早放弃门槛改走 `_is_giveup_answer` 统一词表（修护照题：旧门槛只查 5 个中文词，英文 "cannot" 等漏拦 → 1 步假放弃） |
| `src/agent/prompts.py` | DATA DOWNLOAD 追加「【下载数据文件内容】注入块优先读取再作答/finished」（OWID 类题） |
| `tests/test_premature_giveup.py` + `tests/test_prompt_contract.py` | 9 用例（门槛 7 + 提示契约 2，含禁止外搜红线契约），9/9 通过 |

**不要回退/绕过的关键点**：答案泄漏拦截（否则假成功刷分）、巨型页闸门（否则某题 goto 大文件会卡死整个 task）、外搜黑名单（违规会 disqualify、不只是丢分）。

## 5. 验证结果汇总（全流程 0 API 错误，aixforge 上跑的 run 用 ★ 标注）

### 5.1 sample5 旧 5 题（本地官方样本，回归基线）

| 题 | 网站 | run1基线 | run6（最终） | golden |
|---|---|---|---|---|
| MIT(11) | catalog.mit.edu | ❌ | ✅ `6.042[J]，以及（6.0001 或 Coreq: 6.009）` | 6.042[J] AND (6.0001 OR 6.009) |
| 软科(17) | shanghairanking.cn | ✅ | ✅ `复旦大学、华东师范大学、同济大学` | 同左 |
| statcounter(75) | gs.statcounter.com | ❌读错点 | ✅ `62.58%`（现网真实值；golden 0.6351 是旧数据） | live 62.58% |
| rand(28) | rand.org | ❌ | 合法放弃（403 封锁，官方认可类） | 无（403） |
| sam(86) | sam.gov | 泄漏/死循环 | 干净放弃（多次泄漏尝试全被拦截） | 608 已不存在于现网数据 |

**结论：3/5 答对、4/5 行为正确、0 假成功。**

### 5.2 protocol3 新 5 题（2026-08-24 探索验证，★aixforge）

| 题 | 网站 | 结果 | 备注 |
|---|---|---|---|
| 纵横中文网 | zongheng.com | 干净 FAIL | JS 多级分类筛选，agent 短板类型 |
| OWID | ourworldindata.org | 干净 FAIL（6 步） | 曾触发巨型页卡死（已修）；本轮未走 CSV |
| NYC311 | data.cityofnewyork.us | 中途进程外力消失（未复现） | 同筛选门户短板 |
| 护照申请量 | travel.state.gov | 干净 FAIL；08-25 修复后：step0 放弃被拦 → step3 合法退出（Cloudflare 封锁） | 站点可达性限制（golden=2025/FY2025） |
| JNTO 关西机场 | statistics.jnto.go.jp | 干净 FAIL（166 actions） | 观察点：actions 累计 166>100（无效动作多，SUCCESS 题不受影响） |

**结论：筛选门户类（纵横/NYC311/JNTO/SAM 同型）是 DOM agent 的正确性短板；失败全部干净（不假成功）。评测得分取决于官方题库构成：sample5 型（表格读数/CSV 深链）可保 3-4/5。**

### 5.3 已修复的评测级风险

1. **假成功（SUCCESS 但答案是计划/JSON 泄漏）**：run1 曾全域泄漏 → 三重拦截 → run6 归零。
2. **巨型文本页卡死**：model 自发 goto raw.githubusercontent 的 owid CSV（几十 MB 渲染页）→ JS 提取 15 分钟卡死 → 页文本闸门 → 实测 0.16s 返回。
3. **API 额度**：0x7e.vip 401「额度用尽」→ 换 aixforge（kimi-k2.6 实测可用）。
4. **status 自定义枚举**：FAIL_AGENT_GIVEUP 等不在官方枚举 → 落盘归一化为 FAIL。
5. **viewport**：强制 1920×1080（截图实测）。

### 5.4 2026-08-25 追加修复（TDD 流程，已 push `3d38d0c`）

1. **过早放弃门槛（护照题回归）**：根因 = 门槛词表远窄于最终分类器（只查 5 个中文词，英文 "cannot" 等漏拦），导致页面正常也会第 1 步就放弃。修复：`web_controller` 新增纯函数 `should_block_premature_giveup(is_giveup, effect_step, body)`——**<2 有效步任何页面都拦**；≥2 步后页面确为 403/封锁才放行；main.py 门槛改走 `_is_giveup_answer` 统一词表。
2. **下载数据指引强化（OWID 回归）**：`prompts.py` DATA DOWNLOAD（#7）追加——页面顶部出现【下载数据文件内容】注入块时，**优先读取该块再作答或 finished()**。
3. **测试**：新增 `tests/test_premature_giveup.py`（7 用例）+ `tests/test_prompt_contract.py`（2 用例，含外部搜索红线契约）→ **9/9 通过**；`py_compile` 通过。
4. **验证（passport 单题复跑，★aixforge，task 31 / golden=`2025（FY2025）`）**：
   - 旧行为：1 步干净 FAIL（页面打开、未观察就放弃，未被拦截）；
   - 新行为：`DOM 过早放弃被拦截（step 0）`（日志实证）→ 实际探索到 step 3 → 撞 Cloudflare 全站封锁 → 已 ≥2 步 + 封锁页 → **合法退出**（FAIL，agent_answer=无法完成，capture.json 网络捕获正常）。
   - 结论：早退 bug 已闭环；该题能否拿分仍受「travel.state.gov 对评测环境的 Cloudflare 封锁」限制（本地无法解，属站点可达性）。

### 5.5 2026-08-25 有效提交预演（rehearsal_20260825，3d38d0c，★aixforge）

用当前 main（3d38d0c）全量跑官方 sample5 五题，验证"提交在官方会生效"所需的一切要素：

| task | 结果 | 落盘 status | agent_answer 长度 | capture 请求数 |
|---|---|---|---|---|
| 11 MIT | ✅ | SUCCESS | 19 | 6 |
| 17 软科 | ✅ | SUCCESS | 14 | 54 |
| 28 rand | 合法放弃（403） | FAIL | 4 | 1 |
| 75 statcounter | ✅ `62.58%` | SUCCESS | 6 | 1 |
| 86 sam | 干净失败 | FAIL | 75 | 429 |

- completion_rate 100%（summary.json）；**0 API 错误、0 traceback、0 FAIL_SCROLLDOWN/截图错误**；全程 77 分钟（10:07-11:24）；进程正常退出。
- 归一化实证：28/86 落盘为 `FAIL`（不再出现自定义 FAIL_AGENT_GIVEUP / FAIL_STEP_EXCEEDED）。
- 结论：**result.json（官方枚举 + 非空 agent_answer）+ capture.json（网络捕获 >0）两项全满足 → 官方"有效提交"判定要素齐备**（区分：预演是本地模拟，最终以官方沙箱返回为准）。

#### 官方冒烟失败清单（10.6）逐项核对（2026-08-25）

| # | 官方原因 | 我们的对策 | 证据 |
|---|---|---|---|
| 1 | CDP_URL 无法连接沙箱 | 保留模板 headers 兼容；CDP URL query 自动提取 access_token | `web_controller.py` 21-105 与官方模板同源 |
| 2 | capture.json 未捕获 | context 级请求监听 + 非空兜底 | commit `7ee3cc9`；预演 5/5 capture>0 |
| 3 | 清空标签页导致浏览器关闭 | 清理时至少保留一个 page | commit `0e47a1b` |
| 4 | 模型调用失败 | aixforge key（额度至 ~2026-09-24）+ 3 次指数退避 | 预演 0 API 错误 |
| 5 | 无响应超时 | timeout=120s + 退避重试 | `agent.py` 687/843 行 |

### 5.6 2026-08-25 收盘状态（前置工作全绿，本文档此后即最终现状）

- 官方冒烟测试：**✅ 已通过**（2026-08-25，Bot 回复确认）。此后每次代码改动后、发起正式评测前需重新过冒烟。
- 前置核验（本轮全做）：10.6 官方冒烟失败 5 项逐项有对策（见 5.5 表）；CDP headers/access_token 兼容、capture/标签页修复（7ee3cc9/0e47a1b）、超时重试（timeout=120+退避）、aixforge 配额（至 ~9/24）全绿；外搜红线契约测试锁定；依赖无新增（9dd4a76 锁版本）。
- 基线校准：每轮 **100 题**、所有队伍同一套题；官方 15 题样本 = 3/15（20%）——3/5 仅对 sample5 子集成立，不可外推。构成偏表格/深链型约 20-40%，偏筛选门户型更低。
- 策略确定：窗口内每日 1 次（00:00 刷新）≈ 7 次机会、官方取最优；**8/27 当天先提交一轮锁定有效提交（= 荣誉证书）**，再按官方分数决定是否迭代。
- 开窗后执行链：用户发 `@WR-EvalBot 提交代码` → 等 Bot 返回分数与反馈 →（如要迭代）改代码 → 重过冒烟 → 次日再提交。分数若只显示"答案准确性得分"，最终以人工复核为准。
- **2026-08-25 用户动作（已发生）**：已发 `@WR-EvalBot 提交代码`（冒烟 ✅）；待 8/27 10:00 通道打开后发起「正式评测」——提交时间认定以该动作时刻为准（主索引 10.1）。自冒烟通过后仓库无任何代码改动（= 3d38d0c 未动），发起正式评测前无需重过冒烟。

## 6. 已知待办 / 风险清单（接手者按优先级）

1. **[最高] 评测窗口提交**：8/27 10:00 后，用户在提交群发 `@WR-EvalBot 提交代码`（用户操作，工具无法代发）。可先提交一轮取保底分（官方多次提交取最高分，见主索引 10.5）。
2. **[高] 额度确认**：aixforge kimi-k2.6 额度须覆盖整个窗口；额度耗尽时所有题第一步 401 = 全 0 分，致命。
3. **[中] 评测沙箱出网**：api.aixforge.com 在官方沙箱可达性未实测（低风险，0x7e.vip 同性质此前 OK）。
4. **[中] 6 道未完成题**（45615 样本外的其他官方样题或未来官方题）：如题库含筛选门户类，正确率会下降；如需提升可研究：zongheng/NYC311/JNTO 的 URL 深链参数（参考 sam 的 prompt #8b 模式：构造带筛选参数的直达 URL）。
5. **[低] JNTO actions 166>100**：无效动作计数；如官方按 actions 数判"超步"需留意（当前 FAIL 题无影响，SUCCESS 题动作数均 <20）。
6. **[低] run3 进程外力消失**：单次事件，run5/run6 均正常 EXITCODE=0，未复现。

## 7. 快速验证清单（任何修改后）

- [ ] `python -m py_compile src/agent/*.py` 通过
- [ ] 单题或 5 题测试跑完；result.json 存在且 status ∈ {SUCCESS, FAIL, FAIL_SCROLLDOWN, FAIL_SAVE_SCREENSHOT_ERROR}
- [ ] capture.json 非空（防止官方判"结果为空"）
- [ ] trajectory 截图 1920×1080
- [ ] 日志无 "Error code"（API 健康）
- [ ] 无外搜行为（日志中无 google/bing/baidu goto）
- [ ] push 前确认 config.json 仍是比赛配置（aixforge + kimi-k2.6）

## 8. 关联文档

- `WebRetriever挑战赛-主索引.md` — 项目唯一主文档（规则 10.5 评分、FAQ 对齐）
- `session-handoff-webretriever-to-zcode-2026-08-24.md` — 上一份交接（run 演进细节、修复过程）
- `webretriever-official-faq-aligned-2026-08-24` — 官方 FAQ 对齐记忆（模型允许列表等）

*交接时间：2026-08-25 · 接手上：Claude Code · 上一位：ZCode（2026-08-24）*