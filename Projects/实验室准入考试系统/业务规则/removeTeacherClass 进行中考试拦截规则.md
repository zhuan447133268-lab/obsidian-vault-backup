---
date: 2026-08-14
project: 实验室准入考试系统
type: 业务规则
source: memory/lab-exam-teacher-class-remove-active-exam-rule
---

# removeTeacherClass 进行中考试拦截规则

> 对应 memory：[[lab-exam-teacher-class-remove-active-exam-rule]]
> 相关修复：[[session-handoff-lab-exam-teacher-class-remove-active-exam-block-continued-2026-08-14]]

---

## 规则

`removeTeacherClass`（学院管理员移除教师班级关联）只拦截**进行中**的考试。

### 拦截条件

```ts
where: {
  classId: record.classId,
  status: ExamStatus.PUBLISHED,
  startTime: { lte: now },
  endTime: { gte: now },
}
```

### 允许删除的场景

- 考试状态为 `DRAFT`
- 考试状态为 `PUBLISHED` 但 `startTime > now`（已发布，尚未开始）
- 考试状态为 `CLOSED` 或 `endTime < now`（已结束）

### 原因

用户确认：已发布但未开始的考试，教师应被允许删除后重新创建考试。只有在考试已经开始后，移除教师班级关联才会破坏当前考试的权限链路，因此才需要拦截。

---

## 相关代码

- `server/src/modules/users/users.service.ts` 的 `removeTeacherClass`
- `server/src/modules/users/users.service.spec.ts`

---

## 关联记录

- [[lab-exam-teacher-class-remove-active-exam-block-2026-08-14]]
- [[开发避坑记录]]
- [[实验室准入考试系统——项目索引]]
