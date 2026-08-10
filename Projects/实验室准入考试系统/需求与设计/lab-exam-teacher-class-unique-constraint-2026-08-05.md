---
name: lab-exam-teacher-class-unique-constraint-2026-08-05
description: 2026-08-05 实验室准入考试系统：教师分班增加班级唯一约束，防止一个班级分配给多位教师
metadata:
  type: project
  project: 实验室准入考试系统
  date: '2026-08-05'
---
## 问题
教师分班时，一个班级可能被误分配给两位不同教师。

## 根因
`TeacherClass` 表只有 `(user_id, class_id)` 复合唯一约束，只能阻止“同一位教师被重复分配到同一班级”，无法阻止“不同教师分配到同一班级”。服务层 `upsert` 也只按 `(userId, classId)` 查找，不检查该班级是否已被其他教师占用。

## 修复方案（已实施）

### 1. 数据库层加唯一约束
文件：`server/prisma/schema.prisma` 第 142 行
```prisma
model TeacherClass {
  // ...
  @@unique([userId, classId])
  @@unique([classId])        // 新增
}
```
已执行 `npx prisma db push --accept-data-loss`，MySQL 索引 `teacher_classes_class_id_key` 已创建。

### 2. 服务层前置占用检查
文件：`server/src/modules/users/users.service.ts` 第 688 行 `upsert` 之前
```typescript
const existing = await this.prisma.teacherClass.findUnique({
  where: { classId: cls.id },
});
if (existing && existing.userId !== user.id) {
  throw new BadRequestException({
    code: 1302,
    message: '该班级已分配给其他教师',
  });
}
```

### 3. 前端过滤已分配班级
文件：`web/src/views/college-admin/teachers.vue`
- 导入 `computed`
- 新增 `filteredClasses`：过滤掉 `list` 中被其他教师占用的班级
- 班级下拉框改用 `filteredClasses`

## 验证结果（2026-08-05）
1. `npx tsc --noEmit`（后端）通过
2. `npx vue-tsc --noEmit`（前端）通过
3. MySQL 唯一索引已创建
4. API 实测：
   - 教师1 分配班级 23电气一班 → success
   - 教师2 分配同一班级 → code 1302 "该班级已分配给其他教师"
   - 删除测试数据 → success

## 已知影响
- 后端服务曾因 Prisma Client 重生成被短暂终止，已重新启动（PID 25032）
- 前端 Vite 热更新后无需重启，但需浏览器刷新 `Ctrl+F5`
- 本次改动仍未 commit/push

## 相关记忆
- [[project-lab-exam-master-index]] — 项目全条目索引
- [[session-handoff-lab-exam-local-verify-2026-08-05]] — 本地验证交接
