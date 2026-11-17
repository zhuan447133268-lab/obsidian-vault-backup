---
date: '2026-11-17'
description: 2026-11-17 会话交接：正式环境已发版 4f7e919 + 11_ 138 条清理已执行并只读验收全过；同日晚新增待发批 b234d9c（师生账号编辑/删除，用户拍板随下一次发版一起发，测试环境已验收）；剩余=运维回执数字、李明阳重复教师号待业务确认、详情页残留待复现；含环境状态、红线、可复用手法
name: session-handoff-2026-11-17-prod-release-verified
status: active
tags:
  - lab-exam
  - session-handoff
  - 发版验收
  - 数据清理
type: project
---

# 2026-11-17 会话交接：正式发版 + 138 条清理已验收

> **🆕 2026-11-17 追加（同日晚）：已有新待发版批，用户拍板随下一次发版一起发** —— `origin/main` 前进到 **`b234d9c`** = `e18538c`（`feat(users): 学校管理员可编辑/删除师生账号（仅空账号可硬删）`，6 文件 +932/−40）+ `b234d9c`（发版前审计补丁，3 文件 +161/−9），**无迁移无 SQL**。已推 main、**已在测试环境（`index-BtK0PW_S.js` / `users-BV8bneyD.js`）验收全过**（接口 13/13、生命周期 9/9、浏览器 11 图）、**尚未上正式**。**用户 2026-11-17 拍板：不单独 build，随下一次发版一起发**。本文下面的「当前无待发版批」指 `4f7e919` 那批的结案状态，发版时请以 [[待发版清单]] 顶部与 §二·补·3、[[lab-exam-2026-11-17-师生账号编辑删除]] 为准。

**上一条交接**：[[session-handoff-2026-09-18-prod-500-and-copy-fix-verified]]
**当前 `origin/main`**：`4f7e919`（本地 `D:/01-项目/2026准入题库-main` 同源，工作区干净）

## 一句话现状

`4f7e919` 这批（5 commit）**已由运维发版**，配套 `11_void_bogus_absent_prod.sql`（138 条误标缺考 ABSENT→DRAFT）**已执行**；开发侧**只读复核全过**，无一遗留故障。**该批已结案（此句原文「当前没有待发版内容」仅指该批）**；同日晚 main 已前进到 `b234d9c`（师生账号编辑/删除），成为新待发批，随下一次发版一起发。剩下三件事都不阻塞：运维回执数字、李明阳重复教师号（等业务确认工号）、考试详情页残留（待复现）。

## 一、今天（11-17）完成的事

1. 正式环境只读验收（详见 [[lab-exam-2026-11-17-发版与138条清理验收]]）
   - 构建指纹：入口 `index-Edy8zCrq.js`；`exam-detail-vKqfUcW1.js`=`无法勾选组卷`、`student-Xm0OgSVx.js`=`hasPassed`、`statistics-osQcp8jC.js`=`attempt-panel`/`考试记录`
   - 后端同批判据：4 场作废考试 `statistics/candidates` 全 **0 行**（旧后端会显示 45/43/49/1 行「未开始」）
   - `11_` 结果：4 场卷 45/43/49/1 一张没少、100% `DRAFT`、`ABSENT` 归零；全库 627 张残余 `ABSENT` 全在已自然结束考试、0 场可疑
   - 真实成绩未受影响；从钰 1 行 `attemptCount=3`
   - 界面实拍 4 张：`gui-test-screenshots/2026-11-17-prod-release-sql/01~04`
2. 账号类排查（详见 [[lab-exam-2026-11-17-账号与数据待办]]）
   - 李明阳重复教师号：启用 `100029592`（有 92 分 + 证书）/ 禁用 `100029562`（0 数据）
   - 两名学生「密码错误」定案非 bug（首次登录强制改密后忘了新密码）
   - 全校禁用账号复核：禁用教师只剩 2 个（张凯悦测试教师号、李明阳 562），吴彤已恢复启用

## 二、环境状态（写死的事实，别再重新论证）

| 项 | 现状 |
|---|---|
| 正式环境 | `https://lab-exam.oceghome.com`，已 cookie 模式 + CSRF（**连 GET 都要带 `X-CSRF-Token`**） |
| 正式账号 | `admin` / `oceg2026`（SCHOOL_ADMIN，`isSystemAdmin`，唯一能重置学校管理员的人） |
| 正式库 | `lab_exam_prod`，`_prisma_migrations` 已于 09-18 补齐 8 条；本批无迁移 |
| 测试环境 | 已有 `4f7e919` 构建并验过（含 1406 守卫三场景、v0.4 32/32） |
| 发版硬要求 | ① 前端构建注入 `VITE_AUTH_MODE=cookie` ② push 不触发 Jenkins，需手动 build ③ 部署后 `GET /api/exams` 应 200 |
| 截图 | `gui-test-screenshots/` 只留本地，**绝不推送** |

## 三、待办（按谁在等分类）

**A. 等运维回执（只差数字，不阻塞使用）**
- `11_` 执行回执：`0b / 0c / 0d2 / 0e / 0f / 0g / 1 / 2 / 3a~3f`；要核的两笔账：`3c` 全库 `ABSENT` = `0g` − 138（我量到 **627**）、`3d` 合法缺考 = `0f`
- 备份表 `papers_absent_void_backup_20261110` **保留别删**（删=放弃回滚）

**B. 等业务确认**
- 教育学院李明阳真实工号是 `100029562` 还是 `100029592`（决定「保持现状/删空行」还是「改号保成绩再删空行」）；**切勿反向操作**
- 25数媒一班 4 人补考（王苛豪/陈相杰/潘明明/侯权珂）怎么安排
- 全校统计页要不要 P3 考生明细表
- 学院管理员能否重置本院教师（"再说"状态）
- 学生忘记密码是否要做自助入口（现在只能学校管理员重置）

**C. 待复现/待修**
- 考试详情页在 SPA 客户端跳转时疑似残留上一场试卷表（`exam-detail.vue:314` 无 `watch(route.params.id)`，正常入口会重建组件故未证实）

**D. 技术债（P2/P3，见 [[待发版清单]] §五）**
- 发布事务化 + 状态条件更新、组卷任务唯一键/锁、`paper_generation_jobs` 迁移、`/api/health` 带 commit、导入校验 `answer ⊆ options`、建考 60s 幂等改分布式

## 四、红线

- **正式库没有写权限**：任何数据变更只能出 SQL 交运维，开发侧只做只读核查
- 绝不打印数据库口令（测试库口令从 `D:/claude-work/reset_admin_temp.js` 的 `dbPass` 运行时读，**不要执行该脚本**，它会重置 admin 密码）
- 修 bug 不贴脚本；临时脚本只放 `%TEMP%`，工作区只留结果与证据
- `D:\claude-work\webretriever` 与本项目无关，别混

## 五、可复用手法

- 判「某前端改动上线没」：`GET /` 取入口 js → 正则抓 `xxx-[hash].js` 分片名 → 逐分片 grep 中文/属性名标记串（入口 hash 只反映入口自身；**整批含 `web/src` 时必须变**）
- 正式环境免登录态截管理员页面（Playwright + Edge，全程只读）：Node `fetch` 登录拿 cookie + `csrfToken` → `context.addCookies` → `addInitScript` 往 **sessionStorage** 写 `csrf_token` → `page.goto('/teacher')`；翻页用 `page.evaluate(() => document.querySelector('.el-pagination .btn-next').click())`
- 只读核查账号/成绩：`/api/users?keyword=`、`/api/statistics/candidates?keyword=`、`/api/certificates/admin/list?keyword=`、`/api/exams?page=&pageSize=`（`keyword` 只匹配姓名/工号/学号；考试列表 keyword 只匹配考试标题）

## 六、关联

[[lab-exam-2026-11-17-发版与138条清理验收]] · [[lab-exam-2026-11-17-账号与数据待办]] · [[待发版清单]] · [[避坑指南-验收清单]] · [[lab-exam-2026-11-16-统计口径统一v04测试环境验收]] · [[索引]]