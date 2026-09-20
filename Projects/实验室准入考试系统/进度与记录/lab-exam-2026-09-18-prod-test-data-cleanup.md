---
title: 2026-09-18 正式环境测试数据清理（06号执行单）
tags:
  - 实验室准入考试
  - 数据清理
date: '2026-09-18'
status: 已闭环
---

# 2026-09-18 正式环境测试数据清理（06_clean_test_exams_prod）

## 做了什么

- 交付 `D:\claude-work\lab-exam\06_clean_test_exams_prod.sql` + 执行单文案（不进 git，交运维）：前置检查（exams=8 且全部 09-18 创建）→ 7 张 `_bak_20260918` 备份表 → 7 条 DELETE（JOIN 备份表，删界=备份界）→ 回执（0/0/0/0 + questions=1866/users=8753 未动）→ 回滚语句。
- **运维已执行，API 独立复验：`GET /api/exams` total=0**，19 张试卷及 paper_questions/exam_events/certificates/paper_generation_jobs/student_attempts 连带清光。
- SQL 自检三层：schema 逐列核对 + 8 个考试 ID 与 API 实测机器比对（零误差）+ 测试库 EXPLAIN 干跑 7 条 DELETE JOIN（零语法错误）。

## 清理范围清单（8 场，全部 2026-09-18 创建）

测(李文秀)/1(朴日弘)/999(张凯悦)/测试禁用学生·1/测试学生禁用/测试学生/测试2/测试第一个（老师）（后 5 场张凯悦）——标题全含「测试/测」，成绩为试做特征（100/84/80/4）。

## 残留与决策（重要）

- 运维执行后师生管理仍有测试痕迹：**张凯悦 BN100009258**（09-18 创建的临时教师账号，08-31 实测正式库无此号）与**测试教师 100029018**（09-02 测试轮创建）两个 TEACHER 账号。
- 后端无删除用户接口（users.controller 只有改状态），账号只能 SQL 删或界面禁用。
- **用户拍板：账号保留不删**（学院管理员角色用户已自行移除，现仅剩沈春洋/陈冰冰 SCHOOL_ADMIN）。
- 李文秀/朴日弘为 09-02 金智导入真实教师，不动。

## 教训

- 测试数据清理范围要一开始就**覆盖用户维度**：考试删了，但为测试创建的账号会留在师生管理。下次交付清理 SQL 前先扫 `createdAt` 异常的用户。
- 用户管理无删除接口是产品现状，测试账号的处置（删/禁/留）需用户拍板。

关联：[[lab-exam-2026-09-18-question-enable-blocked-and-csrf-selfheal]]、[[lab-exam-2026-09-18-teacher-participation-rate-36-percent]]
