---
date: '2026-08-12'
tags:
  - lab-exam
  - todo
  - 上线前
  - 安全
  - 评审遗留
status: pending
type: todo
---

# 上线前待办清单（评审遗留问题）

> 由 AI 评审生成，供开发/维护的任何 AI（Claude Code、Hermes 等）上线前逐项处理。
> 上线发布前必须逐条核对，处理完一项勾一项。

---

## P1-4 登录限流：上线前必须从宽松值收紧（最高优先级）

**状态：待处理（上线前改）**

### 问题
- `server/src/modules/auth/auth.controller.ts` 第 33 行：
  `@Throttle({ ttl: 5 * 60 * 1000, limit: 1000 }) // TODO: 测试环境临时放宽，上线前恢复为 5`
- 当前 5 分钟允许 1000 次登录尝试 = 无防爆破。

### 处理方案（已评审确认）
1. `server/src/config/index.ts` 的 `registerAs('app', ...)` 增加：
   `loginThrottleLimit: parseInt(process.env.LOGIN_THROTTLE_LIMIT, 10) || 5`（默认 5）
2. `server/src/modules/auth/auth.controller.ts` 删除硬编码 TODO 注释，
   改为在 controller 内用 `this.configService.get('app.loginThrottleLimit')` 动态构造装饰器参数。
3. `.env.example` 与 `deploy/.env.example` 增加：
   `# 登录限流：同一 IP 5 分钟内最大登录尝试次数（生产建议 5，测试可放宽）`
   `LOGIN_THROTTLE_LIMIT=5`

### 环境值约定
- **测试/开发环境**：`.env` 设 `LOGIN_THROTTLE_LIMIT=1000`（保持宽松，测试人员手动登录不卡）
- **生产环境**：`.env` 设 `LOGIN_THROTTLE_LIMIT=5`

### 验证标准
- `npm run build` 通过
- .env 设 1000 时连续登录 5+ 次不报 1009；设 5 时第 6 次返回 `{ code: 1009, message: '请求过于频繁' }`
- 现有 jest 测试（23 条）全绿

### 注意
- 测试环境部署机的 `.env` 在服务器上，需运维/本人手动加 `LOGIN_THROTTLE_LIMIT=1000`，
  否则默认值 5 会生效、测试人员 5 分钟只能试 5 次登录。

---

## P1-3 submit 并发双击无原子保护（建议做，待拍板）

**状态：待确认**

- 问题：`submit` 先查 `IN_PROGRESS` 再 update，两个并发请求都可能通过检查，重复判分+重复计事件
- 证书有唯一约束兜底（不会重发证书），但事件记录会重复
- 建议改法：状态切换改为条件更新 `updateMany({ where: { id, status: IN_PROGRESS } })`，原子切换
- 注意：`student-exam.service.ts` 第 622 行的 `updateMany` 是缺考自动标注用的，与本问题无关，勿混淆

---

## P1-2 角色快照 vs 数据范围实时（已知取舍，不改代码）

**状态：已确认可接受**

- RolesGuard 用 JWT 里的 roles（登录时签发，最长 2h），数据范围实时查库
- 被移除管理员在 token 过期前仍能调管理接口，但看不到数据（数据范围兜底）
- 已在评审报告标注为已知取舍，写进文档即可，不改代码

---

## P2 中风险（排期做）

- [ ] 管理端操作无审计日志（谁删了考试、谁改了权限、谁导了数据，查不到）
- [ ] 题库权限：COLLEGE_ADMIN 完全碰不到题库（@Roles(SCHOOL_ADMIN) 限定）——是否符合业务预期待确认
- [ ] 同学院另一教师能否修改别人的 DRAFT 考试（需实测确认 publisher 是否硬约束）

## P3 低风险（规范类）

- [ ] 无监控/告警配置（上线后加进程监控 + 数据库备份验证）
- [ ] users.service.ts 单文件 1100+ 行偏大，可拆（非紧急）

## 运维层

- [ ] 数据库备份策略是否验证过恢复？考试数据丢了没法重考，建议演练一次

---

## 已关闭项

- [x] P0 补测试：`server/src/modules/student-exam/student-exam.service.spec.ts`（7 用例）、
  `server/src/modules/auth/services/data-scope.service.spec.ts`（15 用例），2026-08-12 全绿
- [x] P1-2 已知取舍确认