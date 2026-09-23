---
title: CCF BDCI 2026 · 华为 openJiuwen Agent「职场长程生存与晋升挑战」— 主索引
---

> **🏷️ 新 session 先读**：
>
> - **✅ 首日已提交（2026-09-23 08:53）**：v20（`submissions/solution-v20.zip`）已上传平台，**评测排队中、分数未出**；当时为第 2 个提交的 → 本索引 §3.4
> - **⏳ 待触发（分数出来之后）**：由 ZCode **自己到平台网页**查**他人提交数据 + 平台评分情况**，再**自主给出下一步建议** —— 用户 09-23 明确要求"**现在先不用**"去翻 → 见 [[session-handoff-jiuwen-2026-09-23]] §四
> - **2026-09-23 交接（提交后策略：抽样 vs 优化、剩余 7 次机会怎么用）** → [[session-handoff-jiuwen-2026-09-23]]
> - 2026-09-22 交接（提交前定位上传件与门禁证据）→ [[session-handoff-jiuwen-2026-09-22]]
> - ⚠️ **本索引是唯一主文档**：此后该赛题的所有新信息（提交成绩、版本迭代、判据变更）都必须追加更新到这里，新 session 从这里接续，不得只依赖会话内记忆或工作区文件。

# openJiuwen「职场长程生存与晋升挑战」— 主索引

## 1. 项目基本信息

| 项 | 内容 |
| --- | --- |
| 比赛 | CCF BDCI 2026 · 华为 openJiuwen Agent「职场长程生存与晋升挑战」（华为出题） |
| 赛题一句话 | 基于 JiuwenSwarm 框架写 Agent Skills，让 Agent 扮演 **L1 员工**在 **48 个月**职场模拟中生存并最大化职级与财富 |
| 参赛身份 | 队伍名 **大北鼻**，提交模式 `agent`（单人） |
| 工作区 | `D:\华为openjiuwen-Agent职场生存与晋升挑战\CareerSim-BDCI26` |
| 提交平台 | BDCI 竞赛平台（息壤 xir.cn），该赛题下上传 zip；**每日每队 ≤1 次，排行榜取最高分** |
| 交付物 | **单个 zip** = 技能文件夹（`skills/career-strategy/SKILL.md`，agentskills.io 规范）+ `manifest.json`（`team` / `name` / `mode`） |
| 评测模型 | 正式评测统一 **DeepSeek V4 Flash**（组委会付费）；开发调试 token 自理 |

### 关键时间节点（北京时间）

| 节点 | 时间 | 状态 |
| --- | --- | --- |
| 初赛提交窗口 | **2026/09/23 10:00 – 09/30 24:00** | 每天限 1 次，共 8 次机会 |
| 报名 / 组队截止 | **2026/09/30 12:00** | ⚠️ **上传前先确认报名已通过** |
| 初赛截止 / TOP5 入围 | 2026/09/30 24:00 | TOP5 进决赛 |
| 决赛评审 | 2026/10 月 | 复用初赛材料（需设计文档） |
| 颁奖 | 2026/10 下旬 | — |

### 评分结构

- **初赛** = 量化生存成就（**高权重**，本地可算）+ 策略工程质量（低，云端）+ 资源效能（较低，token / 时间开销）。
- **决赛** = 云端评测 **70%** + 专家评审 **30%**（需设计文档）。
- 引擎输出的 `量化分` 与「大赛折算分」关系：**折算分 = 量化分 × 0.7**（例：v20 的 74.79 → 折算 52.35）。

---

## 2. 赛题机制（**改策略前必读**）

### 2.1 主线节奏

- 每月发工资 + 处理剧情事件；**季度末（3/6/9/12 月）**分配 **3 点体力** + 选 **1 个主行动**。
- 每 **6 个月**一次绩效评估 + 晋升判断。
- 48 个月后按六维打 **D–S** 评级：职级成就 / 累计财富 / 身心健康 / 专业能力 / 风险控制 / 同事关系。

### 2.2 交互面

MCP **仅 5 个工具**：`new_game` / `observe` / `take_action` / `show_employee_handbook` / `check_latest_logs`。

### 2.3 晋升闸门语义（判据的物理基础）

- 晋升评审**只发生在 `current_month % 6 == 0` 的月份**（且需在级 ≥6 月），并在日历推进到该月的瞬间读**前一月末**状态。
- 引擎升职行的 `Lv@Mm` 标签 = **闸门月 − 1**；**台账 / 文档正文的 `Lx@Mm` 一律写闸门月**（两套口径差 1，历史误读过）。
- 引擎那条"破格提拔"的事件级改职级通道在 dev 数据集里**无数据可触发**（192 个 `.data` 文件里没有任何剧情选项的 `status_updates` 含 `level`）。
- **L1 期是整条链最脆的一环**：L1 属性上限（技 9 / 产 3 / 脉 3）**恰好等于 L2 门槛**（8/3/3），M1–M5 没有任何缓冲可攒，M5 月末的产出/人脉必须贴在上限才成立。

### 2.4 判读口径（踩过的坑，**务必照读**）

- **「零爆雷」读 `career.statistics.risk_burst_count`**（缺失即 0）。
  **不要**读 `risk_control` 维度的 raw 值 —— 那是**累计风险 = 隐藏风险 + 5 × 爆雷次数**，残余隐藏风险会被误读成爆雷（**误杀方向**）。
  由公式反推：**累计风险 < 5 ⟹ 可证 0 次爆雷**。
- 每局落定后**先冻结原始行**（`freeze_game_rows.py`）：引擎 log 表只保留最近约 5 小时；行来源缺失时链条判据记 **「未观测 = ✗」**，绝不当成通过。
- **落定标志** = 输出目录出现 `score_report.json`。

---

## 3. 当前状态与版本历史

### 3.1 出货件（定格版 v20）

| 项 | 值 |
| --- | --- |
| 版本 | `career-strategy-v20` |
| 完整彩排成绩 | **74.79 / A**（大赛折算 52.35），48/48 月存活，`completed = true` |
| 终局职级 | **L6** |
| 晋升链 | **L2@M6 → L3@M12 → L4@M18 → L5@M36 → L6@M48（赛制下的最快路径）** |
| 风险 | **零爆雷** |
| 同文本第二局 | **19.4 / E**（存活 3 个月）→ 同文本两局 **{74.79, 19.4}，极差 55.39** |

> ⚠️ **由 v20 自己的两局得出的判据修正**：**单局完整彩排分数不再构成"版本更优"的证据**。健康族候选改以**层 2 早窗抽样的早死率**为首（n ≥ 5 窗，基线 = v20 的 0/5），分数只作参考。

### 3.2 换版标准（预登记，判定只读整局记录）

候选须有**连续两局干净**的整局 —— 每局同时满足：**48/48 月**、**晋升链条不晚于 v20**、**0 次爆雷**、**`ending_score ≥ 74.79`**。
只有一局干净 → 排同文本第二局；**第二局不干净立即出局**（不补第三局）。四条里只有"零爆雷"不过 = **次优达标**（首日仍 v20）。
多候选并列时的裁决序：**M6 达标率 → 抽样轮数**。

### 3.3 候选终局（2026-09-19 → 09-20 收束）

| 候选 | 结果 | 否决理由 |
| --- | --- | --- |
| `v26` | **撤销** | 首局 75.46 四项全过，但第二局 `v26b` **22.98 / E 早死于 M24**（整局停在 L1；L2 门槛在 M9 差 1 点产出）→ 一票否决 |
| `v27` | **否决** | 69.67 / B，48/48 月、零爆雷，但 **L6 未到账**、L4@M24 与 L5@M42 各晚一窗 → "链条不晚于 v20"失败 |
| `v28` | **层 2 未过** | 早死 0/5、M6 达标 2/4 → `AMBIGUOUS`，加跑后合计 3/9 → `FAIL` |
| `v29`（合并稿） | **分支未成立** | 在"只有一个 PASS"支**不进任何提交** |

**结论：无候选拿到换版资格 → 首日（09-23）上传件 = `v20`**，机器侧收束、不再开新局。

### 3.4 提交记录（**排行榜取最高分**；每天每队限 1 次）

| # | 日期 | 提交件 | 身份 md5 | zip 字节 / md5 | 平台分数 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| **P1** | **2026-09-23 08:53** | `submissions/solution-v20.zip` | `088355a8bd53c7f7eaaa1fdb1923cb2e` | 737 094 / `50b9d8ab45b3af8c814cef3291bdce4c` | **未出** | 已上传，评测排队中（当时为**第 2 个**提交的） |

- **提交前门禁**：**9 项全绿**（含引擎 `validate` 14/14 **实测**）。提交件与 09-22 复验**同一字节**，**本轮刻意未重打包** —— 比赛要求最高分作品源码自行保存备查，重打包会覆写 zip 而抹掉"被提交的那一份"的字节原样。
- **剩余机会**：至 09-30 24:00 还有 **7 次**。

> ⚠️ **判读纪律：平台分数是"单局抽样"，不是"策略质量"的度量。**
> v20 同文本两整局的实测是 **{74.79, 19.4}，极差 55.39**；官方文档明确云端评测基座为 **DeepSeek-V4.1-Flash**（本地配同名模型是"**以便与云端评测对齐**"）→ **平台会自己重跑一局**，本地彩排分数不会搬到排行榜。**用单次平台分数当优化信号 = 拟合噪声。**

> 📐 **可争空间的量级（决定了该"抽样"还是该"优化"）**：74.79 里余下 25.21 分，其中 **22.4 分锁在「职级 / 财富的结构上限」后面**，真正可争的只有 **风险 2.00 ＋ 人脉 0.83 ≈ 2.8 分**。
> **方差（55）≈ 可优化上限（2.8）的 20 倍 → 主杠杆是"多抽样"，不是"多优化"。**

---

## 4. 上传件与门禁（每次提交前照跑）

### 4.1 待上传件

| 项 | 值 |
| --- | --- |
| 文件 | `D:\华为openjiuwen-Agent职场生存与晋升挑战\CareerSim-BDCI26\submissions\solution-v20.zip` |
| **身份 md5**（**辨认出货件只看这个**） | 包内 `solution/skills/career-strategy/SKILL.md` = **`088355a8bd53c7f7eaaa1fdb1923cb2e`**（自定格起逐字节未改） |
| zip 快照 | 737 094 B / 25 条目 / md5 `50b9d8ab45b3af8c814cef3291bdce4c`（**以 `submissions/SHIP-LOG.md` 末行为准**） |
| manifest | team `大北鼻` / name `career-strategy-v20` / mode `agent` |
| zip 根目录 | 必须是 **`solution/`**（不带前缀的 zip 解包后目录会错位，已踩过一次） |

> **为什么不能写死 zip 的 md5**：包内的 `README.md` 与 `design/` 文档也参与哈希，**每次纯文档校对都要重打包**（否则归档件与工作区不一致），zip 的字节数/md5 随之改变。**决定场上行为的始终是 `SKILL.md` 的 md5**；zip 自身的快照记在 `submissions/SHIP-LOG.md`（该文件在仓库根目录、**不在 zip 内**，所以写它不会反过来改变 zip 哈希）。

### 4.2 上传日门禁（DR 7.11(七) 的 1–5 步，顺序固定）

**任一步不过就不提交当天的新版本**（提交次数是稀缺资源，不用来做随机试验）：

1. **本地完整彩排（层 1）**：`uv run --no-sync python -m career_sim_runner play --submission solution --timeout-s 5400`
   —— 产物落在 `.career_sim_runner/career_emu/outputs/大北鼻/<UTC 时间戳>/`；验收 = 产出 `score_report.json` 且量化分 **≥ 当前定格版本分数（v20 基线 74.79）**。整局 48 个月，本地单段耗时约 **55–80 分钟**，全程无人值守。
2. **环境自检**：`uv run --no-sync python -m career_sim_runner validate --submission solution` —— 必须 **14/14 全绿**（含 `backend-reachable`）。跑前须**引擎空闲**（有 play 在跑时不要跑）。
3. **打包与解包自检**：以 `solution/` 为根打包 → 解包到临时目录 → 对**解包目录**跑离线 `validate_submission`（submission-layout / manifest-fields / skill-frontmatter 三项）→ 核对 zip 内每个文件与工作区 `solution/` **逐字节一致**。
4. **上传（账号侧动作）**：登录 BDCI26 平台上传 zip。**平台侧动作本项目无法代替** —— 与「报名 / 组队」同属队伍账号事项（截止 09-30 12:00），**提交前请确认报名已通过**。
5. **归档与留痕**：当日 zip 存入 `submissions/solution-<ver>.zip`；README 第六节版本定格表追加一行；`git add -f solution/ submissions/` 落**本地** commit（**不 push**）。

### 4.3 一键复验脚本

`%TEMP%\upload_day_selfcheck.py [zip路径] [--no-engine]` —— 一条命令打完 6 类检查（zip 根前缀 / 无重复条目 / 逐字节一致 / 解包离线 3/3 / manifest 队伍模式 / 身份 md5 与 zip 字节==SHIP-LOG 末行 / 引擎 14/14）。**`--no-engine` 先跑快的，引擎项等实例在线再补。**

---

## 5. 工作区文件地图（`D:\华为openjiuwen-Agent职场生存与晋升挑战\CareerSim-BDCI26\`）

| 路径 | 内容 |
| --- | --- |
| `solution/` | **交付源**（被 `.gitignore` 忽略，须 `git add -f`）：`README.md`（含 §六 版本定格表）、`manifest.json`、`skills/career-strategy/SKILL.md`、`design/` |
| `solution/design/decision_report.md` | **判据总账（230 KB）**：§7.11 是提交策略与全部预登记（含（七）提交日操作手册）；§7.5/7.6 是机制归因与逐维对照 |
| `solution/design/replay-game*.md` | 逐局完整复盘（game1–game13） |
| `solution/design/skills_design.md` · `survival-analysis.md` · `window-analysis.md` | 技能设计 / 生存分析 / 窗口分析 |
| `submissions/solution-v20.zip` | **出货件（待上传）** |
| `submissions/solution-v12.zip` | 历史存档件（非待上传件） |
| `submissions/SHIP-LOG.md` | **打包台账（在 zip 外）**：每包的字节/md5/条目/原因 |
| `.career_sim_runner/career_emu/outputs/大北鼻/<run_dir>/` | 逐局证据：`score_report.json` / events jsonl / transcript / `drive_attempts.json` |

---

## 6. 工程纪律与红线

### 6.1 运行

- harness：`uv run --no-sync python -m career_sim_runner <setup|validate|install|play|score|replay>`
- **全量 validate 14/14**（CLI 不打印 N/M，数 `[OK]` 行 + 读 `overall_ok=True`）；**跑 validate 前须让引擎空闲**。
- **同一 agent 同一时刻只允许一个 `play`**；落定标志 = 输出目录出现 `score_report.json`。
- 引擎实例 = **`career_emu`**：`uv run --no-sync jiuwenswarm-start --name career_emu app`（仅后端）/ `--stop career_emu` / `--list`。端口：agent_server **19092** / web 20000 / gateway 20001 / frontend 6173。
- 本机**无 `make`**；测试：`uv run --no-sync python -m pytest tests/`。

### 6.2 本机补丁（venv 重建后须重打）

- `career_emulator/storage.py`：symlink → copytree
- `career_sim_runner/ws_client.py`：`MAX_CONTINUATIONS` 20 → 200

### 6.3 红线

- **不读 `test` / `test_final` 数据集**（禁止过拟合 Dev 打 Test）。
- **不得 push** —— `origin` 指向官方仓库；只落**本地** commit。
- `solution/` 被 `.gitignore` 忽略，提交前须 `git add -f solution/ submissions/`。
- 临时脚本一律只放 `%TEMP%`，**工作区不留中间产物**。

### 6.4 打包纪律

**改到 `solution/` 内任何文档就要重打包一次** → 随后跑上传日自检出全绿证据 → 追加 `submissions/SHIP-LOG.md` 一行 → 本地 commit。**zip 的字节/md5 每次都变，只有 `SKILL.md` 的 md5 是身份。**

---

## 7. 追加记录规范

1. **版本迭代 / 提交成绩 / 判据变更** → 追加到本索引 §3，并在 `solution/design/decision_report.md` 7.11 留下对应的预登记或判读段（**预登记必须写在局产生之前**）。
2. **每次提交后** → 追加一行：日期 / 版本 / 身份 md5 / zip 字节 / validate 结果 / 层 1·2·3 证据。
3. **每次新 session 交接** → 新建 `session-handoff-jiuwen-<YYYY-MM-DD>.md`，并在本索引顶部「新 session 先读」加链。
4. **只读结论先落盘再引用**：链条 / 零爆雷等判据若行来源缺失，记「未观测 = ✗」，**不许当成通过**。