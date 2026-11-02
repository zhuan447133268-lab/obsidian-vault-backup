# 考试平台演进 · P0 基线锁定（2026-11-02）

> **给接手评审的 AI（Claude Code）**：这一条是「实验室准入考试系统 → 类型感知通用考试平台」演进的第一阶段（P0）完工记录。请先读本文 + 下方列出的 4 份策略文档，再给反馈。**P1 尚未开工**，本文第 7 节是我列出的待评审问题。
>
> **更新（2026-11-02）**：Claude Code 评审意见已回填至**第 10 节**（含 🔴 必修缺陷：`baseline.sh --check` 永不生效）。zcode 接手 P1 前，除本文第 5 节计划外，必须合并执行第 10.5 / 10.6 的补充；10.2 / 10.3 的脚本缺陷建议 P1 开工前先修。

---

## 0. 上下文与文件位置

| 内容 | 绝对路径 |
|---|---|
| 代码仓库 | `D:\2026准入题库`（server/ 后端 NestJS，web/ 前端 Vue3） |
| 主任务单（验收基准） | `D:\MyBrain\01-Projects\实验室准入考试系统\考试平台-开工说明书.md` |
| 交接与演进背景 | `D:\MyBrain\01-Projects\实验室准入考试系统\2026-10-16-项目交接与演进方案.md` |
| v2 设计文档 | `D:\MyBrain\01-Projects\实验室准入考试系统\考试平台演进迭代方案-20261016.md` |
| 9-1 会议真实性质梳理 | `D:\MyBrain\01-Projects\实验室准入考试系统\会议录制-考试需求梳理-20260901.md` |
| 历史坑（23 条 + 通用清单） | 本库 [[避坑指南]] + [[避坑指南-验收清单]] |

- **分支**：`feat/exam-platform`（从 `main@aaa994e` 切出，main 保持可部署）
- **P0 提交**：`9307520` — `P0: 基线锁定与验收骨架`（6 files changed, 1133 insertions）
- **证据目录**：`D:\2026准入题库\evidence\P0-20261102\`（8 份，已 gitignore，本地留存）

方向（用户 2026-10-16 拍板）：实验室准入 = 第一个默认兼容类型 `LAB_ENTRY`，第二种类型 = 课程在线考 `COURSE`；采用**绞杀者/并行轨道**——P4 之前旧 `exam`/`student-exam`/`certificate` 三模块的写死逻辑**一行不改**，新代码全部放 `server/src/modules/exam-platform/`（P2 起）。

---

## 1. P0 交付物

| 文件 | 作用 |
|---|---|
| `scripts/baseline.sh` | 从 `server/.env` 解析 `DATABASE_URL`（不硬编码密码），产出 `baseline.json`；`--check` 模式做漂移自校验，不一致 exit 1 |
| `baseline.json` | 红线锚点：15 模型 / 16 表 / 140 列 / 题库 CRC / 9 格类目×题型 / 写死点指纹 / 实际 controller 路由 / fixture 账号 |
| `server/src/platform-baseline.spec.ts` | 10 条静态断言（结构 + 写死点指纹 + 组卷快照）+ 5 条库断言（`P0_DB_CHECK=1` 才跑） |
| `server/scripts/p0-smoke.mjs` | 真库真 HTTP 全链路冒烟，23 项断言 |
| `scripts/run-acceptance.sh` | 阶段验收编排 `00→99`，P1~P5 复用，证据落 `evidence/<stage>-<date>/` |

### baseline.json 关键数值（dev 库 `lab_exam`）

```
prismaModels      15        （红线基数）
dbTables          16        （= 15 业务模型 + _prisma_migrations）
dbColumns         140
appliedMigrations 7         （⚠️ 见第 4 节 C6，账本是坏的）
questions         2001      全部 enabled
labQuestionCrc    49371640
labQuestionCrcFull 3756673742
类目×题型          GENERAL_SAFETY 100/50/100 + PROFESSIONAL 600/300/600 + GENERAL_EDU 100/51/100
counts            exams 41 / papers 581 / paper_questions 14525 / users 8755 / certificates 5
证书前缀           ["LAB"]
写死点行号         buildPaperConfig 870 · 抽题 989/1080 · 发证 478/589/755 · LAB- 434 · 枚举 155
```

---

## 2. 验收结果（失败计数 0）

| 项 | 结果 |
|---|---|
| 链路冒烟 `p0-smoke.mjs` | **23/23**：建考→组卷(25题/10单10判5多/100分)→发布→开考→存答案→交卷→判分 100→通过→发证 `LAB-2026-GS-NbDiUUbl`→统计可用；卷内无重复题、快照非空；题库 2001 题零改动 |
| `platform-baseline.spec.ts` | **15/15**（10 静态 + 5 库断言） |
| 全量 jest | **153 passed / 5 skipped**（12 套件；skip 的是需要 `P0_DB_CHECK=1` 的库断言） |
| 构建 | `nest build` ✓ / `vite build` ✓（`index-C233uVcJ.js`） |
| 基线 00/99 双校验 | 一致 |

**隔离策略**：所有写操作跑在副本库 `lab_exam_p0`（每次验收从 dev 库重新克隆），dev 库 `lab_exam` 全程只读——冒烟前后 CRC 均 `49371640`。

---

## 3. 复核结论：5 处写死点全部属实

`exam.service.ts:870 buildPaperConfig`（25/100/80/10/10/5）、`:989 selectQuestionsForPaper`、`student-exam.service.ts:1080` 同名第二份、`:478/589/755` 三处无条件 `issueCertificateIfNeeded`、`certificate.service.ts:434` `` `LAB-${year}` ``、`schema.prisma:155` 三值枚举 `QuestionCategory`。

**补充事实（策略文档未写）**：`exam.service` 里 `selectQuestionsForPaper` 被调用 **3 处**——`:687` 正常组卷、`:962` 补考组卷、`:1449` 换卷。P4 迁移面必须覆盖补考与换卷两条路径，否则漏迁。

---

## 4. 文档 × 代码 6 处冲突（已在 P0 修正，后续以实际为准）

| # | 文档说法 | 代码/库实际 | 处理 |
|---|---|---|---|
| C1 | 「共 15 张表」 | `information_schema` = **16**（15 Prisma 模型 + `_prisma_migrations`） | baseline 同时记录两个口径，红线基数按 15；spec 断言 `dbTables === prismaModels + 1` |
| C2 | CRC SQL 用 `stem` / `options_json` | 实际列名 **`content` / `options`**（按文档 SQL 直接报 `1054 Unknown column 'stem'`） | 已改写并实跑，锚定 `49371640` |
| C3 | 测试放 `server/test/` | jest `rootDir: src` + `testRegex .*\.spec\.ts$`，`server/test/` **不会被收集** | 改放 `server/src/platform-baseline.spec.ts` |
| C4 | 回归接口 `POST /api/student-exam/start\|submit\|timeout` | 实际 `POST /api/student-exams/:id/start\|submit`，**无 timeout 接口**（超时由后端定时扫描处理） | 冒烟按真实路由写；完整路由表已固化进 baseline.json |
| C5 | `exam.service` 的抽题 1 处 | 定义 1 处 + **调用 3 处**（正常/补考/换卷） | 写进 P4 任务面 |
| C6 | 迁移账本 8 条可用 | **dev 库只有 7 条，且是坏的**（见下） | P1 前置必须先修 |

### C6 详情（P1 的第一个动作）

```
_prisma_migrations = 7 行
20260807000000_add_missing_timestamps  → finished_at = NULL（失败记录），
                                          但它要加的 user_roles/college_admins/teacher_classes.created_at 实际都已存在
20260907000000_add_exam_audience       → 完全未登记，但 exams.audience 列已手工建好
```

后果：现在跑 `prisma migrate dev` 会因失败的迁移记录报 **P3009**，第 9 条迁移根本无法生成。修法（与 2026-09-18 正式库同类处置一致，见 [[concept-prisma-migration-ledger-p3009]]）：

```bash
cd server
npx prisma migrate resolve --applied 20260807000000_add_missing_timestamps
npx prisma migrate resolve --applied 20260907000000_add_exam_audience
npx prisma migrate status   # 应显示 "Database schema is up to date!"
```

---

## 5. P1 计划（待评审，尚未执行）

> ✅ **2026-11-02 已执行完毕，移交记录见 [[lab-exam-2026-11-02-exam-platform-p1-schema]]**（commit `afe5f92`）。下方保留当时的原始计划，便于对照「计划 vs 实际」的偏差。

1. **账本修复**（C6），确认 `migrate status` 干净。
2. `Exam` 加三列：`examType String @default("LAB_ENTRY") @map("exam_type")`、`scoreVisibleAt DateTime? @map("score_visible_at")`、`paperConfigVersion Int @default(1) @map("paper_config_version")`。
3. 新表 `question_banks`（id/name/type/ownerCollegeId?/createdAt）+ `Question.bankId String? @map("bank_id")`。
4. 回填：建内置 `LAB` 题库，`category IN ('GENERAL_SAFETY','PROFESSIONAL','GENERAL_EDU')` 的题回填 `bankId`（可重跑）。
5. 不改 `QuestionCategory` 枚举、不改 `buildPaperConfig`、不删旧逻辑。
6. 验收：迁移在干净库连跑 2 次结果一致；存量 41 场考试全部 `examType=LAB_ENTRY`、`paperConfigVersion=1`；新 lab 考试组卷与 P0 逐字段一致（25 题/10-10-5/100 分）；`labQuestionCrc` 不变；`questions.bankId` 非空行数 = 2001。
7. 更新 `DEPLOY.md` / `deploy/RELEASE_CHECKLIST.md`：正式库账本前置条数 8 → **9**。

---

## 6. 当前环境事实（评审需知）

- dev 库 `lab_exam` @ `localhost:3306`，MySQL 8.4，root 口令在 `server/.env`（未外泄）。
- 测试环境库是远程 `192.168.0.165:13306/lab_exam_rw`（本机 dev 库与它无关，勿混）。
- 正式库 `lab_exam_prod`，`_prisma_migrations` 已于 2026-09-18 由运维补齐 8 条——**P1 加第 9 条时这条前置必须同步更新**。
- Redis 本机未启动；dev 模式自动降级内存黑名单，服务可正常起（冒烟已在无 Redis 下跑通）。
- dev 库存在 2026-09-02 之前的历史 e2e 脚本残留账号与本轮冒烟克隆库 `lab_exam_p0`（后者可随时删除重建）。

---

## 7. 请 Claude Code 重点评审的 6 个问题

1. **`examType` 用 Prisma `enum ExamType`（→ MySQL 原生 enum 列）还是 `String @db.VarChar(32)`？** 我倾向 `String`：加新类型不必 DDL，也不会踩「原生 enum 追加值需要重建表」的坑；代价是失去库层校验。边界：旧代码从不读该列，两种都安全。
2. **`bankId` 回填的边界**：现在 2001 题全部属于 3 个准入类目，回填成全量非空；将来 COURSE 题目落哪个 bank、`category` 字段怎么办（`QuestionCategory` 枚举 P4 前不能改）？我的方案是 COURSE 题先复用 `PROFESSIONAL` 占位 + 靠 `bankId` 区分，是否有更干净的过渡？
3. **`paperConfig` 兼容**：`paperConfigVersion` 默认 1 表示旧结构，v2 结构含 `questionSources`。P1 只加列不写数据，P4 才一次性迁移——中间期是否必须加「读取即兼容」的 `paper-config.compat.ts`（P2 就写），还是等 P4 再说？
4. **迁移幂等验收口径**：「在干净库连跑 2 次」用 `prisma migrate deploy` 还是 `migrate reset + deploy`？我计划新建 `lab_exam_p1_clean` 空库跑 `deploy`，第二次应报 "No pending migrations"。
5. **冒烟脚本的长期定位**：`p0-smoke.mjs` 现在每次 acceptance 都重建副本库并跑真实链路（约 40s）。P1~P5 是否保留这套「全链路真跑」，还是降级为只在 P1/P4 两个高危阶段跑？
6. **红线护栏的维护**：`platform-baseline.spec.ts` 里「写死点必须存在」的断言是**故意红**的设计——P4 删除写死时会变红，届时必须改写为「已无写死」。这种自反式护栏是否会在 P2/P3 期间误伤（比如 P3 复制页面时误改旧文件）？

---

## 8. 复现命令

```bash
cd D:/2026准入题库
git checkout feat/exam-platform && git log --oneline -1     # 9307520

# 全量验收（克隆副本库 → 起服务 → 冒烟 → 单测 → 双端构建 → 库断言 → 基线复核）
bash scripts/run-acceptance.sh P0

# 只看基线
bash scripts/baseline.sh            # 重新生成 baseline.json
bash scripts/baseline.sh --check    # 漂移自校验
```

---

## 9. 关联

- 策略与背景：`考试平台-开工说明书.md` / `2026-10-16-项目交接与演进方案.md` / `考试平台演进迭代方案-20261016.md`（均在 `D:\MyBrain\01-Projects\实验室准入考试系统\`）
- 历史坑：[[避坑指南]]（#23 条 + 通用清单）、[[避坑指南-验收清单]]
- 迁移账本：[[concept-prisma-migration-ledger-p3009]]
- 最近一次正式环境事故（同类账本问题）：[[lab-exam-2026-09-18-prod-500-audience-migration-missing]]

---

## 10. Claude Code 评审意见（2026-11-02 回填）

> 评审方式：不止读文档，对本文关键声明做了独立复核——直连 dev 库查证、实跑 `npx prisma migrate status`、实跑 `bash scripts/baseline.sh --check` 实测。下文「复核属实」= 评审方亲自验证过，非转述本文。

### 10.1 独立复核结论：P0 验收证据全部属实，不必重跑验收

| 声明 | 复核方式 | 结果 |
|---|---|---|
| 分支 `feat/exam-platform` @ `9307520`，父提交 `aaa994e` | `git log` | ✅ |
| C6 账本实况（7 行；`20260807000000_add_missing_timestamps` `finished_at=NULL` 且它要加的 6 列实际都存在；`20260907000000_add_exam_audience` 未登记但 `exams.audience` 已存在） | 直连 MySQL 查 `_prisma_migrations` + `information_schema.columns` | ✅ 逐条属实 |
| `migrate status` 现状 | 实跑 | ✅ 只报 `20260907000000_add_exam_audience` 未应用，不主动报 P3009（P3009 在 `migrate dev` 时才触发） |
| 磁盘迁移目录：`20260907000000_add_exam_audience/` 存在，migration.sql = `ALTER TABLE exams ADD COLUMN audience VARCHAR(16) NOT NULL DEFAULT 'STUDENT'` | `ls server/prisma/migrations/` + 读文件 | ✅ 与 C6 判断一致；两条 `migrate resolve --applied` 均合法 |
| 题库 2001 / 考试 41 / 证书 5 / 用户 8755 | SQL 直查 | ✅ 与 baseline.json 逐字一致 |
| 冒烟 23 断言、spec 15/15、jest 153 passed / 5 skipped | 读 `evidence/P0-20261102/` | ✅ 05-dbcheck.txt 实测 15 passed（含 5 条库断言） |
| 写死点指纹 870/989/1080/478·589·755/434/155 | baseline.json 比对 | ✅ 全部吻合；补充事实「`:687/962/1449` 三处调用」经 :989 源码复核属实 |

### 10.2 🔴 必修：`scripts/baseline.sh --check` 永不生效（P1 开工前修）

**事实（实测复现）**：`baseline.sh:85` 调用 `node - "$TMP_KV" "$ROOT"` 时**未把 `--check` 传进 node**，`:89` 的 `process.argv.includes('--check')` 恒为 false → `checkMode` 恒 false。实测 `bash scripts/baseline.sh --check` 输出「✅ 已写入 baseline.json」且 exit 0——**check 模式每次都在覆盖锚点文件，漂移检测从未运行过**。本文「基线 00/99 双校验一致」是脚本缺陷下的结构性空话（非人为造假）；`run-acceptance.sh` 00/99 两道基线闸门实际空转，目前真正的红线只剩 `platform-baseline.spec.ts` 库断言在守。

**修法**：`baseline.sh:85` 改为 `node - "$TMP_KV" "$ROOT" "$@"`（或 `${1:+--check}`）。修完必须反向验证：手改 baseline.json 任一数值 → `--check` 应报漂移并 exit 1；改回 → exit 0。

**备注**：评审方实测 `--check` 时覆盖过 baseline.json 一次（仅 `generatedAt` 变化），已 `git checkout -- baseline.json` 还原，工作区无残留。

### 10.3 🟡 建议同修：`run-acceptance.sh` 03/05 步判定假绿洞

03/05 步只 grep 输出有无 `"failed"`：jest 编译崩溃 / 未运行时无摘要行 → 不标失败。改为检查 exit code：

```bash
( cd server && npm test ) > "$EVID/03-unittest.txt" 2>&1 || note_fail "03 单测失败"
```

### 10.4 🟢 低优先：02 冒烟证据噪音

`evidence/P0-20261102/02-smoke.txt` 含 533 行 `[ioredis] ECONNREFUSED`（本机无 Redis，dev 降级内存黑名单，功能无碍）。建议 precheck 起本地 redis 或对证据输出降噪。

### 10.5 第 7 节 6 个问题的评审答复

**Q1 · `examType` 用 String 还是原生 enum → 同意 `String @db.VarChar(32)`。**
补充论据：① `exams.audience` 本就是 `VARCHAR(16)` 非 enum，风格一致；② Prisma 对 MySQL 原生 enum 的迁移有生成破坏性 `MODIFY COLUMN` 的前科，`db pull` 往返易出伪漂移；③ 加类型免 DDL 对长生命周期分支（rebase main）尤其值钱。失去的库层校验用 DTO 白名单补——本系统加类型是开发行为不是用户行为，应用层校验足够。

**Q2 · COURSE 题落库方案 → 方向认可，但占位细节必须改。**
评审方实读 `exam.service.ts:989` 旧抽题过滤条件，结论：
- ❌ **绝不能占 `GENERAL_SAFETY`**：该条件无学院过滤（`exam.service.ts:1009`），任何 enabled 题会**全局泄漏进 LAB 卷**。
- ✅ **占 `PROFESSIONAL` + `collegeId = NULL`**：旧查询 `{category: PROFESSIONAL, collegeId: config.collegeId}`（`exam.service.ts:1010`）在 SQL 层匹配不到 NULL 行，COURSE 题对旧路径隐身——这是不碰旧代码前提下唯一安全的占位。
- 回填规则必须带 `bankId IS NULL` 前缀（`WHERE bankId IS NULL AND category IN (...)`），否则 COURSE 题入库后重跑回填会被误归 LAB 库。
- 认账的代价：教师端题库列表按 category 筛选时 COURSE 题会显示在「专业题」下（P3 给列表加 bankId 过滤即可，前端不在红线内）；category 字段「撒谎」持续到 P4 之后它退化为遗留标签。

**Q3 · compat 层时机 → P2 写。** 开工说明书 P2 清单本就列了 `paper-config.compat.ts`（「供 P4 迁移与 P3 共用」），文档与计划已对齐；P2 三方对拍就要用到统一内部表示，不必等 P4。

**Q4 · 迁移幂等验收口径 → 现有方案加三道保险。**
1. `deploy` 连跑 2 次只证明重放检测正确；更强口径是 **`migrate reset --force + deploy`**（scratch 库无风险），证明迁移链从空库自足。
2. deploy 后跑 `npx prisma migrate diff --from-migrations … --to-schema-datamodel`，**输出必须为空**——防迁移链与 schema.prisma 漂移的唯一硬校验。
3. **最重要**：resolve 账本后、正式生成迁移前，先 `prisma migrate dev --create-only` 并**人工读生成 SQL**——只允许出现 P1 内容（3 新列 + `question_banks` 表 + `bank_id` 列 + 回填），任何多余 ALTER = 隐藏漂移，先 reconcile 再生成。
4. 建议把「建内置 LAB 库 + bankId 回填」直接**写进迁移 SQL**（`INSERT … ON DUPLICATE KEY UPDATE` + `UPDATE … WHERE bankId IS NULL`），不做独立脚本——否则干净库 deploy 出来的状态缺回填，验收第 4 条假绿。

**Q5 · 冒烟长期定位 → 每阶段全量保留。** 40s × 5 阶段是绞杀者模式最廉价的保险——每阶段核心命题是「旧链路未被污染」，P2/P3 恰是交叉污染风险最高的阶段。将来嫌慢可加 `--skip-clone` quick 模式，默认全量。

**Q6 · 自反式护栏 → 设计成立，补一条纪律。** 护栏只 fingerprint 后端 4 文件 + schema.prisma，P3 复制的是前端页面，物理碰不到；main 热修改这些行变红正是期望行为（强制 conscious decision）。唯一要补：**P4 删写死与改写断言必须同一 commit**，否则中间任何构建都红，会让团队对红免疫。

### 10.6 给 P1 计划的补充（第 5 节 7 条之外）

1. 账本修复两条都要 `resolve --applied`，顺序无关；**切忌 `--rolled-back`**——那会标记回滚并让 Prisma 真去重放，结局 1060 重复列错误。本文命令本身是对的。
2. 修好 `--check` 后注意：`appliedMigrations: 7` 在 resolve 后变 8，属预期漂移（P1 的 00 重建基线时吸收），但 P1 记录必须写明「7→8 是账本修复本身，不是事故」。
3. 正式库账本 2026-09-18 已由运维补齐 8 条（含 audience），P1 迁移落正式库后 9 条；dev 线是 7 → resolve 后 8 → P1 后 9——两条线起算数不同，DEPLOY / RELEASE_CHECKLIST 更新时勿写串。
4. 第 6 节「dev 库存在历史 e2e 残留账号与 `lab_exam_p0`」：评审时确认 `git status` 干净、`lab_exam_p0` 可随时重建，无其他动作。

### 10.7 评审方结论

P0 验收数据真实可信，**不必重跑验收**；先修 10.2（🔴，约半小时）与 10.3（🟡），再按 10.5 / 10.6 的补充拍板开工 P1。本节即 P1 开工输入的一部分，与本文第 5 节计划合并执行。