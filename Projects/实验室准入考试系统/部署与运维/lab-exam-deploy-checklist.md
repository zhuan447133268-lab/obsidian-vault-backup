---
date: '2026-08-10'
status: active
tags:
  - lab-exam
  - 部署
  - 检查清单
type: project
---
# 实验室准入考试系统部署检查清单

> **硬规则：每次上线/部署前，必须逐项检查并打勾。未打勾项不得上线。**
> 遇到新的部署类问题，必须追加到本清单对应章节。

---

## 一、代码与构建

- [ ] 后端代码已从仓库拉取到最新（`git pull`）
- [ ] 后端已重新 build 成功（`npm ci && npm run build`）
- [ ] 前端代码已从仓库拉取到最新（`git pull`）
- [ ] 前端已重新 build 成功（`npm ci && npm run build`）
- [ ] 确认没有未提交的本地改动影响部署

---

## 二、数据库

- [ ] 已执行 Prisma 迁移（`npx prisma migrate deploy` 或等效命令）
- [ ] 迁移后确认新增/修改的表已存在（`SHOW TABLES; DESC xxx;`）
- [ ] 如果涉及数据变更，已提前备份数据库
- [ ] 数据库连接字符串 `DATABASE_URL` 指向正确环境
- [ ] `DATABASE_URL` **显式带连接池参数**：`?connection_limit=20~50&pool_timeout=10`（不配则走 Prisma 默认 CPU×2+1，**它就是这个应用事实上的并发上限**）
- [ ] **数据库与应用同机房/同网**（跨网时每个考试请求有 3~7 次串行 round-trip，实测单请求 45~292ms 里绝大部分是等网络——同机房是容量提升最直接的一条）
- [ ] 考前确认 MySQL `max_connections` ≥ 应用实例数 × 池上限（现正式库 1500，充裕）

**经验教训追加（2026-08-10）：**
> 本次生成试卷报错「The table `paper_generation_jobs` does not exist」，原因是部署时漏执行 `prisma migrate deploy`。以后新增表后必须验证表存在。

**容量基线追加（2026-09-17，业务方追问"能同时多少人在线考"）：**
> 测试环境实测（真实账号走完整考试流程 + 并发压测，测完回滚）：**现状（单实例 + 库跨网）安全 200~300 人同时在线**，500 人开始秒级延迟；**同机房 + 显式连接池后可期 1000~3000 人**。读路径 100 并发 152 req/s 零 5xx（200 并发劣化到 93）；写单请求 186~292ms；同一张卷 50 并发只有 10 req/s（行锁串行化，真实场景每人一卷不冲突）。
> **发放正式考试前建议做一次容量预演**：自己账号 → 找 `PUBLISHED` 未结束且 `used_count < max_count` 的考试 → `start` 重考 → 压 `answers`/`events` → `submit` → 删新卷 + 恢复 `used_count`（核验卷集合/`used_count`/事件数/证书数四项残留）。完整方法与数据见 [[lab-exam-2026-09-17-capacity-concurrency-assessment]]、避坑提醒见 [[避坑指南]] #28。
> 另注意**单实例是可用性单点**（挂了一考场人全掉线）：千级并发前评估多实例（应用无状态，唯建考 60s 幂等 `Map` 是进程内的 P3）。

---

## 三、环境变量

- [ ] `JWT_SECRET` / `JWT_REFRESH_SECRET` 已配置且与本地不同
- [ ] `AUTH_MODE` 配置正确（测试/生产通常为 `cookie`，本地开发为 `bearer`）
- [ ] `CORS_ORIGIN` 已包含当前环境的域名（注意 http 和 https 都要考虑）
- [ ] `REDIS_URL` 已配置且 Redis 服务可连通
- [ ] `COOKIE_SECURE` / `COOKIE_SAME_SITE` 与是否 HTTPS 匹配
- [ ] `CSRF_SECRET` 已配置
- [ ] `PORT` 配置正确

**经验教训追加（2026-08-10）：**
> 本次豆包浏览器登录报 500，原因是 `CORS_ORIGIN` 只配了 `https://lab-exam-test.oceghome.com`，没配 `http://`。后续要同时考虑 http/https、带/不带 `:80`、带/不带末尾斜杠。

---

## 四、Nginx / 反向代理

- [ ] Nginx 配置已更新并检查语法（`nginx -t`）
- [ ] 已配置 HTTP → HTTPS 强制跳转（`return 301 https://$host$request_uri;`）
- [ ] 已 reload Nginx（`nginx -s reload`）
- [ ] 反向代理指向正确的后端端口
- [ ] 静态资源（前端 dist）路径正确

**经验教训追加（2026-08-10）：**
> 本次测试环境 Chrome 用 https 正常、豆包用 http 报 500。原因是 Nginx 未做 HTTP→HTTPS 跳转，后端 CORS 白名单又只认 https。必须在 Nginx 层统一入口。

---

## 五、服务启动

- [ ] 后端服务已重启（`pm2 restart` / `docker restart` / 等）
- [ ] 后端启动日志无 Error
- [ ] Redis 连接成功（日志中无 `Redis connection error`）
- [ ] 健康检查接口可访问（如 `/api/health` 或等效接口）
- [ ] 前端页面能正常打开

---

## 六、核心流程验证（必须实测）

### 6.1 登录
- [ ] 学生账号能正常登录（建议用真实学号测试）
- [ ] 教师账号能正常登录
- [ ] 学院/学校管理员账号能正常登录
- [ ] 换不同浏览器（Chrome、豆包/Edge 等）测试登录正常

### 6.2 考试与试卷
- [ ] 教师能创建考试
- [ ] 教师选择学生后能成功生成试卷（观察进度条）
- [ ] 生成试卷不超时、不报错
- [ ] **生成试卷首次点击不超时、不重复创建任务**
- [ ] 发布后学生能正常进入考试
- [ ] 学生能正常交卷

### 6.3 证书与统计
- [ ] 成绩合格者能生成证书
- [ ] 统计页面数据正确

---

## 七、安全与回滚

- [ ] 数据库已备份
- [ ] 知道如何回滚到上一版本
- [ ] 生产环境 `.env` 中密码不为默认值
- [ ] 限流配置已恢复为生产值（当前代码中登录限流注释为测试环境临时放宽）

---

## 八、问题追加区

> 每次遇到新的部署/上线问题，在下面追加一条，并写明触发条件、根因、避免方法。

### 2026-08-10 豆包浏览器登录报 500
- **触发条件**：豆包浏览器访问 `http://lab-exam-test.oceghome.com` 登录
- **根因**：后端 `CORS_ORIGIN` 未配置 http 域名，且 CORS 拒绝时原代码返回 500
- **避免方法**：
  1. Nginx 配置 HTTP→HTTPS 跳转
  2. CORS 白名单同时包含 http/https 域名
  3. CORS 拒绝时返回正确状态码（已修复代码）

### 2026-08-10 生成试卷报「paper_generation_jobs 表不存在」
- **触发条件**：部署新增异步生成试卷功能后，教师点击生成试卷
- **根因**：部署时未执行 Prisma 数据库迁移
- **避免方法**：每次后端代码涉及 schema 变更，必须执行 `npx prisma migrate deploy`
- **⚠️ 2026-09-18 更正（上面「避免方法」对这张表无效）**：`paper_generation_jobs` **从未出现在任何迁移文件里**（`git log --all -p -- server/prisma/migrations` 命中 0，迁移目录也从未被删过），它只可能来自 `prisma db push` 或手工 DDL ⇒ 当时跑 `migrate deploy` **建不出这张表**，"根因=漏跑迁移"这个记法误导人。正解：**schema 变更必须先进迁移**（`prisma migrate dev` 生成 `server/prisma/migrations/`），能进迁移的才谈得上"部署时执行 migrate deploy"；临时 `db push` 出来的表要补一条迁移，否则正式库永远缺、且账本与实际 schema 长期不一致（2026-09-18 探针实测正式库**已有**该表，即正式库确实存在账本之外的 DDL）。同类先例：2026-09-07 dev 库 `migrate deploy` 因 `created_at` 重复列漂移当场失败 → 手工 ALTER + `migrate resolve`。详见 [[lab-exam-2026-09-18-prod-500-audience-migration-missing]] §八

### 2026-08-10 生成试卷超时「timeout of 10000ms exceeded」
- **触发条件**：教师选择较多学生生成试卷
- **根因**：原同步接口在循环生成所有学生试卷后才响应，容易超时
- **避免方法**：已改为异步任务 + 前端轮询进度，部署后需验证进度条正常

### 2026-08-10 异步生成试卷首次点击仍超时
- **触发条件**：教师点击生成试卷，第一次请求报 `timeout of 10000ms exceeded`，第二次成功
- **根因**：
  1. 前端 `generatePapers` 接口仍使用默认 10 秒超时，异步提交任务在弱网/学生数量多/服务器响应慢时仍可能超时
  2. 缺少幂等性：第一次请求超时后，后端可能已创建任务，再次点击会重复创建
- **避免方法**：
  1. 前端 `generatePapers` 超时调整为 60 秒
  2. 后端同一考试已有 `pending` / `running` 任务时直接返回已有 `jobId`
  3. 部署后实测首次点击不超时、不重复创建任务

---

## 使用方式

1. 每次部署前，运维/负责人必须逐项检查并打勾。
2. 未打勾项不得继续下一步。
3. 如果遇到本清单未覆盖的问题，处理完毕后必须追加到「问题追加区」。
4. 本清单由 Claude 在每次部署会话开始时主动调取。
