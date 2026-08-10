---
name: session-handoff-lab-exam-login-fix-2026-08-07
description: 实验室准入考试系统测试环境登录修复：数据库为空、seed 修复、前端认证模式改为 bearer
metadata:
  node_type: memory
  type: project
  project: lab-exam
  date: '2026-08-07'
  modified: '2026-08-07T17:30:00Z'
---
## 当前状态

测试环境 CORS 引号问题已修复，跨域通了。但登录时报 `{"code":1001,"message":"用户名或密码错误"}`，进一步排查发现 **测试数据库 `users` 表为空**，没有任何账号。

已通过本机直连测试数据库执行 `npx prisma db seed` 解决，seed 成功：
- Colleges: 6
- Majors: 34
- Classes: 85
- Students: 120
- 默认账号：`admin/123456`、`T001/123456`、`T1001/123456`

seed 后再次登录，页面提示"登录成功"但无法跳转。排查发现 **前端 Local Storage 为空，没有保存 `token`**。根因是 `web/.env.production` 中 `VITE_AUTH_MODE=cookie`，但当前部署实际应为 bearer 模式。

## 已提交变更（main 分支，commit a7965a0）

| 文件 | 说明 |
|------|------|
| `server/prisma/seed.ts` | `import * as bcrypt from 'bcrypt'` 改为 `bcryptjs`，与项目依赖保持一致，解决 seed 执行失败 |
| `server/prisma/migrations/20260807000000_add_missing_timestamps/migration.sql` | 为 `user_roles`/`college_admins`/`teacher_classes` 补 `created_at`/`updated_at`，与 `schema.prisma` 保持一致 |
| `web/.env.production` | `VITE_AUTH_MODE` 由 `cookie` 改为 `bearer`，解决登录成功不跳转 |

## 待办事项

1. **重新 build + 部署前端**
   ```bash
   cd D:\2026准入题库\web
   npm run build
   ```
   把 `dist/` 部署到测试服务器 Nginx 指向的前端目录。

2. **验证登录**
   - 刷新 `https://lab-exam-test.oceghome.com`
   - 用 `admin/123456` 或 `T1001/123456` 登录
   - F12 → Application → Local Storage 应出现 `token`
   - 自动跳转到 `/change-password` 改初始密码
   - 改完密码后应能进入对应角色首页

3. **后端同步（如运维需要重新部署后端）**
   ```bash
   cd /data/server/lab-exam
   git pull origin main
   npm run build
   npx prisma migrate deploy
   pm2 restart lab-exam
   ```
   当前测试数据库已 seed 过，如重新执行 `npx prisma db seed` 会清空数据，需确认无业务数据后再跑。

## 已知关键事实

- 测试域名：`https://lab-exam-test.oceghome.com`
- 部署目录：`/data/server/lab-exam`
- 数据库连接串：`mysql://lab_exam_rw:ZV9Se4awUevt@192.168.0.165:13306/lab_exam`（本机 IP 需白名单，当前已可连）
- 后端 `AUTH_MODE`：之前运维 `.env` 截图为 `bearer`
- 前端 `VITE_AUTH_MODE`：已改为 `bearer`（`.env.production`）
- 登录限流：`auth.controller.ts` 中 5 分钟最多 5 次，测试环境如频繁点登录会触发 `1003`（用户说不用管）

## 关联记忆

- [[session-handoff-lab-exam-deploy-cors-2026-08-07]] — 本日前一阶段：CORS 启动日志、all-exceptions 调试输出、CORS_ORIGIN 配置
- [[session-handoff-lab-exam-deploy-fix-2026-08-06]] — 部署修复（Prisma/Redis/bcrypt/puppeteer）
- [[lab-exam-deploy-status-2026-08-06]] — 部署状态总览

## Why

本次问题链：CORS 修复 → 数据库无账号 → seed 依赖/表结构 bug → 前后端认证模式不一致。每一步都需要客观日志/数据验证，不能靠猜测。

## How to apply

新 session 启动后，直接问用户："前端 build 部署了吗？现在 Local Storage 里有没有 `token`？" 根据结果判断是前端部署未生效还是后端 `/auth/me` 接口问题。


## 2026-08-07 后续发现：菜单/页面合并改动丢失

用户登录成功后，发现测试环境前端菜单/页面与本地不一致：

1. 本地已将"基础数据导入"合并到"人员管理"页（页内右上角有 [批量导入] [新增师生]）
2. 本地"人员管理"已改名为"师生管理"
3. 本地"专业管理"和"班级管理"已合并到"学院管理"下

### 根因

2026-08-05 本地验证时这些改动已在 `feat/art-design-pro-migration` 分支完成，但**未 commit、未 push**。后来切回 `main` 分支，该分支改动丢失。

参考记忆：[[session-handoff-lab-exam-local-verify-2026-08-05]]

### 需要重新实现的改动

| 文件 | 内容 |
|------|------|
| `web/src/router/menu.ts` | 学校管理员侧边栏结构调整：学院管理下挂学院信息/专业管理/班级管理；管理员设置下挂学校管理员/学院管理员；"人员管理"改"师生管理"；移除独立"基础数据导入"菜单 |
| `web/src/router/index.ts` | 可能的路由调整（如默认首页、别名等） |
| `web/src/views/school-admin/users.vue` | 标题改为"师生管理"，页面内增加"批量导入"入口按钮 |
| `web/src/views/school-admin/data-import.vue` | 调整导入页面，可能改为可从师生管理页进入 |

目标菜单结构：

```
首页
学院管理
├── 学院信息
├── 专业管理
└── 班级管理
管理员设置
├── 学校管理员
└── 学院管理员
师生管理          ← 右上角 [批量导入] [新增师生]
教师分班管理
题库管理
证书导出
全校统计
```

### 新增待办

1. 重新实现上述菜单/页面合并改动
2. commit + push 到 main
3. build 前端并部署到测试环境
4. 验证测试环境菜单与本地一致

### 注意

- 当前测试环境前端已部署为 bearer 模式版本，可正常登录
- 限流仍是 5 分钟 5 次（用户说不用管）
- 如需继续排查页面切换卡顿，也记录在 2026-08-05 的 memory 中
