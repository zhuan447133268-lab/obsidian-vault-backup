---
name: lab-exam-cookie-mode-migration-checklist-2026-08-31
description: 2026-08-31 测试环境切换为 cookie 认证模式检查清单（与生产环境统一）
type: project
date: '2026-08-31'
status: in_progress
---
# 2026-08-31 测试环境切换 cookie 认证模式检查清单

**目标**：将测试环境认证模式从 `bearer` 统一为 `cookie`，与生产环境保持一致，避免环境差异导致的线上问题。

**决策**：已选方案 B（根治），由 [[lab-exam-2026-08-31-production-issues-fixed]] 延伸。

---

## 一、历史原因：为什么测试环境当初用了 bearer？

根据 `git log` 追溯：

1. **2026-07-08**（`1b57f7a`）：项目初始同时实现了 **Bearer / Cookie 双模式**，设计意图就是 bearer 用于开发、cookie 用于生产。
2. **2026-08-04**（`d0205c9`）：安全加固，增加了 CORS 白名单、登录限流、强制改密、cookie maxAge 等，cookie 模式的安全性得到完善。
3. **2026-08-07**（`a7965a0`）：提交 `fix: 修复测试环境 seed 失败及登录后无法跳转问题`，其中把 `web/.env.production` 从 `cookie` 改为 `bearer`，commit message 明确说明：
   
   > "解决前端登录成功后未保存 token 导致无法跳转的问题"
   
   **这次改动并没有修复 cookie 模式的代码 bug，而是把生产默认配置也切到了 bearer，相当于绕过了问题。**
4. **后来**：生产环境又通过 **未纳入 git 的 `web/.env.production.local`** 把 `VITE_AUTH_MODE` 改回 `cookie`。
5. **测试环境**：没有 `.env.production.local` 覆盖，因此一直沿用 `bearer`。

**结论**：测试环境用 bearer 不是因为设计如此，而是 2026-08-07 一次临时修复留下的历史债务。现在代码已经支持 cookie 正常运行，可以安全切回。

---

## 二、当前配置事实（基于仓库代码）

### 2.1 本地开发环境
- 后端 `server/.env`：`AUTH_MODE="bearer"`
- 前端 `web/.env.development`：`VITE_AUTH_MODE=bearer`
- 状态：✅ 一致

### 2.2 生产环境
- 后端：配置为 `cookie` 模式（从 admin 登录 403 问题反推）。
- 前端 `web/.env.production`：默认 `VITE_AUTH_MODE=cookie`（**已修改并 push**）。
- 前端 `web/.env.production.local`：`VITE_AUTH_MODE=cookie`（覆盖默认，未纳入 git）。
- 状态：✅ 一致。

### 2.3 测试环境
- 后端：待 Jenkins 重新部署后生效 `cookie`。
- 前端：待 Jenkins 重新 build 后生效 `cookie`。
- 状态：🔄 切换中。

---

## 三、已完成的代码修改（已 push main）

**commit**: `68c97ba` — `chore(deploy): 测试/生产环境认证模式统一为 cookie`

### 3.1 `web/.env.production`
```diff
- VITE_AUTH_MODE=bearer
+ VITE_AUTH_MODE=cookie
```

### 3.2 `docker-compose.yml`
```diff
- AUTH_MODE: bearer
+ AUTH_MODE: cookie
+ CSRF_SECRET: ${CSRF_SECRET:-lab-exam-csrf-secret-dev-only}
+ COOKIE_SECURE: "false"
+ COOKIE_SAME_SITE: lax
```

### 3.3 未 push 的本地变更
- `server/src/modules/exam/exam.service.spec.ts`：单元测试文件，按用户偏好保留在本地 staged，未 commit/push。

---

## 四、Jenkins 部署步骤

1. [x] **提交并 push 代码变更**（`web/.env.production` + `docker-compose.yml`）。
2. [ ] **Jenkins 重新 build 前端**。
   - 注意：如果 Jenkins 构建脚本里有 `VITE_AUTH_MODE=bearer` 的硬编码注入，需要一并去掉。
   - 如果 Jenkins 工作区残留 `web/.env.production.local`，建议删除或确认其内容不会覆盖为 `bearer`。
3. [ ] **测试环境后端重启**。
   - 如果用 `docker-compose.yml`：重新 `docker-compose up -d`。
   - 如果用手动部署：修改 `server/.env` 中 `AUTH_MODE=cookie`，重启服务。
4. [ ] **浏览器清缓存**，强制刷新测试环境页面。

---

## 五、验证清单（必须全部通过）

### 5.1 登录与认证
- [ ] admin 登录后能正常跳转到首页。
- [ ] 学校管理员登录后能正常跳转。
- [ ] 教师登录后能正常跳转。
- [ ] 学生登录后能正常跳转。
- [ ] 登录后浏览器 Network 中能看到 `access_token` 和 `refresh_token` 两个 Cookie。
- [ ] 后续 API 请求头中携带 `X-CSRF-Token`。
- [ ] `/auth/me` 返回 200 且用户信息正确。

### 5.2 管理端核心操作
- [ ] 创建一场新考试。
- [ ] 为考试选择参考班级/学生。
- [ ] 发布考试。
- [ ] 查看考试列表。
- [ ] 编辑考试信息。
- [ ] 学生成绩统计页面正常加载。
- [ ] 导出成绩单/证书（如有）。

### 5.3 学生考试流程
- [ ] 学生进入考试，能正常加载试卷。
- [ ] 答题过程中无 403/1404 弹窗。
- [ ] 切屏/焦点/心跳事件正常上报（Network 中可见，且无报错）。
- [ ] 交卷成功。
- [ ] 交卷后不再出现「没有进行中的考试」1404 弹窗。
- [ ] 学生能查看成绩/证书。

### 5.4 重新生成试卷
- [ ] 在管理端对任意学生点"重新生成试卷"。
- [ ] 新试卷无重复题（重点抽查 BN100009258 同款场景）。

### 5.5 登出与重新登录
- [ ] 点击登出后，Cookie 被清除。
- [ ] 重新登录后恢复正常。

---

## 六、生产环境同步

测试环境全部验证通过后，再同步生产环境：

1. [ ] 确认生产后端 `.env` 仍为 `AUTH_MODE=cookie`。
2. [ ] 确认生产前端构建使用 `VITE_AUTH_MODE=cookie`（现在 `.env.production` 默认就是 cookie）。
3. [ ] 生产环境可考虑删除 `web/.env.production.local`，避免未来维护困惑。
4. [ ] 选择低峰期部署。
5. [ ] 部署后验证 admin 登录跳转。
6. [ ] 部署后验证学生考试交卷无 1404。
7. [ ] 部署后验证 BN100009258 试卷重新生成无重复题。

---

## 七、回滚方案

如果测试环境切换后出现大面积问题，按以下顺序回滚：

1. **前端回滚**：将 `VITE_AUTH_MODE` 改回 `bearer`，重新 build。
2. **后端回滚**：将 `AUTH_MODE` 改回 `bearer`，重启服务。
3. **清缓存**：浏览器强制刷新。
4. **验证**：确认登录和核心流程恢复。

> 生产环境回滚同理，但需提前准备好回滚包或回滚命令。

---

## 八、待确认/待补充

- [ ] Jenkins 构建脚本里是否有 `VITE_AUTH_MODE` 硬编码注入。
- [ ] Jenkins 工作区是否残留 `web/.env.production.local`。
- [ ] 测试环境后端是否用 `docker-compose.yml` 部署。
- [ ] 是否需要同步修改本地开发环境为 `cookie`（如果希望本地-测试-生产三线一致）。

---

## 关联

- [[lab-exam-2026-08-31-production-issues-fixed]]
- [[session-handoff-lab-exam-prod-import-sql-regenerated-2026-08-28]]
- [[lab-exam-deploy-checklist]]
