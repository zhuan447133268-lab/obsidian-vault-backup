---
name: lab-exam-2026-09-01-teacher-mobile-adaptive
description: 张凯悦手机登录教师端「显示不全」根因定案——教师端 AdminLayout 无移动端自适应（260px 侧栏固定+横向溢出），学生端 MobileLayout 有适配；附手机视口实测数据与截图位置
type: project
date: 2026-09-01
---

# 教师端手机「显示不全」根因定案（2026-09-01）

> 复核目标：张凯悦在**手机端**登录教师账号页面显示不全，排查教师端是否做了移动端自适应（学生端应该是有的）。

## 结论

1. **教师端没有任何移动端自适应**：全部 `/teacher`、`/school-admin`、`/college-admin` 页面挂在 `AdminLayout.vue`（Element Plus 桌面布局：固定 260px 侧栏 + 顶栏 + el-table/art-card 内容区），全项目**无一处**针对教师端做折叠侧栏或窄屏适配。
2. **学生端有自适应**：`/student` 系页面挂 `MobileLayout.vue`（van-tabbar 手机布局），且 `global.less:118-137` 有移动端限宽规则（`.mobile-layout` 等选择器 `max-width: 480px` 居中，手机上全宽）——这段规则的选择器**只列了学生端页面**，教师端页面不在其中。
3. 因此张凯悦在手机上看到的是：**260px 侧栏占掉 2/3 屏宽，剩余内容被挤压到 70px 甚至 38px，且整体横向溢出**，表现为"显示不全"。

## 手机视口（390×844）实测数据

| 页面 | 视口宽 | 文档 scrollWidth | 横向溢出 | 侧栏宽 | 卡片可见宽/真实宽 |
|---|---|---|---|---|---|
| 教师端 /teacher/statistics | 390 | 451 | ✅ 溢出 | 260 | 70 / 320 |
| 教师端 /teacher（首页） | 390 | 451 | ✅ 溢出 | 260 | 70 / 104 |
| 教师端 /teacher/classes | 390 | 451 | ✅ 溢出 | 260 | 38 / 147（5 张卡均如此） |
| 学生端 /student（对照） | 390 | 382 | ❌ 无溢出 | — | 全宽正常 |

截图：`gui-test-screenshots/2026-09-01-teacher-mobile/`（01-03 教师端三页手机视口、04 学生端首页对照）。

## 唯一例外

`teacher/exam-detail.vue` 有一处 `@media (max-width: 768px)`（info-grid 3 列→2 列），杯水车薪，且该页同样被 260px 侧栏挤压。

## 修复方向（建议，未实施）

- **方案 A（推荐）**：AdminLayout 增加 `@media (max-width: 768px)` 折叠侧栏（隐藏 aside / 抽屉式）——较小改动，覆盖全部教师端页面。
- **方案 B**：教师端拆出 MobileLayout 移动布局（工作量最大）。
- 配套：`global.less` 的 480px 限宽规则补充教师端根容器类名（若想手机全宽而非被居中限宽样式影响）。
- 注意：张凯悦是在手机浏览器访问 `lab-exam-test.oceghome.com/teacher`（未做移动端 UA 分流，无 m. 站点）。

## 修复实施 + 测试环境验证通过（2026-09-01 下午）

### 实施方案（A 方案落地，commit e8a8967 已 push origin main）

`web/src/layouts/AdminLayout.vue`：
- 模板：侧栏外包 `.sidebar`（原 el-aside），新增 `mobile-mask` 遮罩层（`v-if="isMobile && mobileOpen"`，点击关闭）；header 内新增汉堡按钮 `.menu-toggle`（`v-if="isMobile"`，:aria-label 切换文案）；el-menu `@select="onMenuSelect"`（移动端选中菜单项自动收起抽屉）。
- script：`isMobile`（matchMedia '(max-width: 768px)' 监听，onMounted 注册 / onBeforeUnmount 移除）、`mobileOpen`；`onMqChange` 切回桌面自动收起；`goHome` 路由跳转后自动关抽屉。
- 样式：768px 断点内 `.admin-layout{display:block}`、`.sidebar` 转 fixed 抽屉（`z-index:1100`，`transform:translateX(-100%)`，`.sidebar-open` 展开+阴影）、`.mobile-mask`（`z-index:1000` 半透明遮罩）、header 52px、content padding 12px、用户角色隐藏；`≥769px` 汉堡按钮隐藏。

### 测试环境验证（手机视口 390×844，admin/LabTest2026! 登录，Jenkins 构建部署后）

| 检查项 | /teacher 首页 | /teacher/classes | /teacher/statistics |
|---|---|---|---|
| 文档 scrollWidth vs 视口 | 382 ≤ 390 ✅ 无溢出（修复前 451 溢出） | 390 = 390 ✅ | 382 ≤ 390 ✅ |
| 侧栏默认状态 | 收起 left=-260 ✅ | 收起 left=-260 ✅ | 收起 left=-260 ✅ |
| 汉堡按钮 | 存在 ✅ | 存在 ✅ | 存在 ✅ |
| 页面标题正常 | ✅ | 我的班级 ✅ | 班级统计 ✅ |

抽屉交互：点汉堡→展开（13 个菜单项 + 遮罩出现）✅；点遮罩右侧（x=330 坐标）→ 收起并移除遮罩 ✅（注：playwright 元素中心点击会被 z-index 1100 侧栏覆盖，须点遮罩右侧露出区或直接菜单点选验证）。

截图：`gui-test-screenshots/2026-09-01-teacher-mobile/`（05 首页抽屉展开、06 班级页、07 统计页；01-03 为修复前对照，04 学生端对照）。

**结论：测试环境验证通过，可通知运维 build 正式环境。** 正式环境生效后建议用手机再走一遍张凯悦账号路径确认。

## 相关链接

- [[lab-exam-2026-08-31-teacher-page-check]]（昨天桌面端结论：教师端桌面布局完整）
- [[lab-exam-2026-08-31-prod-env-verify]]
- 记忆：[[labexam-teacher-mobile-adaptive-missing]]