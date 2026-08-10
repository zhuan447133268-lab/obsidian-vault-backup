---
date: '2026-07-13'
tags:
  - project/lab-exam
  - design-doc
  - api-design
title: 学生考试作答端 API 设计 v1.0
type: design-doc
---
# 学生考试作答端 API 设计

> 阶段：第四阶段  
> 版本：v1.0  
> 日期：2026-07-13  
> 目标：支撑学生移动端完成「查看考试 → 开始考试 → 答题 → 交卷」最小闭环

---

## 1. 模块定位

- 新建 NestJS 模块：`server/src/modules/student-exam/`
- 路由前缀：`/student-exams`
- 面向角色：`STUDENT`
- 核心数据：基于现有 `Exam` / `Paper` / `PaperQuestion` / `ExamEvent` / `StudentAttempt` 模型，不新增实体表

---

## 2. 状态机

### 2.1 考试状态（Exam.status）
```
DRAFT → PUBLISHED → CLOSED
```
学生只能看到 `PUBLISHED` 且在自己时间窗口内的考试。

### 2.2 试卷状态（Paper.status）
```
DRAFT ──开始考试──► IN_PROGRESS ──手动交卷──► SUBMITTED
                          │
                          └─超时/断网未恢复──► TIMEOUT
                          │
                          └─系统强制提交──► AUTO_SUBMITTED
```

- `DRAFT`：已组卷，学生未开始
- `IN_PROGRESS`：学生已开始，正在答题
- `SUBMITTED`：学生主动交卷
- `TIMEOUT`：考试结束时间到达，或断网超过 10 分钟未恢复
- `AUTO_SUBMITTED`：系统强制提交（如学生关闭浏览器、切出应用等触发安全交卷）

本阶段实现 `DRAFT → IN_PROGRESS → SUBMITTED/TIMEOUT`。

---

## 3. 接口列表

| 方法 | 路径 | 说明 | 优先级 |
|---|---|---|---|
| GET | `/student-exams` | 查询学生的考试列表 | P0 |
| POST | `/student-exams/:id/start` | 开始考试 | P0 |
| GET | `/student-exams/:id/paper` | 获取试卷题目（不含答案） | P0 |
| POST | `/student-exams/:id/answers` | 保存/更新答案 | P0 |
| POST | `/student-exams/:id/submit` | 交卷 | P0 |
| POST | `/student-exams/:id/events` | 考试事件上报 | P1 |
| GET | `/student-exams/:id/result` | 获取考试结果 | P1 |

---

## 4. 接口详情

### 4.1 查询考试列表

```http
GET /student-exams?status=PENDING|IN_PROGRESS|FINISHED
```

**状态说明**
- `PENDING`：已发布、时间窗口内、paper 状态为 `DRAFT` 的考试
- `IN_PROGRESS`：paper 状态为 `IN_PROGRESS` 的考试
- `FINISHED`：paper 状态为 `SUBMITTED | TIMEOUT | AUTO_SUBMITTED` 的考试

**响应**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": "exam-id",
      "title": "实验室安全准入考试",
      "collegeName": "教育学院",
      "className": "学前2301",
      "startTime": "2026-07-13T09:00:00",
      "endTime": "2026-07-13T18:00:00",
      "durationMinutes": 30,
      "paperStatus": "DRAFT",
      "score": null,
      "remainingSeconds": null
    }
  ]
}
```

### 4.2 开始考试

```http
POST /student-exams/:id/start
```

**业务规则**
1. 考试必须 `PUBLISHED`
2. 当前时间必须在 `[startTime, endTime]` 内
3. 学生必须属于该考试 `collegeId`（及 `classId`，若指定）
4. 必须已存在该学生的 `Paper`（教师已组卷）
5. `Paper.status` 必须为 `DRAFT`
6. 更新 `Paper.status = IN_PROGRESS`、`startTime = now()`、`lastSyncTime = now()`

**响应**
```json
{
  "code": 0,
  "data": {
    "paperId": "paper-id",
    "examId": "exam-id",
    "durationMinutes": 30,
    "endTime": "2026-07-13T18:00:00"
  }
}
```

### 4.3 获取试卷题目

```http
GET /student-exams/:id/paper
```

**业务规则**
1. 只能查询自己的 paper
2. `Paper.status` 为 `IN_PROGRESS` 或 `DRAFT`（允许开始考试后未刷新时获取）
3. 不返回答案字段

**响应**
```json
{
  "code": 0,
  "data": {
    "paperId": "paper-id",
    "title": "实验室安全准入考试",
    "durationMinutes": 30,
    "questions": [
      {
        "id": "paper-question-id",
        "seqNo": 1,
        "type": "SINGLE",
        "content": "题目内容",
        "options": [
          { "key": "A", "content": "选项A" },
          { "key": "B", "content": "选项B" }
        ],
        "score": 4
      }
    ]
  }
}
```

### 4.4 保存答案

```http
POST /student-exams/:id/answers
Content-Type: application/json

{
  "questionId": "paper-question-id",
  "answer": ["A"]
}
```

**业务规则**
1. `Paper.status` 必须为 `IN_PROGRESS`
2. 校验 `questionId` 属于当前 paper
3. `answer` 为字符串数组，`SINGLE/JUDGE` 传 `["A"]`，`MULTIPLE` 传 `["A", "B"]`
4. 更新 `Paper.answers` JSON、`lastSyncTime = now()`
5. 写入 `ExamEvent`：ANSWER 事件（P1 可异步）

**响应**
```json
{
  "code": 0,
  "data": {
    "savedAt": "2026-07-13T09:05:00"
  }
}
```

### 4.5 交卷

```http
POST /student-exams/:id/submit
```

**业务规则**
1. `Paper.status` 必须为 `IN_PROGRESS`
2. 自动批改客观题（单选/判断/多选）
3. 计算总分，更新 `Paper.score`、`status = SUBMITTED`、`submitTime = now()`
4. 生成/更新 `Certificate`（P1，若通过）

**响应**
```json
{
  "code": 0,
  "data": {
    "paperId": "paper-id",
    "status": "SUBMITTED",
    "score": 92,
    "passed": true
  }
}
```

### 4.6 事件上报

```http
POST /student-exams/:id/events
Content-Type: application/json

{
  "eventType": "HEARTBEAT|BLUR|FOCUS|LEAVE|ANSWER|SUBMIT",
  "clientTime": "2026-07-13T09:10:00",
  "payload": {}
}
```

**业务规则**
1. 记录到 `ExamEvent`
2. `HEARTBEAT` 同时更新 `Paper.lastSyncTime`
3. 若 `lastSyncTime` 超过 10 分钟未更新，由定时任务置为 `TIMEOUT`

### 4.7 获取考试结果

```http
GET /student-exams/:id/result
```

**响应**
```json
{
  "code": 0,
  "data": {
    "paperId": "paper-id",
    "status": "SUBMITTED",
    "score": 92,
    "passed": true,
    "durationSeconds": 1260,
    "submitTime": "2026-07-13T09:21:00"
  }
}
```

---

## 5. 权限与越权控制

- 使用现有 `JwtAuthGuard` + `RolesGuard`
- 仅允许 `STUDENT` 角色访问
- 每个接口必须校验 `paper.studentId === currentUser.userId`
- 考试时间窗口硬校验：当前时间必须在 `Exam.startTime` 与 `endTime` 之间（start/end 取考试配置，不是 paper.startTime）

---

## 6. 错误码

| code | 场景 |
|---|---|
| 1401 | 考试未发布或不在时间窗口内 |
| 1402 | 学生不在该考试范围内 |
| 1403 | 试卷不存在或未生成 |
| 1404 | 考试状态不允许当前操作 |
| 1405 | 题目不属于当前试卷 |
| 1406 | 考试已结束或已超时 |

---

## 7. 验证清单

- [ ] `STUDENT` 登录后能列出待考考试
- [ ] 非考试时间窗口内无法 start
- [ ] 教师/管理员访问 `/student-exams` 返回 403
- [ ] start 后 paper 状态变为 `IN_PROGRESS`
- [ ] paper 接口不返回 `answerSnapshot`
- [ ] 保存答案后 `lastSyncTime` 更新
- [ ] 提交后客观题自动批改，score 正确
- [ ] 已提交试卷无法再保存答案
- [ ] 已超时考试无法继续答题

---

## 8. 关联文件

- `server/src/modules/student-exam/student-exam.module.ts`
- `server/src/modules/student-exam/student-exam.controller.ts`
- `server/src/modules/student-exam/student-exam.service.ts`
- `server/src/modules/student-exam/dto/*.dto.ts`
- `server/src/app.module.ts`（注册模块）

