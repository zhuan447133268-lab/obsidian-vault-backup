---
date: '2026-08-10'
tags:
  - lab-exam
  - todo
  - 部署
  - CORS
  - 异步生成试卷
status: pending
type: todo
---

## 更新记录

### 2026-08-10 代码已 push
- 提交 commit：`d0c8b02`
- 推送分支：`main → origin/main`
- 包含改动：
  - `fix(cors)`: CORS 拒绝时返回 403 而非 500
  - `feat(exam)`: 生成试卷改为异步任务 + 轮询进度

## 待办事项

### 1. 测试环境 Nginx 强制 HTTPS 跳转
- **状态**：待运维操作
- **操作**：在测试环境 Nginx 配置中增加 HTTP→HTTPS 的 301 跳转
- **配置示例**：
  ```nginx
  server {
      listen 80;
      server_name lab-exam-test.oceghome.com;
      return 301 https://$host$request_uri;
  }
  ```
- **reload 命令**：
  ```bash
  nginx -t
  nginx -s reload
  ```
- **原因**：豆包浏览器使用 http:// 访问时报 500，Chrome 使用 https:// 访问正常。原因是后端 CORS 白名单只配置了 HTTPS 域名。

### 2. 生产环境同步加入 HTTPS 强制跳转
- **状态**：待上线前运维操作
- **操作**：生产环境 Nginx 同样配置 HTTP→HTTPS 跳转
- **后端 CORS_ORIGIN**：生产环境只保留 HTTPS 域名

### 3. 异步生成试卷改造
- **状态**：代码已 push，待 build 部署验证
- **包含改动**：
  - 后端新增 `paper_generation_jobs` 任务表
  - `POST /exams/:id/papers/batch-generate` 改为异步提交，返回 `jobId`
  - 新增 `GET /exams/:id/papers/generate-progress?jobId=xxx` 轮询接口
  - 前端点击生成后显示进度条 `生成中 X/Y`
- **待办**：前端 build 后部署到测试环境验证

## 关联会话
[[session-handoff-lab-exam-teacher-issues-2026-08-10]]
