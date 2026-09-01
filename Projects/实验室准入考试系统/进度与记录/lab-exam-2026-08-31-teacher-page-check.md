---
name: lab-exam-2026-08-31-teacher-page-check
description: 测试老师张凯悦（BN100009258）反馈教师端页面展示不完整——排查结论：改密闸门拦截 + 提示文案与真实密码不符导致卡死；教师端三页面本身完整
type: project
date: 2026-08-31
---

# 2026-08-31 张凯悦教师端"页面展示不完整"排查（测试环境）

## 现象
测试老师张凯悦（BN100009258）反馈教师端页面展示不完整。

## 排查过程（浏览器实测 + 代码 + DB）

1. **登录即被改密闸门拦截**：张凯悦 DB 中 `need_change_password=1` → 登录成功后被路由守卫强制弹到「修改初始密码」页（router/index.ts:264-266 只放行 /change-password），教师端 /teacher、/teacher/classes、/teacher/statistics 全部不可见。
2. **提示文案与实际密码不符（卡死根因）**：改密页 placeholder 写死「初始密码为 123456」（change-password/index.vue:23），但该账号实际密码是 `zxcvbnm123`（实测登录接口：123456 → 1001 失败，zxcvbnm123 → code 0）。老师按提示输 123456 永远失败 → 卡在改密页 → 表现为"教师端页面看不到/不完整"。
3. **绕过改密后三页面本身完整**：临时置 need_change_password=0 后，/teacher/classes（5 个班，可建考/可监考标识）、/teacher（12 场考试列表，操作列齐全）、/teacher/statistics（筛选器+统计表）DOM 全部正常，布局无横向溢出（1280 视口 scrollW==clientW），创建考试对话框完整（学院固定/班级下拉/时间器均正常）。截图通道故障（activity capture failed），以 DOM 快照为证据。
4. **附带发现**：
   - 登录接口 `dataScope.classIds` 恒为空数组：auth.service.ts 登录 findUnique 的 include 缺 `teacherClasses`（data-scope.service.ts:43 拿不到 → ??[]），与页面实际班级数（5 个班，来自 getMyClassList 自行查 teacherClasses）不一致。代码缺陷，页面当前不受影响，但依赖登录 dataScope 的逻辑会误判。
   - 测试环境存在 3 场一模一样的草稿「测试」考试（8/28 15:36 ×3）脏数据。
   - 教师首页「发布」按钮 paperCount=0 时 disabled，但有 el-tooltip「需先进入详情页生成试卷」，不算无提示。

## 结论与建议
- 主因 = **测试环境账号密码（zxcvbnm123）与改密页提示（123456）不一致 + need_change_password=1**：老师不知道 zxcvbnm123 就永远进不去。测试环境账号密码约定（zxcvbnm123）与导入 SQL 默认密码（123456）不一致是根源，后续若重置测试库需统一。
- 修复建议（按需）：
  1. 测试环境：把张凯悦等测试老师的 need_change_password 置 1 前先确认密码是 123456；或直接告知老师真实密码。
  2. 代码（可选）：auth.service.ts 登录 include 补 `teacherClasses`，让 dataScope.classIds 真实返回（不影响页面，但消除隐患）。
  3. 前端（可选）：改密页提示文案不要写死 123456，可改为「请输入原密码」。

## 验证已恢复
- 测试库 `need_change_password` 已还原为 1；未改动任何密码、正式环境未触碰。

## 关联
- [[lab-exam-2026-08-31-testenv-full-recheck]]
- [[session-handoff-2026-08-13]]（BN100009258/zxcvbnm123 账号来源）