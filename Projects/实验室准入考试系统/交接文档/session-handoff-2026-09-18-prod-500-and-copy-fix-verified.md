---
title: 交接 · 正式环境 500 事故闭环 + 迁移账本补齐 8 条 + 文案两条测试环境验收通过
date: 2026-09-18
project: 实验室准入考试系统
tags:
  - lab-exam
  - 交接文档
  - 事故复盘
  - 迁移账本
  - 文案修复
---

# 交接：正式环境 500 闭环 + 迁移账本补齐 + 文案验收（2026-09-18）

> **新 session 先读本文**。状态：正式环境 500 **已修复并独立复验闭环**；正式库迁移账本由 **0 条补齐为 8 条**（下次 `migrate deploy` 安全）；测试环境已 build `2834ac8` + `00129a0` 并**验收全过**；**无 pending 代码工作**，等业务方/运维节奏。

## 一、当前状态（一句话）

v0.2~v0.3.5 已在正式环境上线（线上代码 = main `2834ac8`），发版时**运维漏跑迁移**导致 `exams` 缺 `audience` 列、所有查 exams 的接口 500 → 运维补执行 + 我独立复验闭环；排查中发现正式库 `_prisma_migrations` **整表 0 条**（建库起即非 migrate 管理，比"缺第 8 条"严重），运维已逐条 `migrate resolve --applied` 补齐 8 条；文案两条（`2834ac8` 已上正式、`00129a0` 未上）在测试环境同一次 build 里验收全过。

## 二、今天做了什么（时间线）

| # | 事项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 正式发版后 500「加载考试列表失败」 | 根因=正式库 `exams` 缺 `audience` 列（v0.2 迁移漏执行）；无生产库权限下用「同表显式 select 探针」判定=缺列而非表不可用 | [[lab-exam-2026-09-18-prod-500-audience-migration-missing]] §一 §四 |
| 2 | 交付 SQL 硬编码库名 | 原 `04_add_exam_audience_prod.sql` 写死 `USE lab_exam;`（开发机库名，正式库=`lab_exam_prod`）→ 已改写（去 USE / `DATABASE()` 校验 / 前置检查 / resolve 说明）；**改写版不进 git**（DDL 真源在迁移文件） | 同上一节 §二 |
| 3 | 运维执行 + 我独立复验 | `GET /api/exams` 200 且返回含 `audience: "STUDENT"`；证书导出页考试下拉列出「全部考试 / 111 / 测试考试」；全校统计页出数 8473/283。**500 闭环** | 截图 `gui-test-screenshots/2026-09-18-prod-audience-fix/01~07` |
| 4 | 正式库迁移账本体检 | **实测 0 条**（非 7 条缺 1 条）⇒ 任何人跑 `migrate deploy` 都会重放全部历史迁移 → `Duplicate column` → **P3009** 卡死后续；用测试库连接串（192.168.0.165:13306/lab_exam，8 条齐全 + 原时间戳）对照，钉死运维截图为正式库 | 同上一节 §八 §九 |
| 5 | 运维补齐登记 | 容器内对 8 条迁移逐条 `npx prisma migrate resolve --applied <name>`（只写登记不动表）；回执 finished_at 全为 09-18 04:27–04:28（补录特征）；同刻复测测试库登记**未被误动** | 同上一节 §九 |
| 6 | 文案两条：提交 + 测试环境验收 | `2834ac8`（「上方」→「下方」4 文件）+ `00129a0`（明细口径提示随「考生类型」）→ 测试环境手动 build（`index-D1EUAOW4.js` → **`index-2si0ntx2.js`**）后 #29/#30 **全过** | [[lab-exam-2026-09-18-copy-direction-fix]] §八、[[避坑指南-验收清单]] 2026-09-18 批次 |
| 7 | 防复发文档入库（3 个 docs 提交） | `49b0617` RELEASE_CHECKLIST 三条 + `6d90623` DEPLOY.md 升级章节 +14 行 + `bd3d311` RELEASE_CHECKLIST 迁移账本前置项 | `git log --oneline` |

## 三、环境状态（重启接续看这里）

| 项 | 正式环境 | 测试环境 |
|---|---|---|
| 站点 | `https://lab-exam.oceghome.com` | `https://lab-exam-test.oceghome.com` |
| 代码 | 线上跑 `2834ac8`（main 现为 `bd3d311`，仅文档差异） | 已 build `2834ac8` + `00129a0` |
| 前端产物 | statistics 分片含「下方」文案、旧「上方」0 处 | 入口 `index-2si0ntx2.js`（旧 `index-D1EUAOW4.js`） |
| 迁移账本 | **8 条**（09-18 resolve 补录；发版前复查 `SELECT COUNT(*) FROM _prisma_migrations;` 应为 8） | 8 条齐全（原始时间戳，未被误动） |
| 数据概览 | 学生 8473 / 教师 283 / 8 学院 / 题库 1866（判断 754）/ **证书 0 张** / 考试 2 场（DRAFT「111」、「测试考试」） | 进士/教师/证书均有测试数据；陈卓口径明细 73（50 学生 + 23 教师） |
| 账号 | `admin` / `oceg2026`（SCHOOL_ADMIN） | `admin` / `oceg2026`；学院管理员 **陈卓 `IME000179` / `Test@2026v2`**（已恢复为**电气电子智能工程学院**管理员） |

## 四、待办（按"谁来推"分层）

**A. 等运维（下次发版窗口一起做）**
- 正式环境 build 下次迭代的改动——**`00129a0` 尚未上正式**（正式学院统计页当前仍显示旧提示「含学生和教师」；`2834ac8` 的「下方」文案已生效）。
- 发版前照 `deploy/RELEASE_CHECKLIST.md` 逐项打勾，重点三条：① `_prisma_migrations` 计数应为 8，不足先 `migrate resolve --applied` 补登记再 `migrate deploy`，否则 P3009；② 正式前端构建须注入 `VITE_AUTH_MODE=cookie`；③ 部署后验证 `GET /api/exams` 返回 200（考试管理页/证书导出页能拉到考试列表）。
- **push 不触发 Jenkins**，测试环境/正式环境都需**手动 build main**。

**B. 等用户拍板**
- 正式环境**写数据回归**（学院管理员建教师考试 → 教师考试 → 教师证书导出）：需在正式库造真实考试数据，做完有留痕，**待用户决定是否做**。
- 证书「考生类型」筛选与导出 Excel/ZIP 的**行为级**验证：正式库现 0 张证书，只能验到控件存在 + 接口 200；待有证书后补。
- 提高并发容量的三件事（同机房 / 显式连接池 / 合并「存答案+ANSWER 事件」）——见 [[lab-exam-2026-09-17-capacity-concurrency-assessment]]。

**C. 长期 / 下次发版顺手做**
- **P2 迁移账本健康度**：`paper_generation_jobs` 从未进过任何迁移（`schema.prisma` 有、迁移文件 0 命中，正式库却实测存在）→ 补一条 `CREATE TABLE` 迁移，并统一「schema 变更必须先 `prisma migrate dev` 生成迁移文件」的流程。
- `fix-school-admin-password.sql` 未执行（沈春洋 `BN100005453` 正式密码仍为 `Gb$d!a$X8&eTbij4`）；或让他走 `/change-password` 自助改密。
- 其他缓做：规范 2b 分页收口、`college-admins.vue` 翻页验证、测试环境交卷慢定位（缺 DB 侧实测数据）、C+ 配色验证、login 样式确认、全校统计页明细表（P3 待业务确认）。

## 五、环境事实与坑（今天新摸到的，省得重踩）

- **cookie 模式连 GET 也要 CSRF**：正式/测试环境 `POST /api/auth/login`（字段是 **`account`**，不是 `username`）→ 取 `data.csrfToken` 放 `X-CSRF-Token` 头，否则一律 `403 / 1004`。
- **CSRF 令牌不可从前端 JS 读取**（`localStorage` 空、cookie 全 httpOnly）⇒ 想在浏览器里确认某接口是否 200，**别看自己发的请求，看页面自己发的**：`performance.getEntriesByType("resource")` 带 `responseStatus`/`duration`。IAB 的 `tab` 对象也没有 `on/addListener`，挂不上网络监听。
- **前端产物文案残留扫描**：别用 `curl` 抓 `/assets/*.js`（本机 Git Bash 下 `grep -o` 出路径会丢字符导致解析失败）；改用**页面内 `fetch` 同源抓取**（`fetch('/')` → 入口 js 里的 chunk 映射 → 分批 `Promise.all`，注意单次 evaluate 32s 上限）。今天实测全量 63 个产物 js。
- **Element Plus 下拉/按钮**：`evaluate` 取 `getBoundingClientRect` + `cua.click` 最稳；下拉第一项常是「全部 XX」（等于没筛，要用真实项）；复位优先点输入框右侧**清除图标**。
- **明细表读数**：页面上不止一张表，`.el-table__body` 会串台 → 先按 `th` 文本定位目标表，再用**表头驱动列索引**。
- **测试库直连**（192.168.0.165:13306 / `lab_exam`）：写时间列必须 `UTC_TIMESTAMP(3)`（时区坑）；本机 `server/.env` 指向无关的 localhost 库。
- **陈卓的 `COLLEGE_ADMIN` 角色**今天又被别的会话摘掉过（只剩 TEACHER → 进不了学院统计页），已按产品流程恢复为**电气电子智能工程学院**管理员；注意 `users.collegeId` 是他本人所属（教育学院），与"管哪个学院"无关。
- 概念卡 [[concept-prisma-migration-ledger-p3009]]（迁移账本机制 / 处置命令表 / 三条红线）。

## 六、本次相关交付物

| 项 | 位置 |
|---|---|
| 事故记录 | [[lab-exam-2026-09-18-prod-500-audience-migration-missing]]（§一~§九，含账本闭环） |
| 文案记录 | [[lab-exam-2026-09-18-copy-direction-fix]]（§八 为测试环境复验结果表） |
| 概念卡 | [[concept-prisma-migration-ledger-p3009]] |
| 坑与验收 | [[避坑指南]] #29 · [[避坑指南-验收清单]] 2026-09-18 批次 #29/#30（全勾） |
| 代码提交 | `2834ac8`（文案）、`00129a0`（明细口径提示）、`49b0617`/`6d90623`/`bd3d311`（部署文档闸门） |
| 截图 | `D:\2026准入题库\gui-test-screenshots\` 下 `2026-09-18-prod-audience-fix/01~07`、`2026-09-18-testenv-hint-audience/01~07`、`2026-09-18-copy-direction-fix/01~03` |

## 相关

- [[lab-exam-2026-09-18-prod-500-audience-migration-missing]] · [[lab-exam-2026-09-18-copy-direction-fix]]
- [[session-handoff-2026-09-17-v03-teacher-dimension-stats-export]]（上一份交接）
- [[避坑指南]] · [[避坑指南-验收清单]] · [[lab-exam-deploy-checklist]]