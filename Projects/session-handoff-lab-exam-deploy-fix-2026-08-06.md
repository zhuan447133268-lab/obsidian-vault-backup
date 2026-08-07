---
description: 2026-08-06 实验室准入考试系统部署问题修复会话交接：已提交多项部署修复与交付文档，等待运维部署测试环境
date: '2026-08-06'
project: 实验室准入考试系统
type: session-handoff
---
## 当前状态

- **项目**：实验室准入考试系统（lab-exam）
- **仓库**：https://git.oceghome.com/aiproject/lab-exam
- **本地路径**：`D:\2026准入题库\`
- **当前分支**：`main`
- **最新提交**：`348f0f3 docs(deploy): 补充测试环境无域名时的临时部署方案`

## 本轮会话完成的工作

### 已修复/已提交的部署问题

1. **Prisma TS2339 编译错误**
   - 修复：`server/Dockerfile` 中 `npm run build` 前增加 `RUN npx prisma generate`
   - Commit：`e685ca0`

2. **Redis URL / 密码配置误解**
   - 修复：`server/.env.example` 补充带密码 URL 示例，`README.md` 增加说明
   - Commit：`4a83704`

3. **bcrypt 跨平台原生模块缺失**
   - 修复：`bcrypt` 替换为 `bcryptjs`
   - Commit：`877387d`

4. **Puppeteer 安装时下载浏览器失败**
   - 修复：`server/package.json` 配置 `puppeteer.skipDownload`，`server/Dockerfile` 更新环境变量
   - Commit：`e685ca0`

5. **部署健壮性增强**
   - 新增启动时环境变量校验（`server/src/config/validate-config.ts`）
   - 生产环境 Redis 连接失败时服务拒绝启动（`server/src/modules/redis/redis.service.ts`）
   - `/health` 接口同时检查 database 和 redis
   - Commit：`a439c0e`

6. **部署交付物完善**
   - 新增 `deploy/` 目录：`.env.example`、`nginx/lab-exam.conf`、`README.md`、`RELEASE_CHECKLIST.md`
   - Commit：`549a33b`、`348f0f3`

### 文档更新

- `README.md`：项目结构增加 `deploy/` 说明
- `DEPLOY.md`：完整运维部署手册
- `deploy/README.md`：面向运维的交付说明
- `web/.env.production`：增加配置注释

## 当前流程（已确认）

1. 开发完成 → 推代码 + README/部署说明到 Git
2. 运维部署测试环境 → 返回测试链接（含域名）
3. 基于测试链接验证 → 修 bug
4. 运维部署正式环境 → 返回正式链接

**域名由运维部署时配置，开发侧只需要提供占位符配置。**

## 占位符配置说明

以下文件中的域名为占位符，需运维按实际测试/正式域名修改：

| 文件 | 占位符 | 说明 |
|---|---|---|
| `deploy/.env.example` | `CORS_ORIGIN="https://your-domain.com"` | 运维复制为 `server/.env` 后修改 |
| `web/.env.production` | `VITE_API_BASE_URL=https://lab-exam.school.edu.cn/api` | 前端构建前修改 |
| `deploy/nginx/lab-exam.conf` | `server_name _;` | 可按需修改 |

## 已知潜在风险（待验证）

1. MySQL 网络/权限问题
2. CORS_ORIGIN 与实际前端域名不匹配
3. Chromium 未安装导致证书导出失败（核心考试流程不影响）
4. Nginx root 路径未改对
5. 前端 `VITE_API_BASE_URL` 未按实际域名修改

## 待办事项

1. 等待运维部署测试环境并返回测试链接
2. 基于测试链接进行功能验证
3. 修复验证中发现的 bug
4. 最终版部署正式环境
5. **生产环境上线前**：配置 Jenkins/GitLab CI 自动化部署
6. **生产环境上线前 1 天**：配置数据库自动备份机制

## 不需要现在做的事

- Jenkins 自动化部署（测试环境不需要）
- 数据库定时自动备份（测试环境不需要）

## 关键结论

- 代码仓库从未提交过 `node_modules/`
- 之前的部署问题根因是部署流程不规范（复制 Windows node_modules、未执行 prisma generate、环境变量名写错）
- 当前代码和文档已覆盖已知高频部署问题
- 运维按 `deploy/README.md` + `DEPLOY.md` 操作，部署成功概率高

## 相关记忆

- [[project-lab-exam-master-index]]
- [[bug-lessons-and-self-check]]
- [[todo_database_backup_before_launch]]
- [[session-handoff-lab-exam-2026-08-06]]
