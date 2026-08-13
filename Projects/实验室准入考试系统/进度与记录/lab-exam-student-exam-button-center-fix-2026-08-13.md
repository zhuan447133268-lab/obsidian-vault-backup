---
name: lab-exam-student-exam-button-center-fix-2026-08-13
description: 手机端考试页面底部功能按钮偏移，已修复并push
metadata: 
  node_type: memory
  type: project
  originSessionId: 79485d53-99a8-46cb-9d67-59c98547f482
  modified: 2026-08-13T06:16:19.967Z
---

**时间**：2026-08-13
**分支**：`main`
**修改文件**：
- `web/src/views/student/exam-paper.vue`

**Bug 根因**：
学生考试页面底部操作栏 `.bottom-actions` 使用 `justify-content: space-between`，按钮两端对齐，在手机端视觉上不在屏幕正中央。

**修复方案**：
- `justify-content: space-between` → `justify-content: center`
- `gap: 8px` → `gap: 12px`
- `.van-button` 从 `flex: 1`（拉伸均分）改为 `flex: 0 0 auto; min-width: 72px`（按内容宽度居中排列）

**验证**：
- `npm run build`（web）通过

**影响范围**：
- 仅影响学生手机端考试作答页面底部按钮布局
- 学生端其他页面、教师端、管理端不受影响

**Why：** 测试反馈底部功能按钮应整体水平居中，space-between 会让按钮贴边，视觉中心偏移。

**How to apply：** 手机端底部固定操作栏若要求按钮居中，优先使用 `justify-content: center` + 按钮不拉伸，避免两端对齐造成的偏移感。
