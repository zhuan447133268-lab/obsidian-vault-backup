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

---

## 2026-08-11 金智库→lab_exam 数据同步决策（待业务方确认）

> 触发条件：用户说「从金智库同步学生/教师」时读取本段。

### 已确认的同步范围
1. **只同步哈尔滨剑桥学院（010201）学生**，烟台校区（010204）不导入。
2. **只同步"在读"学生**（xsdqzt='在读'），毕业/退学跳过。
3. **学号可直接匹配**：金智库 XH = lab_exam student_no，按学号判断是否已存在，只新增、已存在跳过。
4. **电子电气智能工程学院已存在** lab_exam 中（DQ），正常同步。

### ⚠️ 待业务方确认（阻塞项）
- **金智库「智能与电气电子工程学院」(01020126，约2723在读生) 是否导入 lab_exam？**
  - lab_exam 无此学院、无题库。
  - 用户判断：**本学院暂时不导入**，待找业务方确认归属（映射到 DQ 还是 ZN，或新建学院）。
  - **确认前不要导入该学院学生。**

### lab_exam 学院 ↔ 金智库机构编码 对照（已核实）
| lab_exam 学院(编码) | 金智库机构编码 | 金智库名称 |
|---|---|---|
| 电气电子智能工程学院(DQ) | 01020156 | 电气电子智能工程学院 |
| 工商管理学院(GS) | 01020127 | 工商管理学院 |
| 教育学院(JY) | 01020124 | 教育学院 |
| 汽车与机电工程学院(QC) | 01020125 | 汽车与机电工程学院 |
| 艺术学院(YS) | 01020128 | 艺术学院 |
| 智能科学与工程学院(ZN) | 01020157 | 智能科学与工程学院 |
| 通识教育学院(TS) | 01020153 | 通识教育学院 |
| 信息化教学中心(XX) | 01020121 | 信息化教学中心 |

### 参考数据源
- 金智库连接：`219.147.169.72:63306`，user=`temp_read`，库=`jinzhi_midd`
- 学生表 `t_xsjbxx`（XH学号/XM姓名/SZYX学院/calss_code班级/xsdqzt状态）
- 教职工表 `t_jzgjbxx` + `t_jzggbzwxx`（任职单位关联学院）
- 组织机构表 `t_zzjgxx`（机构编码/名称）
- 题库文件确认的考试学院：DQ/GS/JY/QC/YS/ZN/TS（见 `D:\2026准入题库\题库题目`）
