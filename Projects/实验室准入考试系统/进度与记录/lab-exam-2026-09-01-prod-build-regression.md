---
date: '2026-09-01'
description: 2026-09-01 正式环境 build 后回归：e8a8967 移动端自适应 + e627ab8 切屏 off-by-one 双修复正式线上验证（bundle 指纹、admin 登录跳转、手机视口三页、抽屉、考试数）
name: lab-exam-2026-09-01-prod-build-regression
tags:
  - lab-exam
  - prod-verify
  - mobile-adaptive
  - leave-force-submit
type: project
---
# 2026-09-01 正式环境 build 后回归验证

**前置**：[[session-handoff-2026-09-01-teacher-mobile-and-leave-force-submit]] P0 待办（运维已 build 正式）。

## 1. 产物确认 ✅

- 正式 index.html 引 `index-SV2mKqn8.js`（指纹与 08-31 不同，新构建已上线）。
- 主 bundle 含特征字符串：`menu-toggle`×1、`mobile-mask`×1、`sidebar-open`×1 —— **e8a8967 移动端自适应代码在正式产物内**。
- auth chunk（`auth-BIWhAOdb.js`）含 `X-CSRF-Token`，主 bundle 含 `csrf_token` —— **cookie 认证模式构建生效**（VITE_AUTH_MODE=cookie）。

## 2. P0-1 admin 登录跳转 ✅

- admin / `oceg2026` → 点击登录 → URL `/login` → `/school-admin`。
- 学校管理首页渲染完整：侧栏 8 项菜单（首页/学院管理/权限管理/师生管理/教师分班管理/题库管理/证书导出/全校统计）、用户信息「系统管理员 / SCHOOL_ADMIN」、概览卡（8 学院 / 8473 学生 / 278 教师 / 2001 题）。
- **cookie+CSRF 链路正常，登录不跳转问题正式环境未复发**。

## 3. P0-2 手机视口 390×844 教师端三页 ✅

admin 可访问 /teacher 路由（面包屑「教师首页」），逐页实测：

| 页面 | clientWidth | scrollWidth | 侧栏 left | 结果 |
|---|---|---|---|---|
| /teacher | 390 | 390 | -260 | ✅ 无溢出 |
| /teacher/classes | 390 | 390 | -260 | ✅ 无溢出 |
| /teacher/statistics | 382 (含滚动条) | 382 | -260 | ✅ 无溢出 |

- 「打开菜单」汉堡按钮存在（menu-toggle 生效）；点击后侧栏 left -260→0、遮罩 390px 满屏 block。
- 遮罩点击关闭侧栏（left→-260、遮罩消失）✅；抽屉内点击菜单项「师生管理」→ 跳转 /school-admin/users **且自动收起** ✅。
- 三页内容正常渲染（统计页表头完整：姓名/学号/班级/考试/状态/次数/分数/通过/证书编号，空数据预期——正式库无考试）。

## 4. P0-3 切屏强制交卷 ⚠️ 待补验

- 接口实测 `GET /api/exams?page=1&pageSize=1` → `{total: 0, list: []}` —— **正式库仍无考试**。
- 无考试无法触发 leave 强制交卷；测试环境已验证（第 3 次 LEAVE 才 AUTO_SUBMIT，[[labexam-leave-force-submit-off-by-one]]），正式环境**有考试后补验**。

## 结论

正式环境双修复（e8a8967 / e627ab8 前端部分）回归验证通过；唯一遗留为正式库无考试数据的端到端验证（切屏 + 交卷 1404）。

截图：`gui-test-screenshots/2026-09-01-prod-regression/`（01 学校管理手机视口、02 教师首页抽屉打开、03 统计页手机视口）。