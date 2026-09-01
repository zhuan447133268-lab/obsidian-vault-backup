---
date: '2026-08-31'
description: 2026-08-31 会话交接：测试环境 cookie 认证模式切换待运维确认修改环境
name: session-handoff-lab-exam-cookie-mode-2026-08-31
status: pending
tags:
  - lab-exam
  - session-handoff
  - cookie-mode
  - deploy
type: project
---
# 2026-08-31 会话交接：cookie 模式切换待运维确认环境

**时间**：2026-08-31  
**会话目的**：将测试环境认证模式从 bearer 统一为 cookie，与生产环境保持一致。  
**当前状态**：代码已 push，Jenkins 前端构建成功，但测试环境后端实际运行仍为 bearer，待运维确认修改的是哪个环境。

---

## 已完成的改动

代码已 push 到 main：

1. `web/.env.production`：`VITE_AUTH_MODE` 默认由 `bearer` 改为 `cookie`。
2. `docker-compose.yml`：`AUTH_MODE` 由 `bearer` 改为 `cookie`，补充 CSRF 相关配置。
3. `web/package.json`：锁定 `vant` 版本为 `4.10.0`，避免 vant@4.10.1 的 workspace 依赖导致 pnpm 安装失败。

本地保留未 push 的单元测试文件：`server/src/modules/exam/exam.service.spec.ts`（staged）。

---

## 当前卡壳点

### 测试环境后端未切换到 cookie

- 测试环境地址：`https://lab-exam-test.oceghome.com/`
- 无论 admin 还是教师账号登录，`/auth/login` 返回的都是 `accessToken` + `refreshToken`。
- **cookie 模式下应该返回 `csrfToken`**。
- 结论：测试环境实际运行的后端 `AUTH_MODE` 仍是 `bearer`。

### 运维反馈"已发布"但效果不符

- 运维表示已重新发布，但测试环境后端模式未变。
- **关键疑问**：运维修改的是测试环境还是生产环境？
- 测试环境后端由 ansible `node_standard.yml` + supervisor 管理，不是 docker-compose。仓库里的 `docker-compose.yml` 改动对当前测试环境部署不直接生效。

---

## 新 session 继续事项

1. **确认运维修改的是哪个环境**
   - 直接问运维：修改的是测试环境（lab-exam-test）还是生产环境？
   - 要求运维提供：修改的文件路径、执行的命令、重启后的状态截图。

2. **如果修改的是测试环境**
   - 让运维执行排查命令，找到 lab-exam 实际读取的 `.env` 或 supervisor 配置文件。
   - 确认 `AUTH_MODE` 实际值，改为 `cookie` 后重启。
   - 重新验证 admin/教师/学生登录。

3. **如果修改的是生产环境**
   - 立即验证生产环境 admin 登录是否正常。
   - 如果生产环境正常，说明后端切换逻辑正确，测试环境需要按同样方式处理。
   - 如果生产环境异常，考虑回滚。

4. **验证测试环境全部功能**
   - admin/学校管理员/教师/学生登录与跳转。
   - Cookie 和 X-CSRF-Token 是否正常。
   - 管理端创建/发布考试。
   - 学生考试流程（进入、答题、交卷，无 1404）。
   - 重新生成试卷无重复题。

---

## 给运维的关键质问

直接复制发送：

> 测试环境 `https://lab-exam-test.oceghome.com/` 登录接口仍返回 `accessToken`，不是 `csrfToken`，说明后端 `AUTH_MODE` 还是 bearer。
>
> 请确认：
> 1. 你刚才修改的是测试环境还是生产环境？
> 2. 具体改了哪个文件？路径是什么？
> 3. 执行了什么重启命令？
> 4. 请把修改的配置文件内容和重启后的状态截图给我。
>
> 如果线上沟通效率低，建议直接远程共享 192.168.2.13 屏幕排查。

---

## 关联

- [[lab-exam-cookie-mode-migration-checklist-2026-08-31]]
- [[lab-exam-2026-08-31-production-issues-fixed]]
- [[lab-exam-deploy-checklist]]
