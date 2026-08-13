---
name: lab-exam-admin-layout-scroll-fix-2026-08-13
description: 管理后台侧边栏随页面内容一起滚动，已修复并push
metadata: 
  node_type: memory
  type: project
  originSessionId: 79485d53-99a8-46cb-9d67-59c98547f482
  modified: 2026-08-13T05:51:33.018Z
---

**时间**：2026-08-13
**分支**：`main`
**修改文件**：
- `web/src/layouts/AdminLayout.vue`

**Bug 根因**：
管理后台 `AdminLayout.vue` 使用 `min-height: 100vh`，当页面内容超过视口高度时，布局整体被撑高，`el-main` 的 `overflow: auto` 因无溢出而不生效，滚动发生在 `body` 上，导致侧边栏/顶栏作为普通文档流元素跟着一起滚出视口。

**修复方案**：
`AdminLayout.vue` 第 115 行：`min-height: 100vh` → `height: 100vh`。
- 布局高度锁定为视口高
- `el-main` 自动获得固定高度，`overflow: auto` 生效，滚动发生在内容区
- 侧边栏高度=视口高，固定不动；菜单超高时由内部 `el-scrollbar` 滚动

**验证**：
- `npm run build`（web）通过

**影响范围**：
- 所有管理端页面共用 `AdminLayout`，专业管理/学院信息/班级管理/师生管理/题库管理/全校统计/教师分班管理等长页面同步修复
- 学生端（MobileLayout）、登录页、改密页、错误页等整页滚动设计不受影响

**Why：** 固定侧边栏布局必须给内容区一个固定高度才能触发内部滚动，`min-height` 在内容撑高时会让溢出转移到 body。

**How to apply：** 后续遇到"固定侧边栏但滚动时跟着跑"，优先检查外层容器是 `height: 100vh` 还是 `min-height: 100vh`。
