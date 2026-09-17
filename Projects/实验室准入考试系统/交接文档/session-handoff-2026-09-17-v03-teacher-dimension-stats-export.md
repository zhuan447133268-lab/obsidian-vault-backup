---
title: 交接 · 迭代 v0.3 统计/证书导出纳入教师数据（v0.3.1 + v0.3.2 同日收口，测试环境两轮复验通过）
date: 2026-09-17
project: 实验室准入考试系统
tags:
  - lab-exam
  - 交接文档
  - 迭代v0.3
---

# 交接：迭代 v0.3（统计与证书导出纳入教师数据）— 2026-09-17

> **新 session 先读本文**。状态：**已推 main、已部署测试环境、两轮测试环境复验全部通过**，无 pending 代码工作；对外待业务方/测试老师最终认可。

## 一、当前状态（一句话）

教师考生作为**独立维度**接进统计与证书导出（v0.3），统计页加「导出内容」只导教师（v0.3.1），并按测试环境反馈修掉统计页贴边/间距与选择器不可见（v0.3.2）。commit `6466abb` + `fe87ad6` 已在 main，测试环境构建 `index-DbG_pRdd.js`，**两轮复验全过**。

## 二、本次交付物

| 项 | 位置 |
|---|---|
| PRD | `D:\2026准入题库\需求确认文档-迭代版.md` §7 / §8（v0.3、v0.3.1、v0.3.2 三行变更记录） |
| 详细记录 | [[lab-exam-2026-09-17-v03-teacher-dimension-stats-export]] |
| 坑与根因 | [[避坑指南]] #22 |
| 验收清单 | [[避坑指南-验收清单]] #22（全部勾选，含两轮测试环境实测数据） |
| 截图 | `D:\2026准入题库\gui-test-screenshots\2026-09-17-teacher-dimension\01~20`（01~09 本地、10~12 测试环境第一轮、13~16 本地 v0.3.2、17~20 测试环境 v0.3.2） |

改动文件：`server/src/modules/statistics/*`、`server/src/modules/certificate/*`、`server/src/modules/user/*`（keyword/工号搜索）、`web/src/views/school-admin/statistics.vue`、`web/src/views/college-admin/statistics.vue`。

## 三、业务方拍板 4 条（口径，别改）

1. 教师**单独维度**，不与学生 KPI 合并；
2. 学院统计加「本院教师」一行；
3. 证书页「考生类型」做成界面可选筛选；
4. 导出取消 2000 条上限。
5. （v0.3.1 追加）导出内容可选择：导出全部考生 / 仅导出学生 / 仅导出教师——**只影响导出，不动页面 KPI 口径**；默认导出含学生+教师全部考生。

## 四、测试环境复验结论（可直接引用）

- **第一轮（`index-BSkJxAPJ.js`）**：部署前 `?scope=school&audience=TEACHER` → 400「property audience should not exist」，部署后 → 200；统计导出 202 行 = 学生 180 + 教师 22，含「考生类型」列；证书 14 = 学生 10 + 教师 4；按班级筛 + 教师 → 0 条；全校 KPI 学生 8477 / 教师 306；学院（李卓）本院教师 60。
- **第二轮（`index-DbG_pRdd.js`）**：全校/学院统计 1440 与 390 实测——标题、分组标题、KPI 卡全部落在卡片内容起算点（比卡片边框缩进 20px），两张表间距 20（改前 0），手机标题不再折成两行、横向溢出 0；「导出内容」标签可见；选「仅导出教师」只发 `audience=TEACHER` 请求且 KPI 不变。

## 五、环境事实（易踩）

- **Obsidian 库**：本机 Obsidian 打开的是 `C:\Users\dfjq\Documents\Obsidian Vault`（注册表里唯一 `open:true`）。`D:\MyBrain` 未注册进 Obsidian；本次已把 [[避坑指南]] / [[避坑指南-验收清单]] 放进本库项目目录，后续更新写这里。
- **测试环境账号**：admin / oceg2026（SCHOOL_ADMIN）；李卓 BN100009014 / 123456（COLLEGE_ADMIN，`need_change_password` 已复原为 1）。
- **测试库**：`mysql://lab_exam_rw:***@192.168.0.165:13306/lab_exam`（本机 `server/.env` 指向无关的 localhost 库，要覆盖 DATABASE_URL）。
- **前端登录态存 sessionStorage**（`token`/`refresh_token`/`csrf_token`），注入别写错 storage；cookie 模式需 `X-CSRF-Token`。
- **内置浏览器截图**若报 `browser screenshot activity capture failed for guest`，改用本机 Edge + `web/node_modules/playwright-core`（`channel:'msedge'`）直连出图。

## 六、待办 / 待拍板

- 无代码待办。等测试老师/业务方对新页面观感与导出体验的最终反馈。
- 正式环境尚未部署本次改动（`6466abb` + `fe87ad6`）；正式库仍有历史遗留：判断题题干错位修复 SQL `D:\claude-work\lab-exam\03_fix_questions_prod.sql`、学校管理员密码 SQL `fix-school-admin-password.sql` 均**待运维执行**（与本迭代无关）。
- 仓库当前有其他工作流的未提交改动（`server/src/modules/exam/exam.service.ts` 及其 spec、`AppFormDialog.vue`、若干管理页面），**不属于本次迭代**，勿一并提交。

## 相关

- [[lab-exam-2026-09-17-v03-teacher-dimension-stats-export]]
- [[避坑指南]] · [[避坑指南-验收清单]]
- [[session-handoff-2026-09-16-full-regression-testenv]]（上一份全量回归交接）
- [[session-handoff-2026-09-07-v02-college-admin-exam-teacher-candidate]]（v0.2 迭代）