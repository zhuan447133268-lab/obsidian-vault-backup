# 考试平台演进 · P1 类型化基础字段与题库（2026-11-02）

> 接 P0 记录 [[lab-exam-2026-11-02-exam-platform-p0-baseline]]。本文是 P1 完工记录，含**执行结果、与指令的偏差、以及一处比评审预期更严重的既有缺陷**。
> 分支 `feat/exam-platform`，提交链：`9307520`（P0）→ `45f472b`（P0.5）→ `afe5f92`（P1）。`main` 仍为 `aaa994e`，未动。

---

## 0. 结论速览

| 项 | 结果 |
|---|---|
| P1 验收 `bash scripts/run-acceptance.sh P1` | **失败计数 0**（冒烟 23/23、jest 154 passed / 8 skipped、双端 build ✓、库断言 19/19、基线 00/99 不漂移） |
| exams 存量 41 场 | 全部 `exam_type='LAB_ENTRY'` / `paper_config_version=1` / `score_visible_at=NULL` |
| 题库回填 | 2001/2001 题 `bank_id` 指向内置 LAB 库；`labQuestionCrc` 仍 `49371640` |
| 迁移链自足性 | 空库 `deploy` 连跑 2 次（10 条）→ 第二次 "No pending migrations"；`migrate diff` 与 schema.prisma **同构（输出空迁移）** |
| 账本 | dev：applied 8 → 10；物理行 11（含 1 条 rolled_back 历史行） |
| 旧三模块写死逻辑 | 一行未动（5 处指纹仍在：870 / 989 / 1080 / 478·589·755 / 434） |

---

## 1. 做了什么（按指令顺序）

### 第 0 步 · 两个脚本缺陷（`45f472b`）
1. `scripts/baseline.sh` 的 `node - "$TMP_KV" "$ROOT"` 补上 `"$@"` —— 评审实测对：修前 `--check` 恒写盘、漂移检测从未运行。**修后反向验证**：手改 `labQuestionCrc` → `--check` 报漂移 exit 1；还原 → exit 0，且 check 模式不再打印「已写入」。
2. `run-acceptance.sh` 03/05 步改为判退出码（`|| note_fail`）。用 `node -e "process.exit(7)"` 造零输出的假 crash 验证过：改前会假绿，改后强制 ❌。

### 第 1 步 · 迁移账本（C6 落地）
```
npx prisma migrate resolve --applied 20260807000000_add_missing_timestamps
npx prisma migrate resolve --applied 20260907000000_add_exam_audience
```
`migrate status` → `Database schema is up to date!`

**实测修正一个细节**（与指令预期不同）：对「失败记录」执行 `resolve --applied` 时，Prisma 会先把那条失败行标记 `rolled_back_at`、**再补插一条新的 applied 行**，不做原地更新，也没有重放 SQL（无 1060）。所以：
- 物理行数 7 → **9**（不是 8）；`rolled_back_at IS NULL` 的 applied 计数 = **8**（这才是 Prisma 口径）。
- 已把 `baseline.sh` 与 spec 的迁移计数改成 `WHERE rolled_back_at IS NULL`，并在 DEPLOY 写明「按 applied 口径查，别按物理行数查」。
- 正式库 2026-09-18 是空表逐条补录 8 条，没有失败行，物理行 = 8 = applied；P1 后为 **10**。

### 第 2 步 · P1 迁移
`migrate dev --create-only` 在本机跑不了（Prisma 判定非交互环境，直接报错退出）。改用等价且更可审的路径：
1. `prisma migrate diff --from-migrations prisma/migrations --to-schema-datamodel prisma/schema.prisma --shadow-database-url <空库> --script` 生成 SQL；
2. **人工逐条读**（这一步就是评审 Q4.3 的闸口）；
3. 手写迁移目录 + 回填，`prisma migrate deploy` 应用。

迁移内容（`20261102020000_p1_exam_type_question_bank`）严格只有：
- `exams` + `exam_type VARCHAR(32) NOT NULL DEFAULT 'LAB_ENTRY'`
- `exams` + `paper_config_version INT NOT NULL DEFAULT 1`
- `exams` + `score_visible_at DATETIME(3) NULL`
- `question_banks` 新表（id/name/type/owner_college_id/created_at）
- `questions` + `bank_id VARCHAR(36) NULL` + 索引 + 外键（ON DELETE SET NULL）
- 内置 LAB 库 `INSERT … ON DUPLICATE KEY UPDATE`（固定 id `1ab00000-0000-4000-8000-000000000001`）
- 回填 `UPDATE … WHERE bank_id IS NULL AND category IN ('GENERAL_SAFETY','PROFESSIONAL','GENERAL_EDU')`

### 第 3 步 · 自足性验收
空库 `lab_exam_p1_clean` → `deploy` 10 条 → 再 `deploy`「No pending」→ `migrate diff` 输出 `-- This is an empty migration.`；库内 17 表、`question_banks` 恰 1 行（中文名「实验室准入题库」无乱码）、`teacher_classes_class_id_key` 唯一索引存在。

### 第 4 步 · 业务验收
`run-acceptance.sh P1` 全绿。补充**三方对拍**（冒烟卷 `f62c2875…`）：
- 接口回执：25 题 / 10 单 10 判 5 多 / 100 分 / 无重复
- SQL 直算：`paper_questions` 25 行、`COUNT(DISTINCT question_id)=25`、`SUM(score)=100`、SINGLE 10 / JUDGE 10 / MULTIPLE 5、25 行全部 `bank_id` 非空
- 手算预期：`buildPaperConfig` 的 25/100/4 分 × 25 = 100、10+10+5 = 25
三路一致。且**旧代码建的考试**（未传 exam_type）自动落 `LAB_ENTRY`/`pcv=1`，证明「新列不参与旧逻辑」。

### 第 4 步补充 · 浏览器端到端复验（11:17–11:20）

用 P1 构建产物起 `vite preview`（4173）+ `dist/main.js`（3000，`AUTH_MODE=cookie`），连 P0 克隆库 `lab_exam_p0`，真实浏览器跑一遍：

| 检查 | 结果 |
|---|---|
| `admin` 登录 → 跳 `/school-admin` | ✅ 首页 8 学院 / 8474 学生 / 275 教师 / 2001 题目 |
| `/school-admin/questions` | ✅ 表格正常渲染 2001 题（`bank_id` 新列未影响查询） |
| `/school-admin/certificates-export` | ✅ 列表带出 P0 冒烟证书 `LAB-2026-GS-2pnjrDt7` |
| 页面内 network | `/api/exams?pageSize=200` 200、`/api/questions` 200、`/api/certificates/admin/list` 200 等 **11 条全部 2xx** |
| 旧接口契约 | `/api/exams` 返回字段与 P1 前**完全一致**（无 examType 等新键泄漏）——旧 DTO 未动 |
| 经重生成的 Prisma Client 查库 | 42 场考试全 `LAB_ENTRY`/`pcv=1`/`score_visible_at=NULL`；2001 题 `bank_id` 无空；`question_banks` 1 行 |

截图：`gui-test-screenshots/2026-11-02-p1-schema-preview/01~03`，接口与查库明细 `04-api-checks.txt`（同目录）。

### 第 4 步补充 2 · Claude Code 评审意见回填（12:00–12:05，commit `6c172ee`）

把 P0 笔记 §10 的 12 条评审项逐条对照 P1 的实际交付，**10 条在主流程已闭环，最后 2 条今天补完**：

| 评审项 | 处置 |
|---|---|
| 10.4 🟢 冒烟证据噪音（P0 时 533 行 ioredis ECONNREFUSED） | 已修：`run-acceptance.sh` 新增 `collapse_smoke_noise()`，重复行折叠成一行计数，原文另存 `02-smoke.raw.txt` 便于排查。实测 13 行 → 1 行，断言输出不再被淹；全量重跑失败计数仍 **0** |
| Q4.1 更强自足性口径 `migrate reset --force` | 已补：scratch 库 `lab_exam_p1_reset` 一次性重放 10 条迁移 → 17 表 / applied 10 / `question_banks` 1 行 / `teacher_classes_class_id_key` 存在 / `paper_generation_jobs` 存在 / `exam_type` 默认 `LAB_ENTRY`；随后 `deploy` 报 No pending。证据 `evidence/P1-20261102/03-clean-reset.txt`，跑完已 drop |

其余项（10.2 / 10.3 / Q1 / Q2 / Q3 / Q5 / Q6 / 10.6 全部、Q4.2–Q4.4）在 P1 主流程已执行，见第 1–3 节。**唯一被现实推翻的是 10.6.3 的「P1 后正式库 9 条」**：迁移链不自足、多出 reconcile 迁移，实际是 10 条（见第 2 节）。

> 补充：本次重跑也把 `baseline.json` 的 `commit` 字段从 `45f472b` 刷新到 `afe5f92`（其余数值零漂移，`--check` 通过）。

### 第 4 步补充 3 · P1.2：评审 §3.3 闭环 + 顺带查出「02 步证据假绿」（14:00–14:15，commit `47747cc`）

Claude Code 复核记录（[[lab-exam-2026-11-02-exam-platform-p1-claude-review]]）§3.3 指出 ioredis 折叠只吞头行、**26 行栈帧仍留在 02-smoke.txt**。修的时候按「证据必须可复核」往下追，发现了比 §3.3 严重得多的既有缺陷：

| # | 问题 | 实测 | 处置 |
|---|---|---|---|
| 1 | §3.3 折叠不全 | 每个事件尾随 2 行 `at internalConnectMultiple/afterConnectMultiple` 未匹配，26 行残留 | awk 补 `node:net` 栈帧模式 + RedisService 降级行（ANSI 容错 `/RedisService\]/ && /Redis connection (error\|failed)/`） |
| 2 | **02 步证据假绿（新发现）** | 后台服务日志与冒烟输出同时 append 同一文件，Windows/MSYS 互相覆盖：冒烟 36 行**只落 16 行**、控制台 23 条断言文件里一条没有，而**退出码仍是 0**，验收判绿 | 改为「一个文件只有一个写者」：服务日志独立 `02-server.log`，服务停止后顺序合并进 `02-smoke.txt` |
| 3 | 只判退出码，冒烟没跑也算过 | 用 `node -e "0"` 替换冒烟（静默成功）→ 旧逻辑仍绿 | 新增正向证据门槛：`✅` 断言 < 20 条即 `note_fail`。负向验证结果：失败计数 **1**、exit **1** |

复验（真实脚本全量重跑）：失败计数 0，`02-smoke.txt` 152 行 / **24 条 ✅**（23 断言 + 全绿行）、栈帧残留 **0**，`02-smoke.raw.txt` 保留全量原文（13 头行 + 26 栈行）；服务日志以 `===== 后端启动/运行日志 =====` 分隔附在冒烟之后。`baseline.json` 锚点随之刷新到 `6c172ee`（库事实零漂移）。

> 排查手段备忘：`tee` 与 `cat >>` 两种写法都复现丢写 → 用「双目标 tee（证据文件 + `$TEMP` 镜像）」判定 `tee` 收齐数据、问题在并发写；再用 `wc -l` 探针在 pipeline 结束后立刻计数，排除是 fold 阶段丢的。**结论是文件级并发写，不是 tee 的锅**（第一版注释曾写错归因，已改）。

---

## 2. 意外发现：迁移链从来就不自足（比评审预判更严重）

第一次 `migrate diff` 不是空的，暴露出 6 处**与 P1 无关的既有漂移**——迁移链从零重放得到的是 **14 张表**，而真实库是 15 张业务表：

| # | 漂移 | 真实库 | 迁移链重放 | 处置 |
|---|---|---|---|---|
| 1 | `paper_generation_jobs` 整张表 | 存在（12 行数据） | **完全没有** | 补 `CREATE TABLE IF NOT EXISTS` |
| 2 | `teacher_classes.class_id` 唯一索引 | 存在 | 缺失 | 动态 SQL 幂等补建 |
| 3 | `classes/colleges/majors/student_attempts.updated_at` 默认值 | `CURRENT_TIMESTAMP(3)` | 无默认值 | 补 `MODIFY` |
| 4 | `teacher_classes.updated_at` 默认值 | 无 | `CURRENT_TIMESTAMP(3)` | `DROP DEFAULT` |
| 5 | `user_roles.created_at/updated_at` | 存在 | 存在 | **datamodel 漏登记**（schema.prisma 没有这两字段）→ 补登记，不删库列 |
| 6 | 账本 `20260807` 失败记录 | — | — | 见第 1 步 |

后果与处置：
- 若直接发版，`migrate deploy` 在**空库/新环境**上会少建 `paper_generation_jobs`，`PaperGenerationJob` 相关接口全挂；这正是 2026-09-18 正式库「有表但不在任何迁移里」的同一个病根。
- 已新增独立迁移 `20261102010000_reconcile_chain_drift` 把链补齐（对已有库基本 no-op）。**没有把它塞进 P1 迁移**，保持 P1 迁移可逐条审。
- 因此 applied 迁移数是 **10**（8 + reconcile + P1），不是指令预期的 9。DEPLOY / RELEASE_CHECKLIST 已按 8 → 10 改，并加了发版前硬校验（见下）。

---

## 3. 与指令的偏差（逐条认账）

| # | 指令 | 实际 | 原因 |
|---|---|---|---|
| 1 | `migrate dev --create-only` 生成迁移 | 改用 `migrate diff` + 手写目录 + `migrate deploy` | Prisma 在本机判定「non-interactive environment」直接拒绝；diff 生成的 SQL 与 create-only 同源，且人工审更彻底 |
| 2 | 账本 7→8 | 7→8 applied（物理 9） | `resolve --applied` 对失败行的实现是「标记 rolled_back + 补插 applied」，已在脚本/文档统一按 applied 口径 |
| 3 | P1 迁移只有 3 列 + 表 + bank_id + 回填 | 是；另加一条独立 reconcile 迁移 | 迁移链不自足（第 2 节），不修则第 3 步验收不可能过 |
| 4 | 不改旧逻辑 | 是；但 schema.prisma 的 `UserRoleRel` 补登记了 2 个**库中已存在**的字段 | 否则 datamodel 与库永久不同构；补登记不产生任何 DDL |

---

## 4. 顺手修掉的第三个脚本缺陷（未在评审清单里）

`run-acceptance.sh` 的 `cleanup()` 只 `kill` 子 shell，Windows 上**杀不掉 node 子进程**：P0 验收残留了一个占用 3100 端口的服务（`dist/main.js`，创建时间正是 P0 验收时刻）。危害是下一次验收的 health 探测会命中**旧构建进程** → 冒烟假绿。

修复：新增 `kill_port()`（`netstat -ano` 找 PID + `taskkill /F`），02 步起服务前先清端口并断言端口已空闲，`cleanup` 里也按端口清。孤儿进程已终止。

---

## 5. 发版前置（正式库，交给运维）

正式库与 dev 的起点不同，**不要照抄 dev 的数字**：

1. 查账本：`SELECT COUNT(*) FROM _prisma_migrations WHERE rolled_back_at IS NULL;` **应为 8**（2026-09-18 补录的 8 条，无失败行）；不足先补登记，否则 P3009。
2. `teacher_classes` 重复检查：`SELECT class_id, COUNT(*) c FROM teacher_classes GROUP BY class_id HAVING c > 1;` **必须为空**——reconcile 迁移要建唯一索引，有重复行会失败。
3. `paper_generation_jobs` 存在性：`SHOW TABLES LIKE 'paper_generation_jobs';` 应 1 行（历史手工建，已进链并做 IF NOT EXISTS 兜底）。
4. `migrate deploy` 后会新增 2 条 → applied **10**。
5. 硬校验：`migrate diff --from-migrations … --to-schema-datamodel … --shadow-database-url <空库>` 输出必须为空。

---

## 6. 留给 P2 的确定事实

- 内置 LAB 库 id 固定：`1ab00000-0000-4000-8000-000000000001`（spec 与迁移同源断言）。
- `examType` / `QuestionBank.type` 都是 `VARCHAR(32)`，不是原生 enum；校验放 DTO 白名单。
- COURSE 题过渡占用规则（评审 §10.5 Q2）：`category='PROFESSIONAL'` + `collegeId=NULL` + 独立 bank；**严禁 GENERAL_SAFETY**（旧查询对该类目无学院过滤）。
- `paper-config.compat.ts` 按 Q3 在 P2 写。
- 迁移链现在是自足的：P2 加表/列后，先 `migrate diff` 审 SQL，再落迁移目录。

---

## 7. 复现

```bash
cd D:/2026准入题库
git checkout feat/exam-platform && git log --oneline -4      # 47747cc / 6c172ee / afe5f92 / 45f472b

bash scripts/run-acceptance.sh P1                            # 失败计数应为 0

# 自足性（任选一个空库连接串）
cd server
npx prisma migrate diff --from-migrations prisma/migrations \
  --to-schema-datamodel prisma/schema.prisma \
  --shadow-database-url "mysql://…/某个空库" --script        # 应输出 empty migration
```

证据：`evidence/P1-20261102/`（21 份，含账本前后、干净库 deploy ×2、diff、冒烟对拍）。

---

## 8. 关联

- 上一阶段：[[lab-exam-2026-11-02-exam-platform-p0-baseline]]
- 迁移账本概念卡：[[concept-prisma-migration-ledger-p3009]]
- 同类事故：[[lab-exam-2026-09-18-prod-500-audience-migration-missing]]
- 避坑：[[避坑指南]] / [[避坑指南-验收清单]]