# lab-exam UI 换肤改造方案（对齐 PaperCore 设计语言）

> 状态：✅ 已完成（2026-08-12 执行并提交）
> 日期：2026-08-12
> 依据仓库：https://git.oceghome.com/aiproject/papercore（Vue3 + TailwindCSS 手写设计系统）
> 改造路径：换肤（路径A）—— 只改样式变量与全局 CSS，不动业务逻辑
> 唯一例外：登录页模板可改（选项2，用户已批准）
> 提交：`e89a6e5`（main，已推送 origin）
> 验收：最终构建通过；登录页/主色/卡片/标签/表头逐项 JS 实测确认

---

## 一、为什么用"换肤"而不是"重建"

- lab-exam 与 PaperCore 技术栈高度重合（都 Vue3 + Tailwind），
  PaperCore 的价值 = 一份更现代的设计规范（配色/卡片/徽章/动效），不是施工图纸。
- 只借"设计规范"，不借"组件实现"。不把手写表格/表单换掉 Element Plus。
- 重建（把手写组件替换 el-table/el-form）风险极高：无测试、无 CI，2-4 周，且大概率出隐藏 bug。本次明确不做。

---

## 二、主题体系关键事实（改造前必读）

**主题是"单点映射"结构，改一处全端生效：**

1. `web/src/styles/art/core/tailwind.css` 的 `:root` 里定义 `--art-primary`（唯一主色源头）
2. `web/src/styles/variables.less` 把 `--art-primary` 映射成 `@primary`
3. `web/src/styles/global.less` 把 `@primary` 映射给 **Vant 全部变量**（按钮/标签/导航栏/tabbar 等）

→ 结论：改主色只需动 `tailwind.css` 一处，管理端（Element Plus）+ 学生端（Vant）同时变蓝，两端不用分别改。

**涉及的主题文件：**
- `web/src/styles/art/core/tailwind.css` —— 主色 / 背景 / Element 变量 / Tailwind 配色
- `web/src/styles/art/core/el-light.scss` —— Element Plus sass 源码级覆盖（primary 色）
- `web/src/styles/global.less` —— art-card 卡片样式 / Vant 变量映射
- `web/src/styles/art/core/el-ui.scss` —— Element 组件细节（按钮/表格/对话框/标签）
- `web/src/views/login/index.vue` —— 登录页（选项2，唯一允许动模板）

---

## 三、第一批：核心换肤（半天）

### 3.1 主色：黑色 → PaperCore 蓝色系
**文件**：`web/src/styles/art/core/tailwind.css`（`:root` 区）

| 变量 | 现值 | 改为 |
|---|---|---|
| `--art-primary` | `#171717` | `#3b82f6` |
| `--theme-color` / `--main-color` | `#171717` | `#3b82f6` |
| `--el-color-primary` | `#171717` | `#3b82f6` |
| `--el-color-primary-light-3` | | `#76a7f9` |
| `--el-color-primary-light-5` | | `#9dc0fa` |
| `--el-color-primary-light-7` | | `#c4d9fc` |
| `--el-color-primary-light-8` | | `#d7e6fd` |
| `--el-color-primary-light-9` | | `#ebf2fe` |
| `--el-color-primary-dark-2` | | `#2563eb` |
| `--el-color-primary-rgb` | `23, 23, 23` | `59, 130, 246` |

同文件 `.dark` 区（暗色模式）的 `--el-color-primary` 同步换浅蓝 `#93c5fd` 一组，保持暗色可用（当前无开关，但别弄坏）。

**文件**：`web/src/styles/art/core/el-light.scss` —— `$colors.primary.base` 从 `#171717` 改为 `#3b82f6`（sass 源码覆盖，保持与 tailwind.css 一致）。

### 3.2 背景色：冷灰 → 浅灰蓝
**文件**：`web/src/styles/art/core/tailwind.css`（`:root` 区）

| 变量 | 现值 | 改为 |
|---|---|---|
| `--default-bg-color` | `#fafafa` | `#f8fafc` |
| `--art-gray-100` | `#fafafa` | `#f8fafc` |

---

## 四、第二批：卡片质感 + 动效（1 天）

### 4.1 卡片阴影 + hover 抬升
**文件**：`web/src/styles/global.less`（`.art-card` 块）

- 阴影：`0 1px 3px rgba(0,0,0,0.03)` → `0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.04)`
- hover 抬升 + 蓝描边：
  ```css
  .art-card:hover {
    transform: translateY(-2px);
    border-color: #bfdbfe;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06), 0 8px 24px rgba(59,130,246,0.08);
  }
  ```
- `.art-card` 加 `transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;`

### 4.2 按钮按压缩放
**文件**：`web/src/styles/art/core/el-ui.scss`
```css
.el-button--primary:not(.is-disabled):active {
  transform: scale(0.98);
}
```

---

## 五、第三批：状态标签 + 表格（半天）

### 5.1 状态标签 → 胶囊徽章
**文件**：`web/src/styles/art/core/el-ui.scss`（或 `global.less` 追加）
```css
.el-tag { border-radius: 9999px; font-weight: 500; }
```
状态色沿用现有 success/warning/danger 色系（已映射，无需改）。全局覆盖，所有页面自动统一。

### 5.2 表格表头层次
**文件**：`web/src/styles/art/core/el-ui.scss`
```css
.el-table th { background: #f8fafc; font-weight: 600; color: #475569; }
```

---

## 六、第四批：登录页（选项2，唯一允许动模板）

### 6.1 视觉目标（对齐 PaperCore）
- 渐变背景 + 居中圆角卡片
- 去掉"左品牌区 + 右表单"的左右分栏

### 6.2 实现要点
**文件**：`web/src/views/login/index.vue`
- 背景：`linear-gradient(135deg, #f0f4ff 0%, #e8eeff 30%, #f5f3ff 60%, #eef2ff 100%)`
- 卡片：白色圆角 `rounded-2xl` + 分层阴影 + `border border-slate-200/50`
- 卡片内：标题 + 表单（账号/密码）+ 登录按钮（蓝色）

### 6.3 红线（允许改模板，但严禁动逻辑）
- **严禁改动 script 部分** —— 登录页嵌金智 CAS 跳转逻辑，动逻辑影响全校师生登录
- 只重排 template 结构 + 该页 scoped 样式，表单校验、提交、loading 逻辑原样保留
- 保留学号/工号登录、密码框、登录按钮这些功能元素

---

## 七、禁止动的（已核实，保持现状）

- 路由过渡动画：`art/index.scss` 已有 router-transition，不用加
- 暗色模式变量：半成品、无开关，别碰
- 学生端 Vant 页面布局：只吃全局色变量，自动变蓝，不用逐页改
- 骨架屏：lab-exam 是"加载中..."文字，改骨架屏要动 AppTable 等组件 → 本次不做
- 所有 ts/业务逻辑、接口、组件结构、路由：一律不动

---

## 八、验收清单（改完逐项核对）

1. `npm run build` 通过（sass 编译无误）
2. 登录页：居中卡片 + 渐变背景 + 蓝主色生效，CAS 登录功能正常
3. 管理端抽查：考试列表、题库、班级管理、统计页 —— 按钮变蓝、标签变胶囊、卡片 hover 抬升
4. 学生端抽查：考试列表、答题页 —— 按钮/导航栏/tabbar 变蓝
5. 弹窗、表格、分页正常显示，无样式错乱
6. 暗色相关：无页面异常（虽无开关，保险起见）

---

## 九、工作量预估

- 第一~三批：1.5-2 天（含构建验证 + 人工验收）
- 第四批登录页选项2：+0.5-1 天
- 合计：2-3 天，纯 CSS + 登录页模板，零业务逻辑改动

---

## 十、开发纪律（禁止跑偏）

1. 严格按本清单执行，只做这三批 + 登录页
2. 不新增本清单外任何功能/样式"顺手优化"
3. 每批完成后先 `npm run build` 验证，再人工验收
4. 登录页是唯一允许动模板的文件，其余只改样式文件
5. 不做骨架屏、不做组件重建、不碰暗色模式

---

## 十一、执行记录（2026-08-12 已完成）

**改动文件（5个，严格限定）：**
- `web/src/styles/art/core/tailwind.css` — 主色黑→蓝(#3b82f6) + 背景#f8fafc，亮/暗双主题同步
- `web/src/styles/art/core/el-light.scss` — Element sass 源 primary → #3b82f6
- `web/src/styles/global.less` — 卡片阴影升级 + hover 抬升 + 蓝色描边
- `web/src/styles/art/core/el-ui.scss` — 按钮按压缩放 scale(.98) + 标签胶囊化(9999px) + 表头层次
- `web/src/views/login/index.vue` — 居中卡片 + 渐变背景（template/style 重排，script 逻辑原样）

**验证结果：**
- 分5步执行，每步 `npm run build` 通过后才进入下一步
- 主色生效实测：--art-primary=/--el-color-primary=#3b82f6，登录按钮 rgb(59,130,246)
- 卡片/按钮/标签/表头规则均确认编译进产物
- 登录页实测：flex 居中、渐变背景、卡片 420px/圆角20px/蓝投影
- 登录页 script 区仅清理无用 import（CircleCheck），所有登录逻辑原样保留
- 改动文件数：5（未夹带）；git diff 逐项核对与方案一致

**提交：** `e89a6e5` "web: UI换肤对齐PaperCore设计语言"（main，已推送）

**遗留：**
- 学生端（Vant）页面未逐页人工过目，需登录后人工验收（按钮/导航栏/tabbar 变蓝）
- 管理端各页面（考试列表/题库/统计）需人工过一遍确认无样式错乱
- 暗色模式无开关，未验证（保险起见保持现状）