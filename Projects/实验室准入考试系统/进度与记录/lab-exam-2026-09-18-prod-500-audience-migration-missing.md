# 2026-09-18 正式环境发版后 500——audience 迁移漏执行 + 交付脚本硬编码库名

> 状态：**✅ 全部闭环（2026-09-18 深夜）**——audience 列修复 + 独立复验 200；正式库迁移账本由 0 条补齐为 8 条（resolve），migrate deploy 隐患解除；测试库实测未受影响。详见 §九
> 桌面交付件：`正式环境500排查-2026-09-18.md`、`正式环境500修复行动清单-2026-09-18.md`、`正式环境500修复结论-2026-09-18.md`

## 一、事故经过

- 2026-09-18 正式环境发版（v0.2~v0.3.5 + 文案修复 `2834ac8`），测试反馈证书导出页「加载考试列表失败」
- 实测：所有查 `exams` 表的接口 500（`/api/exams`、`/statistics/candidates`），不碰的全 200；判别探针 `/users/my-classes/list` 查同一张表但显式指定 5 列 → 200，证明表在、缺的是某一列
- 根因：**运维发版漏跑 `npx prisma migrate deploy`**，`exams` 表缺 v0.2 的 `audience` 列，Prisma 全列查询即炸（接口只回笼统 1000，日志里才有 `Unknown column 'exams.audience'` 原文）

## 二、排查中发现的第二个坑：交付 SQL 硬编码库名

- 原 `04_add_exam_audience_prod.sql` 写死 `USE lab_exam;`——那是**开发机本机库**名（本机 server/.env 与 docker-compose 用它）；正式库按运维导入指南是 `lab_exam_prod`
- 照原样执行的两种坏结局：线上无此库 → Unknown database 白跑；恰有此库 → ALTER 打到错库且自带校验返回「成功」假象（假成功最难查）
- **已改写**（`D:\\claude-work\\lab-exam\\04_add_exam_audience_prod.sql`）：去 USE 不硬编码库名、校验用 `DATABASE()`、加前置检查（打印当前库 + `_prisma_migrations` 计数）、补「手工 ALTER 后必须 `prisma migrate resolve --applied 20260907000000_add_exam_audience` 否则将来 migrate deploy 撞 Duplicate column → P3009 阻塞」说明

## 三、运维执行顺序（最终版）

1. 备份 exams 表
2. 执行前 grep 后端日志「未处理异常」→ 应见 `Unknown column 'exams.audience' in 'field list'`
3. 跑前置检查：看 `SELECT DATABASE()` 打印的库名（应是 lab_exam_prod，以现场为准）+ `_prisma_migrations` 计数
4. 分岔：
   - 7 条历史迁移、末条 `20260807000000_add_missing_timestamps` → `cd server && npx prisma migrate deploy`（首选，自动按 DATABASE_URL 选库+补记录）
   - 表不存在/条数不对 → 改写版手工 SQL + 事后 `migrate resolve --applied`（**千万别跑 migrate deploy**，会重放全部历史迁移撞已存在的表）
5. 复验：`GET /api/exams` 返回 200、证书导出页拉到考试列表、日志那行消失

## 四、已核验事实（多轮独立复核，勿重复操作）

| 事项 | 状态 | 证据 |
|---|---|---|
| audience 迁移 | ❌ 未执行（本次要跑） | 查 exams 接口全 500，其余 200 |
| 线上代码 | ✅ = main HEAD `2834ac8`，干净构建 | 产物指纹：statistics 分片含 candidates 路径与「下方」文案 |
| 题库 03 脚本 | ✅ 09-02 已执行，**绝不可重跑** | 正式库 1866 道、题干真实、createdAt=09-02；脚本是 DELETE+2001 INSERT 快照，重跑=覆盖（新增丢、约 135 道复活） |
| 沈春洋密码 SQL | ❌ 未执行，与本次无关 | 旧强密码仍一次登录成功，另定时间处理 |

## 五、已入库的防复发措施（均已推 main 并 git 核验）

- `49b0617`：RELEASE_CHECKLIST 三条——①发版 SQL 列入交付物并标注执行状态 ②手写 SQL 不得硬编码库名 ③部署后验证 `GET /api/exams` 返回 200
- `6d90623`：DEPLOY.md「五、升级部署」补 14 行——migrate deploy 不可省（自动按 DATABASE_URL 选库）、500 核对法（日志 Unknown column + 迁移计数）、手工补 SQL 两坑（禁 USE、resolve 防 P3009）
- `RELEASE_CHECKLIST` 再补一条（**`bd3d311` 已推 main，2026-09-18**）：「正式库 `_prisma_migrations` 登记应为 8 条，不足先补登记再 deploy，否则 P3009」（详见 §九）
- **决议**：改写版 04 SQL 不进 git——DDL 真源已在 `server/prisma/migrations/20260907000000_add_exam_audience/`，副本漂移正是今天的坑；01/02/03/fix-password 含 bcrypt 哈希绝不进 git；将来如需版本化兜底 SQL 落脚点，新建 `deploy/sql/` 只放纯 DDL

## 六、复盘要点

- **migrate deploy 不进 Dockerfile**（构建期连不上生产库，每次构建触发迁移风险大）；正确形态=部署步骤（README 早有，这次是漏跑）
- audienceHint 改动（明细口径提示随「考生类型」）当时滞留工作区，后续已随 `00129a0` 入库，与本次事故无关
- 闭环信号：运维执行后 `GET /api/exams` 返回 200

## 七、当前进度（09-18 深夜，重启接续看这里）

- **运维已执行 + 我独立复验闭环（2026-09-18）**：正式 admin 登录（`/api/auth/login`，字段 `account`/`password`）拿 csrfToken → `GET /api/exams?pageSize=200` → **200**，2 场考试（「111」「测试考试」）均带 `audience=STUDENT`；浏览器端证书导出页考试下拉列出「全部考试/111/测试考试」、全校统计页出数（学生 8473、教师 283）。截图 `gui-test-screenshots/2026-09-18-prod-audience-fix/01~05`
- **正式环境回归（只读部分，2026-09-18 完成）**：`/api/exams` 200、`/api/statistics/candidates` 200（total=80；修复前 500）、`/api/statistics/school` 200、`/api/certificates/admin/list` 200；浏览器端统计页**学院筛选实测生效**（选电气 → 学生 1130 / 教师 52，两表同步收窄，截图 `06`/`07`）。**写数据部分**（学院管理员建教师考试 → 教师考试 → 教师证书导出）要在正式库造真实考试数据，**待用户决定是否做**；证书筛选/导出的有数据验证同理（正式库现 0 张证书）
- **账本隐患已解除（09-18 深夜）**：正式库 `_prisma_migrations` 由 0 条补齐为 8 条（resolve），详见 §九；§三「7 条历史迁移」前置判据对正式库是错的（实际 0 条），仅适用于测试库/开发库，将来发版文案勿沿用
- 遗留不阻塞：**checklist 账本前置项已随 `bd3d311` 推 main（2026-09-18）**；fix-school-admin-password.sql 未执行（沈春洋密码，另定时间）；audienceHint 改动已随 `00129a0` 入库（测试环境验过、正式未上）；提高并发三件事待拍板（见 [[lab-exam-2026-09-17-capacity-concurrency-assessment]]）

## 八、为什么"只影响下次发版"——迁移账本（`_prisma_migrations`）的定时炸弹

`prisma migrate deploy` 是**记账式**的：只执行账本里没有的迁移。列已经在、账本没记 → 下次任何人跑 deploy 都会重放这条 `ALTER TABLE exams ADD COLUMN audience` → `Duplicate column name 'audience'` → 该迁移在账本里被标 **failed** → 此后 deploy 报 **P3009**，**拒绝执行任何后续迁移**。于是疼点集中在下次发版：那次新增的字段/表补不上，新功能一上线就是 500（与本次同款症状）。平时没有任何东西会碰这条迁移，所以**现在没事、发版才炸**；解开只要一条 `migrate resolve --applied`，但那是发版窗口里才发现。

**"运维应该就是 migrate deploy 走的"这个假设不能默认成立——本项目有三条实证（2026-09-18 复核）：**

| 证据 | 内容 | 出处 |
|---|---|---|
| 交付形态被刻意改成 SQL 文件 | 2026-08-28 拍板「**运维更熟悉 SQL 文件执行方式**，便于审计和回滚」，交付物=01/02/03 SQL + ops-import-readme | [[生产环境数据库导入清单]] 更新记录 |
| `migrate deploy` 在本项目**真的失败过** | 2026-09-07 dev 库 `prisma migrate deploy` 因历史漂移失败（`created_at` 重复列，先于本次存在）→ 改为**手工 ALTER**；测试环境同样手工 ALTER + `migrate resolve` 登记 | [[session-handoff-2026-09-07-v02-college-admin-exam-teacher-candidate]] |
| 正式库存在**账本之外的表** | 2026-09-18 探针实测：`GET /api/exams/:id/papers/generate-progress?jobId=<假 id>` 返回业务错 `1201 任务不存在`（不是 500）⇒ `paper_generation_jobs` **表存在**；而该表**从未出现在任何迁移文件里**（`git log --all -p -- server/prisma/migrations` 命中数 0，迁移目录也从未被删过）⇒ 正式库这份 schema 至少有一处不是迁移建出来的 | 本次实测 |

补充：`paper_generation_jobs` / `exam_events` 中，**`exam_events` 在 init 迁移里，`paper_generation_jobs` 不在**——即 2026-08-10「生成试卷报 paper_generation_jobs 表不存在」那次事故的根因被记成"漏跑 migrate deploy"其实是**记错了**，跑 migrate deploy 永远建不出这张表（它只能来自 `prisma db push` 或手工 DDL）。这条更正建议同步进 [[lab-exam-deploy-checklist]] 第八章。

---

## 九、深夜收尾：账本确认全空 → 8 条 resolve 补齐 ✅（2026-09-18 闭环）

**比 §八 担心的更严重**：运维回执查询 `_prisma_migrations` 结果为 **0 条（全空）**，不是"缺第 8 条"——正式库建库起即非 migrate 管理（手工 SQL/db push 铺底，旁证：`paper_generation_jobs` 表不在任何迁移文件里）。意味着正式库处于"**任何人跑 migrate deploy 都会从第 1 条重放全部迁移 → 表已存在 → P3009**"的状态，不只是 audience 一条的事。

**排查插曲（用事实钉死查的是哪个库）**：运维截图 tab 显示 `lab_exam.p…`，一度疑为测试库。用用户提供的测试库连接串 `192.168.0.165:13306/lab_exam`（本机 mysql 8.4 客户端直连）实测：测试库登记 **8 条齐全**（原时间戳 08-07/09-07）+ audience 列在（varchar(16) DEFAULT 'STUDENT'），该实例无 lab_exam_prod。→ 截图必为正式库。

**修复（发版前置，已完成）**：运维在 `lab-exam-server` 容器内对 8 条迁移逐条 `npx prisma migrate resolve --applied <name>`（只写登记不动表）。回执截图：8 条齐全，finished_at 全为 09-18 04:27–04:28（resolve 补录特征时间戳）；同刻复测测试库登记未被误动（原时间戳原样）→ 确证改的是正式库。**正式库从此可安全 `migrate deploy`（只跑新增迁移）。**

**RELEASE_CHECKLIST 已补发版前置项**（**`bd3d311` 已推 main**，`00129a0..bd3d311`；纯文档、推送不触发 Jenkins）：「正式库 `_prisma_migrations` 登记已补齐——发版前 `SELECT COUNT(*) FROM _prisma_migrations;` 应为 8，不足先补登记再 deploy，否则 P3009」。

**修正一处旧判据**：§三 前置检查"7 条历史迁移"的预期对正式库是错的（实际 0 条）——该判据仅适用于测试库/开发库，将来发版文案勿再沿用。

**遗留（均不阻塞）**：audienceHint 改动已随 `00129a0` 入库并在测试环境验过（正式未上）；RELEASE_CHECKLIST 前置项已随 `bd3d311` 入库；业务方回归证书导出页；fix-school-admin-password.sql 未执行；提高并发三件事待拍板。

相关概念卡：[[concept-prisma-migration-ledger-p3009]]
