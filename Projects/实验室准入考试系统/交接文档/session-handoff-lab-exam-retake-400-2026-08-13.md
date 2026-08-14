# 2026-08-13 学生端重考 400 修复 —— 会话交接

**状态**：代码已修复并 push 到 `main`，等测试环境部署验证。  
**commit**：`082d471`

## 已完成功能

- 定位并修复学生考试未通过后点击“重新考试”报 400 的问题。
- 后端统一 `canRetake` 权限判定（发布状态 + 时间窗口 + 剩余次数）。
- 前端结果页按后端返回的 `canRetake` 显示/隐藏重考按钮。
- web/server 构建通过，student-exam 单元测试 7/7 通过。

## 修改文件

- `server/src/modules/student-exam/student-exam.service.ts`
- `web/src/api/student-exam.ts`
- `web/src/views/student/exam-result.vue`
- 同时提交已有的测试文件：
  - `server/src/modules/student-exam/student-exam.service.spec.ts`
  - `server/src/modules/auth/services/data-scope.service.spec.ts`

## 下一会话待跟进

1. 测试环境部署 `main` 后，验证重考流程：
   - 窗口内、有剩余次数：未通过后可正常重考。
   - 考试关闭或超窗：结果页不显示“重新考试”按钮。
2. 若窗口内仍报 400，需提供后端日志/响应体继续排查。

## 相关记录

- [[lab-exam-student-retake-400-fix-2026-08-13]]
- [[lab-exam-deploy-checklist]]
- [[session-handoff-lab-exam-2026-08-13-统计状态筛选部署待验证]]
