---
name: lab-exam-2026-08-31-zhangkaiyue-login-rootcause
description: 张凯悦正式环境"进不去"根因定案——zxcvbnm123 是测试环境密码，正式环境密码是 123456（initial 密码）且登录改密链路 CSRF 无 bug；之前会话看到的全站 1004 系手动 refresh 污染会话的副作用
type: project
date: 2026-08-31
---

# 张凯悦正式环境「进不去」根因定案（2026-08-31 结论）

> 复核目标：张凯悦（正式学号 2302220248）在正式环境 lab-exam.oceghome.com 登录不上去，究竟是 bug 还是密码问题。

## 结论（可直接对外回复）

1. **不是 bug，是密码问题**：正式环境张凯悦的密码是 **123456**（导入时初始密码，need_change_password=1）；用户提供的 **zxcvbnm123 仅是测试环境密码**，在正式环境提交返回 1001「用户名或密码错误」，所以"登不上去"。
2. **改密链路 CSRF 无 bug**：干净路径实测（清空会话 → 123456 登录 → 强制改密页 → 提交改密【故意用错误原密码，零副作用】）返回 `1202 原密码错误`——说明前端携带页面 csrf_token 的请求已被 CSRF 校验放行，进入业务层。只要原密码填 123456、新密码合规（8-20 位含字母数字），即可改密成功。
3. **之前会话发现的全站 1004「CSRF Token 缺失或错误」是排查副作用，不是真实用户路径 bug**：排查过程中手动 `POST /api/auth/refresh` 会把 httpOnly cookie 里的 access_token 换成新 jti，而 sessionStorage 的 csrf_token 仍是旧 jti 对应的 → 后续所有带旧 csrf 的请求全部 403/1004，直至重新登录才恢复。**用户正常登录后不做 refresh，csrf 与 token 始终配套**。

## 用户认知澄清（2026-08-31 追问）

用户反馈：zxcvbnm123 应是在正式环境登录后张凯悦自己改的密码，且她已用该账号测试了几个问题。

**实测证据显示相反——zxcvbnm123 是测试环境密码，正式环境一直是 123456：**

| 环境 | 2302220248 / 123456 | 2302220248 / zxcvbnm123 |
|---|---|---|
| 测试 lab-exam-test.oceghome.com | 1001 ✗ | **登录成功 ✓（code 0）** |
| 正式 lab-exam.oceghome.com | **登录成功 ✓（code 0）** | 1001 ✗ |

- 张凯悦是在**测试环境**把密码改成了 zxcvbnm123（测试环境 8-31 数据与正式不同源，测试库有改密记录、hash 对应 zxcvbnm123；正式库无直连但登录接口结果已足够定案）。
- 正式环境她从未成功改密过（正式库该账号 hash 仍=123456，与 01_user_data.sql 一致，且 8-31 新版 SQL 未在正式库重跑）。
- 她"进不去"的是正式环境，原因正是拿了测试环境的密码 zxcvbnm123 去登录正式环境 → 1001。
- 她在两个环境测试过多个问题，但**密码各自独立**，改过密码的只有测试环境。

## 证据链（2026-08-31 浏览器实测）

| 步骤 | 结果 | 说明 |
|---|---|---|
| 2302220248 / zxcvbnm123（正式） | 1001 | 测试环境密码，正式不认 |
| 2302220248 / 123456（正式，干净会话） | 登录成功 → 跳转 /change-password | csrf_token 写入 sessionStorage（64 位） |
| 页面已存 csrf 调 GET /auth/me | 200 code 0 | 前端同源请求配套 |
| 页面已存 csrf 调 PATCH /users/me/password（**错误原密码**） | 400 code 1202「原密码错误」 | **CSRF 已放行**，卡在业务校验（故意填错，未真改密） |
| 对照组：手动 refresh 后 sessionStorage 里旧 csrf 调 /me | 403 code 1004 | 会话被污染时的状态，非用户路径 |

## 机制备忘（cookie 认证模式）

- access_token / refresh_token 放 **httpOnly cookie**（auth.controller login/refresh setCookie）；JwtAuthGuard 的 validateCsrf 计算 `expected = HMAC_SHA256(csrfSecret, 当前 token.jti)`，与请求头 x-csrf-token 比对，不一致 → 403 code 1004。
- 登录响应里的 csrfToken 与同一签发的 accessToken jti 配套；refresh 响应新 csrfToken 与新 accessToken jti 配套。**前端 cookie 模式只需要在登录/refresh 成功后把 csrfToken 写入 sessionStorage（stores/auth.ts loginAction/refreshAction 已做）**。
- 排查教训：**不要手动调 /auth/refresh 后继续用旧 csrf 做页面同会话验证**，会污染浏览器会话产生"假 bug"。

## 遗留

- 张凯悦正式环境密码处置：告知她正式密码是 123456（引导改密），或由管理员（沈春洋/陈冰冰）协助重置；她需要的是**教师角色**才能在教师端看数据——正式库她目前只有 STUDENT 行（2302220248），**无教师账号**。
- 学校管理员密码修复 SQL（fix-school-admin-password.sql）仍待正式库执行。

## 关联

- [[lab-exam-2026-08-31-prod-env-verify]]（正式环境复核）
- [[labexam-auth-mode-mismatch]]（cookie/CSRF 整体机制）