---
title: 09-22 交接（上传件已定位并复验 9 项全绿；明天 09-23 开窗上传 v20）
---

# 2026-09-22 会话交接（ZCode）

> 前置阅读：[[openJiuwen职场生存与晋升挑战-主索引]]
> ✅ **后续进展（2026-09-23）**：v20 已于 **09-23 08:53** 提交到平台，评测排队中 → 见 [[session-handoff-jiuwen-2026-09-23]]（本文档下面的"待上传"状态已被其取代）。
> **一句话状态：出货件 = `submissions/solution-v20.zip`，本日复验**上传日门禁 9 项全绿**（离线 3/3 + 引擎 14/14 含 `backend-reachable`，均为**实测**而非沿用 09-20 结论）。**明天 09-23 10:00 开窗，唯一还没做的是第 1 步完整彩排（55–80 分钟、走自己的 API 额度）；平台上传与报名确认是账号侧动作，只能由用户完成。**

---

## 一、上传件在哪（本会话的直接问题）

**要上传的就一个文件：**

```
D:\华为openjiuwen-Agent职场生存与晋升挑战\CareerSim-BDCI26\submissions\solution-v20.zip
```

不是工作区根目录，也不是 `solution/` 文件夹 —— `solution/` 是它的内容源，上传的是 `submissions/` 下那个 zip。

| 项 | 值 |
| --- | --- |
| **身份 md5**（**辨认出货件只看这个**） | 包内 `solution/skills/career-strategy/SKILL.md` = `088355a8bd53c7f7eaaa1fdb1923cb2e` |
| zip 快照 | **737 094 B / 25 条目 / md5 `50b9d8ab45b3af8c814cef3291bdce4c`** |
| manifest | team `大北鼻` / name `career-strategy-v20` / mode `agent` |
| zip 根目录 | `solution/`（唯一根前缀，无重复条目） |

**首日上传件为什么是 v20**：候选 `v26`（第二局 22.98/E 早死 M24 → 撤销）、`v27`（69.67/B 但链条未到账 L6 → 否决）、`v28`（层 2 合计 3/9 → 未过）、`v29`（"只有一个 PASS"支不进提交）**全部没拿到换版资格**，按统一收口**维持定格版本 v20**。详见主索引 §3.3。

---

## 二、本日复验证据（9 项 ALL GREEN）

用 `%TEMP%\upload_day_selfcheck.py submissions/solution-v20.zip` 一条命令打完：

| 门禁项 | 结果 |
| --- | --- |
| zip 根前缀唯一为 `solution/` | **PASS** |
| 无重复条目 | **PASS**（25 条目） |
| 条目全部位于 `solution/` 之下 | **PASS** |
| **zip 内每个文件 vs 工作区 `solution/` 逐字节一致** | **PASS**（mismatched=[] missing=[]） |
| 解包目录离线 `validate_submission` | **PASS 3/3**（submission-layout / manifest-fields / skill-frontmatter） |
| manifest 队伍 / 模式 | **PASS**（`大北鼻` / `agent`） |
| 出货身份 md5 == SHIP-LOG 末行 | **PASS**（`088355a8…`） |
| zip 字节 / md5 == SHIP-LOG 末行 | **PASS**（737 094 / `50b9d8ab…`） |
| **引擎全量 `validate`（工作区 `solution/`）** | **PASS 14/14，`overall_ok=True`**（含 `backend-reachable`） |

> 与 09-20 那次预跑的区别：**引擎那一项这次是实测**。原先 `career_emu` 实例处于 `stopped`、19092 未监听，`backend-reachable` 没法验；本会话已把实例拉起来后复跑，故 14/14 是实况结论。**出货件字节/md5 与 09-20 那次完全相同 —— 本轮没有重打包。**

---

## 三、本会话对环境做的两处改动（透明记录）

1. **启动了 `career_emu` 实例**（原先 `stopped`）。命令 = `uv run --no-sync jiuwenswarm-start --name career_emu app`（仅后端模式）；AgentServer 已在 `ws://127.0.0.1:19092` 监听。进程 = `jiuwenswarm.server.app_agentserver` + `jiuwenswarm.gateway.app_gateway`，**无 `play` 在跑、引擎空闲**（符合"跑 validate 前须引擎空闲"的纪律）。
   现已**保持运行中**，省去明天等待启动；要停：`uv run --no-sync jiuwenswarm-start --stop career_emu`。
2. **追加了 `submissions/SHIP-LOG.md` 一行（09-22 16:25 复验）**，并修正了其中两行的时间标签笔误：原写 `09-19 00:15 / 00:19`，但其内容（v27 判读落盘 / 上传前门禁预跑）与包 mtime、DR 7.11(七) 均记为 **09-20 00:1x**，故更正为 `09-20`。**修正这件事本身写进了新行的备注**，没有静默改历史。追加后重跑完整门禁，确认台账仍能被自检脚本正确解析（脚本读末行取身份与 zip 快照）。
   **该文件在 zip 外 → 出货件字节完全未动。** 目前 `git status` 只有 `M submissions/SHIP-LOG.md`，**未 commit**。

---

## 四、明天（09-23 10:00 开窗）要做的

按 `solution/design/decision_report.md` 7.11(七)，**顺序固定，任一步不过就不提交新版本**：

| 步 | 动作 | 当前状态 |
| --- | --- | --- |
| **1** | **本地完整彩排**（`play --submission solution --timeout-s 5400`，55–80 分钟，无人值守） | ❌ **唯一未做**。走自己的 API 额度；且因"同文本两局极差 55.39"，**单局分数不能当判据**，是否今晚先跑由用户定 |
| **2** | **环境自检** `validate --submission solution` → 须 **14/14** | ✅ 今天已实测全绿；明天实例已在线，重跑很快 |
| **3** | **打包 / 解包自检**（根前缀、逐字节、离线 3/3） | ✅ 今天已全绿；**只要不重新打包就沿用** |
| **4** | **平台上传**（BDCI26 平台，账号侧动作） | ⏳ 只能由用户执行；**先确认报名已通过** |
| **5** | **归档留痕**：存 `submissions/`、README §六 追加行、`git add -f solution/ submissions/` 落**本地** commit（**不 push**） | ⏳ 待做 |

**重跑门禁的快捷方式**：`python %TEMP%\upload_day_selfcheck.py submissions/solution-v20.zip`（引擎不在线时加 `--no-engine`）。

---

## 五、硬截止与提醒

- **报名 / 组队截止：2026-09-30 12:00** —— ⚠️ **上传前先确认报名已通过**，否则提交可能无效。
- **初赛提交截止：2026-09-30 24:00**；每天每队限 **1 次**，排行榜**取最高分**（所以首日就该交当日最优版本，不要留到后面试）。
- TOP5 进决赛，决赛 10 月评审并复用初赛材料，10 月下旬颁奖。

---

## 六、判读口径备忘（下次判局前必读）

- **「零爆雷」读 `career.statistics.risk_burst_count`**（缺失即 0）；**不要**读 `risk_control` 维度 raw 值 —— 那是**累计风险 = 隐藏风险 + 5 × 爆雷次数**，残余隐藏风险会被误读成爆雷（**误杀方向**）。累计风险 < 5 ⟹ 可证 0 次爆雷。
- 引擎升职行 `Lv@Mm` = **闸门月 − 1**；**台账 / 文档正文一律写闸门月**。
- 晋升评审只在 `current_month % 6 == 0` 发生，且读**前一月末**状态。
- 每局落定后**先冻结原始行**（引擎 log 表只留最近约 5 小时）；行来源缺失时链条判据记 **「未观测 = ✗」**，绝不当成通过。
- 同一 agent 同一时刻**只允许一个 `play`**；落定标志 = 出现 `score_report.json`。