---
tags: [lab-exam, handoff, bugfix, v02]
date: 2026-09-16
---

# 2026-09-16 双角色账号「看不到自己发的考试」排查与修复（commit fb2dec1）

## 一、测试反馈

测试人员在学院管理员发考试时发现：**同时是「教师」和「学院管理员」的账号**，管理员给自己发教师考试后，**管理员状态下看不到自己的试卷**；撤掉管理员身份（变纯教师）才能看到。询问是否为刻意做的角色互斥。

## 二、排查结论：不是角色互斥，是前端入口缺失（bug）

**后端无角色互斥**，数据链路全部放行：
- `roles.guard.ts:36` 是**集合包含**判断（`requiredRoles.some(r => userRoles.includes(r))`），不是"最高角色"限制——双角色账号含 TEACHER 即可过 `@Roles(STUDENT, TEACHER)`。
- `student-exam.controller.ts:33` `@Roles(UserRole.STUDENT, UserRole.TEACHER)`——双角色账号（如薛晓转）实测手动访问 `/student` **无 403**，考试列表正常渲染（按参考名单过滤显示）。

**真正断点在前端两处：**
1. `stores/auth.ts:38-50` `primaryRole` 优先级 `SCHOOL_ADMIN > COLLEGE_ADMIN > TEACHER > STUDENT` → 双角色登录必落 `/college-admin`；`homePath`（52-67 行）COLLEGE_ADMIN → `/college-admin`。
2. `router/menu.ts` 管理端菜单（schoolAdminMenus / collegeAdminMenus）**无任何考生答题入口** → 管理员身份下没有路能进学生端「我的考试」列表。

撤管理员 → 纯教师 → `homePath=/student` → 「碰巧」有入口。即"看到/看不到"完全取决于登录落点，与考试数据无关。

**复现实锤**：测试库 `college_admins` 2026-09-16 10:36（02:36 UTC）新增张凯悦（BN100009258）COLLEGE_ADMIN 记录；「测试教师考试」（9/16 10:38 发布）参考名单含张凯悦 BN100009258（待考）。账号=张凯悦，场景=管理员给自己发考试后无入口。

## 三、修复内容（commit fb2dec1，已推 main）

1. `web/src/router/menu.ts`：schoolAdminMenus / collegeAdminMenus 各加 `{ title: '我的考试', path: '/student', icon: DocumentChecked, roles: ['TEACHER'] }`——**仅兼任教师的管理员**显示，纯管理角色不显示。
2. `web/src/layouts/AdminLayout.vue`：menu 计算属性改用 `filterMenusByRoles(getMenusByRoles(roles), hasRole)`，让菜单项自身 `roles` 条件生效（此前 filterMenusByRoles 定义了但从未被调用）。
3. `web/src/views/student/profile.vue`：「我的」页新增「返回管理端」cell（`COLLEGE_ADMIN || SCHOOL_ADMIN` 时显示），点击回 `homePath`——校长管理员从学生端答题后可一键回管理端，形成闭环。

## 四、验证（本地 dev + 代理测试环境后端，VITE_AUTH_MODE=cookie）

- 薛晓转 100029018（TEACHER+COLLEGE_ADMIN）登录 → 落 `/college-admin`，**侧栏出现「我的考试」**（修复前无此菜单，实测对比）。
- 点「我的考试」→ 进入 `/student` 学生端考试列表（无 403；薛晓转不在参考名单故列表为空，属正常过滤）。
- 学生端「我的」页 → 显示「返回管理端」→ 点击 → 回 `/college-admin`。双向往返闭环 OK。
- `vue-tsc --noEmit` + `npm run build` 均通过。
- 纯 COLLEGE_ADMIN（无 TEACHER）不显示「我的考试」——由 menu roles:['TEACHER'] + filterMenusByRoles 保证（未用账号实测，逻辑同 school-admin 首页项去重模式）。

## 五、测试环境部署

**2026-09-16 已部署并验证通过**：Jenkins 手动 build 后测试环境新指纹 `index-DlZn6KyP.js`（产物已含「我的考试」字符串）。用薛晓转 100029018（TEACHER+COLLEGE_ADMIN）在测试环境真实网址实测：
- 登录 → 落 `/college-admin` → 侧栏 6 项含「我的考试」（修复前 5 项）✅
- 点「我的考试」→ `/student` 考试列表正常，无 403（薛晓转不在参考名单故列表空，属正常过滤）✅
- 「我的」页 →「返回管理端」→ 点击回 `/college-admin`，闭环成功 ✅
- 截图已存本机 artifacts。

**待测试人员（张凯悦）验收**：她登录后侧栏「我的考试」应看到「测试教师考试」待考卷（BN100009258 在参考名单）并可进入答题。⚠️ 提醒：浏览器多标签页共享登录 cookie、后登录顶替前会话，切账号测试看到"列表空"先确认当前标签页会话身份再判断。

## 六、部署后回归清单（张凯悦验收通过后核对）

- 张凯悦 BN100009258 登录 → 落管理端 → 侧栏「我的考试」→ 应看到「测试教师考试」待考卷 → 可答题。
- 薛晓转 100029018 登录同上（其参考名单内考试时可见）。
- 纯学院管理员账号（找一个无 TEACHER 角色的 college_admins）→ 侧栏应无「我的考试」（roles:['TEACHER'] 过滤生效）。

## 七、相关

- 2026-09-16 全量回归：[[session-handoff-2026-09-16-full-regression-testenv]]（A-H 八组全过，本次 bug 属其 B 组后续补充发现）
- 需求：[[需求确认文档-迭代版-2026-09-07]] R1/R2（学院管理员统一建考 + 教师考生）——验收清单未覆盖"管理员兼任教师"场景，本次为补充。
- 角色优先级/落点设计：`web/src/stores/auth.ts`（primaryRole/homePath/isTeacherOnly）