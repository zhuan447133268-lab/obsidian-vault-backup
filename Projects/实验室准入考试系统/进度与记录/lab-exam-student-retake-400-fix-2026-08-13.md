# 学生端重考 400 修复

**时间**：2026-08-13
**分支**：`main`
**修改文件**：
- `server/src/modules/student-exam/student-exam.service.ts`
- `web/src/api/student-exam.ts`
- `web/src/views/student/exam-result.vue`

## 现象

测试反馈：手机端学生考试未通过后，点击“重新考试”，控制台报：

```
POST /api/student-exams/{id}/start 400 (Bad Request)
```

## 根因

考试结果页重考按钮显隐条件仅为：

```vue
v-if="!result.passed && result.remainingAttempts > 0"
```

没有校验考试是否仍处于 `PUBLISHED` 状态以及当前时间是否在 `startTime~endTime` 窗口内。当考试已过期、被自动关闭（`CLOSED`）或不在窗口内时，`start` 接口的 `assertExamOpen` 会抛 400，但前端仍然展示按钮，用户点击即触发报错。

## 修复

1. **后端 `list` 接口**：`canRetake` 在原有“终态 + 次数未用完”基础上，追加 `exam.status === PUBLISHED && inWindow`。
2. **后端 `getResult` 接口**：新增 `canRetake` 字段，统一由后端根据发布状态、时间窗口、剩余次数综合判定。
3. **前端 `exam-result.vue`**：重考按钮显隐改为 `result.canRetake`。

## 验证

- `npm run build`（web）通过
- `npm run build`（server）通过
- `npx jest --testPathPatterns=student-exam.service.spec.ts`：7/7 通过
- 已 push 到 `main`

## 影响范围

- 仅影响学生端结果页/列表页的重考按钮显隐
- 考试仍在发布窗口内且有剩余次数时，重考流程不受影响
- 考试关闭或超窗后，不再展示重考按钮，避免触发 400
