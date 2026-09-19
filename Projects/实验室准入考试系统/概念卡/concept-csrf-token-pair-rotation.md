# 概念卡：Cookie+CSRF 双凭证对与多标签页/顶号互顶

> 出自 2026-09-18「题库禁用后无法启用」排查（详见 [[lab-exam-2026-09-18-question-enable-blocked-and-csrf-selfheal]] §四）。本项目 7 月就曾记录同坑（多账号共用一个 token 槽 → 管理页集体 403），当时只记现象未修机制，09-18 老师再次踩中。

## 机制

- 后端 CSRF token = `HMAC(serverSecret, JWT.jti)`（`jwt-auth.guard.ts:50`）——**不是随机数，是 JWT 的派生值**
- 因此 **每次登录、每次 /auth/refresh 都会轮换**：新 JWT 带新 jti → 旧 CSRF 立即作废
- 存储形态天然分裂：**cookie 是浏览器级共享**（所有标签页/窗口共用一个），**CSRF 存在各标签页自己的 sessionStorage**
- 请求要「cookie + CSRF 头」配对才放行，两个错配来源：
  - **多标签页**：A 页 refresh 换新对后，B 页存的旧 CSRF 与全局 cookie 里的新 JWT 对不上 → 403(1004)
  - **顶号**：同浏览器另一账号登录，cookie 槽被覆盖，旧页面旧 CSRF 配新账号 JWT → 403(1004)

## 症状特征（识别这个坑）

- 操作**随机失败**（禁用成功、启用失败/换个浏览器又好了），与具体操作、具体数据无关
- 报 403 code=1004「CSRF Token 缺失或错误」；前端页面级 catch 常只弹笼统的「启用失败/保存失败」盖住真实 toast
- 单标签页单账号时几乎不出现（axios 拦截器会在 401 时自动 refresh 并同步存储的 CSRF）

## 处置

- **用户侧**：刷新页面重新登录即恢复（拿到新 cookie+CSRF 对）
- **代码侧（本项目 09-18 已修，`df072d5`）**：前端收到 1004 → 静默 refresh 换新 CSRF → `/auth/me` 核对账号与本标签页登录快照（`user_account`）一致 → 原请求重发一次（`_csrfRetried` 防循环；/auth/me 自身豁免防递归）
- **红线：必须核身份再重试**——cookie 是共享的，若已被别的账号顶掉，盲目重试等于**冒名执行操作**。身份不一致应清登录态引导重新登录，而不是重试

## 自检清单

- [ ] 用户报「操作随机失败/换浏览器就好」→ 先怀疑本坑，让用户报失败时的**完整报错截图**（区分 1004 vs 业务 400）
- [ ] 排查时先 curl 同账号直测 API：API 通 + 浏览器不通 = 本坑；API 也不通 = 真后端问题
- [ ] 修复方案里有没有「重试前核身份」？没有就是埋雷

## 关联

[[lab-exam-2026-09-18-question-enable-blocked-and-csrf-selfheal]]、[[lab-exam-2026-09-18-prod-500-audience-migration-missing]]（同日迁移账本坑——「手工铺底的东西不记账，记账的东西不校验」是一类问题）
