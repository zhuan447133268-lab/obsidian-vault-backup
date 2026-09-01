---
name: lab-exam-2026-08-31-prod-env-verify
description: 2026-08-31 正式环境（lab-exam.oceghome.com）复核：cookie 模式端到端就绪、admin 登录跳转修复生效；exams 空库 + 无 BN100009258 教师号，交卷/去重待有考试后补验
type: project
date: 2026-08-31
---

# 2026-08-31 正式环境复核记录（lab-exam.oceghome.com）

> 目标：验证「上面的问题」在正式环境是否已解决（交接文档六、的正式环境部署验证清单）
> 截图证据：`D:\2026准入题库\gui-test-screenshots\2026-08-31-prod-verify\`（浏览器登录→跳转改密页）

## 一、验证方法（零写操作，全程只读）

1. **API 探测**（admin 会话，curl + cookie jar + X-CSRF-Token）：
   - `POST /api/auth/login`（admin + 强密码）→ 确认认证模式
   - `GET /api/auth/me`（带/不带 X-CSRF-Token）→ 确认 CSRF 强校验
   - `GET /api/exams`、`/api/users`、`/api/users?role=TEACHER`、`/api/questions` → 数据规模
2. **前端产物指纹**（下载 `assets/index-*.js`、`auth-*.js` grep）→ 确认 `VITE_AUTH_MODE=cookie` 构建
3. **浏览器 GUI 验证**（IAB 真实点击）→ admin 登录 → 观察跳转

**未做任何写操作**：不改密码、不重新生成试卷、不删改数据（admin need_change_password=true，改密页已到但未提交新密码）。

## 二、验证结果

| 项 | 结果 | 证据 |
|---|---|---|
| 后端认证模式 | ✅ cookie + CSRF 强制 | 登录返回 `csrfToken`；`/me` 无 token → 1004「CSRF Token 缺失或错误」 |
| 前端构建指纹 | ✅ cookie 构建 | 产物含 `headers["X-CSRF-Token"]=t` 拦截器（auth-*.js） |
| admin 登录跳转 | ✅ 修复生效 | 登录成功 → 跳转 `/#/change-password` 强制改密页，不再卡登录页（08-31 核心 bug） |
| 用户数据导入 | ✅ | 8753 用户 / TEACHER 278 人（与导入清单预期 ≈278 一致）/ 题库有题（2001 条通用+专业） |
| 交卷无 1404 | ⚠️ 无法触发 | 正式环境 `exams` 表为空（API total=0），无进行中考试 |
| BN100009258 去重 | ⚠️ 无从验证 | 正式环境无 BN100009258 教师账号（张凯悦仅 STUDENT 行 2302220248），`exams` 为空 |
| 学校管理员 123456 | 未验证 | 未登录 BN100005453/IME000290（不主动测密码） |

## 三、关键事实（新 session 引用）

1. **正式环境已 cookie 化且前后端一致**：后端强 CSRF（无 token /me 直接 1004），前端产物带 `X-CSRF-Token` 注入。08-31「测试环境 bearer/正式环境 cookie 不一致」的根因在正式环境侧已闭环。
2. **正式环境数据导入已完成**：01_user_data.sql（8753 人、8 学院、278 教师）+ 题库均已在库；`exams` 表为空是**正常状态**——考试在系统内创建，不在导入 SQL 范围。
3. **BN100009258 是测试环境账号**：正式环境张凯悦无此教师号；「重新生成 BN100009258 试卷」待办在正式环境无从执行，原始出处需澄清（疑为测试环境/本地演示环境的观察）。
4. admin 账号 `need_change_password=true`，登录后强制改密——验证登录链路到此为止，**改密未执行**（避免改正式环境管理员密码）。

## 四、遗留/下一步

1. 正式环境有真实考试后：补验交卷无 1404、组卷去重（任意新卷 content_snapshot 唯一性即可）。
2. 确认「BN100009258 重复题」待办目标环境（若是测试环境，可直接关掉；测试环境 0676156 已实测生效）。
3. 学校管理员 BN100005453/IME000290 密码 123456 SQL：仍按需执行（未做）。

## 五、关联

- [[lab-exam-2026-08-31-production-issues-fixed]]（线上问题根因与修复）
- [[session-handoff-2026-08-31-testenv-full-recheck]]（测试环境全量复核）
- [[lab-exam-2026-08-31-testenv-full-recheck]]（测试环境验证记录）
- 记忆（labexam-auth-mode-mismatch：正式 cookie/CSRF vs bearer 前端）