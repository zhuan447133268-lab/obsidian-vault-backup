---
date: '2026-07-15'
status: 进行中
tags:
  - 实验室准入考试系统
  - 前端迁移
  - art-design-pro
  - Element Plus
  - 规划方案
---
# 2026-07-15 前端迁移 art-design-pro 详细规划方案

## 背景与目标

当前前端使用 Vant（移动端组件库），导致 admin/教师/学校管理端页面看起来“灰蒙蒙、像置灰、很难看”。用户决定迁移到 art-design-pro（Vue 3 + Vite + TypeScript + Element Plus 管理后台模板），让管理端变成现代 admin 风格。

**目标**：admin/教师/学校管理端全面改用 Element Plus + art-design-pro 布局；学生考试端保持原有 Vant 移动交互；所有后端 API 和业务流程不变。

## 迁移策略

**增量迁移**：在现有 `D:\2026准入题库\web` 仓库内引入 Element Plus 与 art-design-pro 的布局/主题能力，逐步替换页面，而不是推倒重来。

- 学生移动端**保留 Vant**（考试交互复杂、E2E 依赖 Vant DOM）。
- 管理端/教师端**替换为 Element Plus** 组件。
- Vant 与 Element Plus CSS 变量命名空间不同（`--van-*` vs `--el-*`），可共存，只需处理全局 reset 冲突。
- **不照搬 art-design-pro 演示化代码**：模板包含暗色模式、work-tab、settings panel、独立 store 等较重功能。实际采用「借鉴布局/主题，自研 ElMenu + ElHeader 布局」的轻量化方案。

## 分阶段计划

### Phase 0 - 模板调研与脚手架（1-2 天）✅ 已完成

- 拉取/阅读 art-design-pro 源码，重点看 layout、router/menu、theme、vite config。
- 安装依赖：`element-plus`、`@element-plus/icons-vue`、`unplugin-auto-import`、`unplugin-vue-components`、`sass`。
- 更新 `vite.config.ts`：增加 Element Plus / icon resolver，保留 `@` alias 与 less 预处理。
- 更新 `src/main.ts`：保留 Vant，引入 Element Plus CSS 与模板基础样式。
- 新增 `src/styles/element-theme.less`：把 `--el-color-primary` 映射到现有 Soft Clay 色板。

**交付**：dev 能启动，无构建报错。

### Phase 1 - 共享基础设施（2-3 天）✅ 已完成

- `src/api/request.ts`：`showToast` → `ElMessage.error`，保留刷新队列与双认证逻辑。
- `src/router/index.ts`：admin 路由 layout 替换为 art-design-pro 布局；保留 `meta.roles` 与路由守卫。
- 新增 `src/router/menu.ts`：按角色生成侧边菜单。
- 重写 `src/layouts/AdminLayout.vue`：左侧 `ElMenu`、顶部 Header、面包屑、内容区。
- 迁移 `src/views/login/index.vue`、`src/views/error/403.vue`、`src/views/error/404.vue` 到 Element Plus。

**交付**：登录、403/404、角色首页、菜单可见性可用；Playwright 登录相关用例可跑通。

### Phase 2 - 学校管理员页面迁移（3-4 天）✅ 已完成

迁移 `src/views/school-admin/*.vue`（共 11 个页面）。

核心替换：
- `<table>` → `ElTable` / `ElTableColumn`
- `van-field` → `ElInput` / `ElSelect` / `ElDatePicker` + `ElFormItem`
- `van-dialog` + `van-form` → `ElDialog` + `ElForm`
- `van-button` → `ElButton`，`van-tag` → `ElTag`，`van-loading` → `v-loading`
- `van-empty` → `ElEmpty`，`van-pagination` → `ElPagination`
- `van-uploader` → `ElUpload`
- 移动端 `van-picker` 弹窗 → 桌面端 `ElSelect`

新增可复用组件：`AppTable.vue`、`AppSearchForm.vue`、`AppFormDialog.vue`。

同时迁移共享组件 `src/components/CertificateExportPanel.vue`。

**交付**：学院/专业/班级 CRUD、用户管理、学院管理员、数据导入、题库、证书导出、全校统计全部可用。

### Phase 3 - 学院管理员页面迁移（2-3 天）⏳ 待启动

迁移 `src/views/college-admin/*.vue`（4 个页面）：
- `index.vue`
- `teachers.vue`
- `certificates-export.vue`（几乎不变，依赖已迁移的 `CertificateExportPanel.vue`）
- `statistics.vue`

复用 Phase 2 组件。

**交付**：学院管理员首页、本院教师管理、证书导出、学院统计可用。

### Phase 4 - 教师页面迁移（3-4 天）待启动

迁移 `src/views/teacher/*.vue`（3 个页面），交互最复杂。

重点：
- 考试列表状态筛选用 `ElRadioGroup` / `ElTag` 组。
- 创建考试弹窗：学院/班级 `ElSelect` 联动，时间 `ElDatePicker`。
- 考试详情页：学生选择表格用 `ElTable` 的 `type="selection"`，试卷预览用 `ElDialog` + `v-loading`，发布/关闭/组卷/补考按钮全替换。

**交付**：教师可创建、发布、关闭、组卷、预览、提醒、生成补考；`teacher-flow.spec.ts`、`makeup-flow.spec.ts` 跑通。

### Phase 5 - 学生移动端兼容检查（1-2 天）待启动

- 学生视图**不替换** Vant 组件。
- 检查 Element Plus 全局样式对学生页 reset 的影响，必要时覆盖恢复。
- 验证 MobileLayout 底部 tabbar、考试页倒计时、答题提交、证书查看在 390×844 视口正常。

**交付**：`student-flow.spec.ts`、`certificate-flow.spec.ts`、`makeup-flow.spec.ts` 学生部分通过。

### Phase 6 - 全量验证与收尾（2-3 天）待启动

- `npm run build` 零 TS 错误。
- `npx playwright test` 全量通过，失败用例补充 `data-testid`。
- 清理 admin 视图残留 Vant import；删除旧 AdminLayout 备份。
- 验证 light/dark 模式（若 art-design-pro 支持）。
- 验证双认证模式：`bearer` 与 `cookie`。
- 更新 README。

**交付**：构建通过、E2E 全过、双认证验证通过。

## 文件级关键变更

### 新增
- `src/router/menu.ts`
- `src/styles/element-theme.less`
- `src/components/AppTable.vue`
- `src/components/AppSearchForm.vue`
- `src/components/AppFormDialog.vue`

### 大幅修改
- `package.json`、`vite.config.ts`、`src/main.ts`
- `src/api/request.ts`
- `src/router/index.ts`
- `src/layouts/AdminLayout.vue`
- `src/views/login/index.vue`
- `src/views/error/403.vue`
- `src/views/error/404.vue`
- `src/views/school-admin/*.vue`
- `src/views/college-admin/*.vue`
- `src/views/teacher/*.vue`
- `src/components/CertificateExportPanel.vue`

### 保留（仅兼容性检查）
- `src/layouts/MobileLayout.vue`
- `src/views/student/*.vue`

### 删除/废弃
- 旧 `src/layouts/AdminLayout.vue` 备份（Phase 6 清理）
- admin 页面中 Vant 局部注册与样式（Phase 6 清理）

## 时间估算

| 阶段 | 天数 |
|------|------|
| Phase 0 - 模板调研与脚手架 | 1-2 |
| Phase 1 - 共享基础设施 | 2-3 |
| Phase 2 - 学校管理员页面 | 3-4 |
| Phase 3 - 学院管理员页面 | 2-3 |
| Phase 4 - 教师页面 | 3-4 |
| Phase 5 - 学生端兼容 | 1-2 |
| Phase 6 - 全量验证与收尾 | 2-3 |
| **合计** | **14-21 天** |

## 主要风险与应对

1. **art-design-pro 源码结构与预期不符** ✅ 已确认演示化较重，采用自研轻量化布局。
2. **Vant 与 Element Plus CSS 冲突**：分变量命名空间覆盖；对学生页做 390×844 回归。
3. **管理端 E2E 选择器失效**：迁移时同步加 `data-testid`。
4. **日期格式不兼容**：`ElDatePicker` 配置 `value-format="YYYY-MM-DDTHH:mm:ss"`。
5. **主题色仍显灰旧**：不只改 primary，还要覆盖 `--el-color-primary-light-*`、`--el-fill-color`、`--el-bg-color` 等完整令牌。
6. **ElTable 行类型跨组件丢失**：操作列使用 `as Type` 显式转换，已在 Phase 2 验证通过。

## 验证标准

- 每阶段：`npm run dev` 无控制台报错，`npm run build` 通过，本阶段页面手工走查通过。
- Phase 6：`npx playwright test` 全量通过，双认证模式均验证通过。

## 共享组件接口约定

### AppTable.vue
```vue
<app-table :data="list" :loading="loading" empty-text="暂无数据">
  <el-table-column prop="name" label="名称" />
  <!-- 操作列注意用 as Type 转换 -->
  <el-table-column label="操作">
    <template #default="{ row }">
      <el-button @click="handleEdit(row as ItemType)">编辑</el-button>
    </template>
  </el-table-column>
</app-table>
```

### AppSearchForm.vue
```vue
<app-search-form @search="loadData">
  <el-form-item><el-input v-model="keyword" /></el-form-item>
  <el-form-item><el-select v-model="role" /></el-form-item>
</app-search-form>
```

### AppFormDialog.vue
```vue
<app-form-dialog v-model="showForm" title="标题" @cancel="showForm = false" @confirm="onSubmit">
  <el-form :model="form">...</el-form>
</app-form-dialog>
```

## 参考

- Art Design Pro GitHub: https://github.com/Daymychen/art-design-pro
- Art Design Pro Docs: https://www.artd.pro/docs/en/
- 当前进度交接：Projects/实验室准入考试/2026-07-15 前端迁移工作暂停交接
- 项目技术方案：实验室准入考试系统/技术方案-2026-07-07
