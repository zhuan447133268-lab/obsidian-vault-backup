---
name: lab-exam-teacher-share-card-fix-2026-08-13
description: 教师端考试分享卡片优化：链接全宽可换行、复制内容含考试信息
metadata: 
  node_type: memory
  type: project
  originSessionId: 79485d53-99a8-46cb-9d67-59c98547f482
  modified: 2026-08-13T02:22:28.343Z
---

**时间**：2026-08-13
**分支**：`main`
**修改文件**：
- `web/src/views/teacher/index.vue`

**问题**：
教师创建完考试后点击分享按钮，弹出的分享卡片里链接放在只读输入框中，420px 弹窗内 URL 太长显示不全；复制按钮只复制纯链接，粘贴出去没有考试名称/范围/时间。

**修复方案（方案A）**：
1. 链接显示从 `el-input` 改为全宽可换行 `<div>`（`word-break: break-all`），截图能看清完整链接
2. 复制按钮文案改为「复制链接与考试信息」
3. 复制内容改为多行文本：
   ```
   【考试名称】
   范围：XX学院 / XX班级
   时间：2026-08-13 14:00 ~ 15:00
   链接：https://xxx/student/exam-share/{id}
   ```

**验证**：
- `npm run build`（web）通过

**上下游影响**：
- 只改 `teacher/index.vue`，零后端改动
- 学生打开链接的 `exam-share.vue` 页面无影响
- 二维码生成与扫码链路无影响

**Why：** 截图传播和链接复制两条路径各缺一半信息，需要同时补齐。

**How to apply：** 后续若再遇到分享卡片类需求，默认同时考虑「截图可见完整信息」和「复制粘贴带出完整信息」两条传播路径。
