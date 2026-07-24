
# 原型 HTML 开发避坑清单

> 日期：2026-06-22 | 来源：经营分析看板原型 HTML 一天内踩到的全部坑
> 用途：后续任何 HTML/前端原型开发时必读

---

## 本次全部 Bug 清单

### Bug 1：PowerShell Set-Content 破坏 UTF-8 中文

**现象**：JS 代码里所有中文字符变成 `���` 乱码，页面 JS 语法报错

**根因**：Windows PowerShell 5.1 的 `Get-Content | -replace | Set-Content -Encoding UTF8` 管道处理多字节 UTF-8 字符时，内部字符串转换会损坏某些字节序列

**修复**：用 Python `open(file, 'w', encoding='utf-8')` 重写文件

**避坑规则**：
- 🔴 **绝对禁止**用 PowerShell 对含中文的 UTF-8 文件做文本替换
- ✅ 文本替换用 Python 脚本（`open().read().replace().write()`）
- ✅ 或用 Edit 工具（基于字节级匹配，不损坏编码）
- ✅ 必须用 PowerShell 时，仅操作纯 ASCII 内容

---

### Bug 2：CDN 选型不考虑国内网络

**现象**：页面打开 5-8 秒白屏，Vue 模板语法裸露显示

**根因**：`unpkg.com` 在国内被墙/极慢，Vue/ElementPlus/ECharts 三个核心库加载失败。Vue 不初始化 → `v-if`/`v-for` 等指令不执行 → 所有隐藏的 DOM（弹窗、空状态）全裸展示

**修复**：换成 `cdn.bootcdn.net`（国内最快免费 CDN）

**避坑规则**：
- 🔴 **面向国内用户的 HTML 原型，CDN 首选 bootcdn**，不用 unpkg/jsdelivr
- ✅ bootcdn 可用资源：Vue 3.4.21、Element Plus 2.6.1、Element Plus Icons 2.3.1、ECharts 5.5.0
- ✅ CDN URL 格式：`https://cdn.bootcdn.net/ajax/libs/{包名}/{版本}/{文件路径}`

---

### Bug 3：Vue 原型不加 v-cloak

**现象**：页面打开瞬间弹窗（job progress modal）、`{{ }}` 模板语法随处可见

**根因**：Vue 从 CDN 加载需要 1-3 秒。在这期间，浏览器按普通 HTML 渲染所有 DOM，包括 `v-if="false"` 的元素和 `{{ variable }}` 模板表达式。用户看到的是裸 Vue 模板。

**修复**：
```css
[v-cloak] { display: none !important; }
```
```html
<div id="app" v-cloak>...</div>
```
加一个加载提示 `<div id="app-loading">` 放在 `#app` 外面，`onMounted` 里隐藏。

**避坑规则**：
- 🔴 **所有 CDN 加载的 Vue 原型必须加 v-cloak**
- ✅ `[v-cloak] { display: none !important; }` 放在 `<style>` 第一行
- ✅ `#app` 元素加 `v-cloak` 属性
- ✅ 加加载提示 spinner（纯 HTML/CSS，不依赖 JS），Vue mount 后用 `document.getElementById().style.display='none'` 隐藏

---

### Bug 4：UTF-8 BOM 放在 DOCTYPE 前面

**现象**：部分浏览器进入怪异模式，页面渲染异常

**根因**：Windows 系统创建的 UTF-8 文件默认带 BOM（`EF BB BF`），BOM 在 `<!DOCTYPE html>` 之前会导致某些浏览器无法正确识别文档类型

**修复**：用 Python `open(file, 'r', encoding='utf-8-sig').read()` + `open(file, 'w', encoding='utf-8').write()` 去掉 BOM

**避坑规则**：
- 🟡 HTML 文件保存为 **UTF-8 without BOM**
- ✅ 用 Python `encoding='utf-8'`（不带 `-sig`）写入
- ✅ 用 Edit 工具（自动处理编码）

---

### Bug 5：overflow-x 和 overflow-y 分离不彻底

**现象**：
- 表格内容超出高度时，右侧滚动条拖不动
- 表格内容不超出高度时，右侧仍显示一条假滚动条
- 一个页面出现两条竖向滚动条

**根因**：
1. `.sheet-table-wrap` 只设了 `overflow-x:auto`，缺少 `overflow-y` → 垂直溢出不生成滚动条
2. `::-webkit-scrollbar-thumb` 颜色 `rgba(148,163,184,.25)` 透明度 75%，白底上几乎看不见
3. 所有 `.sheet-table-wrap` 公用一个 CSS 类，`max-height` + `overflow:auto` 一刀切 → 7 行数据不需要滚动的容器也会显示滚动条
4. `.sheet-tabs` 只设 `overflow-x:auto`，缺少 `overflow-y:hidden` → 竖向出现多余滚动条空间

**修复**：
- CSS 基类只保留 `overflow-x:auto`（横向滚动）
- 需要纵向滚动的容器用**内联 style** 精确控制：`style="max-height:560px;overflow-y:auto;overflow-x:auto"`
- 滚动条滑块改为实色 `#94a3b8`，悬停 `#64748b`，加 track 底色
- `.sheet-tabs` 加 `overflow-y:hidden`

**避坑规则**：
- 🔴 **不要用 CSS 类一刀切控制滚动**，按容器实际数据量分两种情况：
  - 数据量固定的（≤10 行）→ 只要 `overflow-x:auto`
  - 数据量动态的（可能超过可视区）→ 加内联 `max-height` + `overflow-y:auto`
- ✅ 滚动条样式必须同时定义 `::-webkit-scrollbar`、`::-webkit-scrollbar-track`、`::-webkit-scrollbar-thumb`、`:hover`
- ✅ 滚动条滑块颜色用实色，透明度 ≥ 0.6
- ✅ `overflow-x:auto` 的容器必须同时设 `overflow-y:hidden`（反之亦然），避免无内容方向出现空滚动条

---

### Bug 6：用 Python compile() 校验 JavaScript 语法

**现象**：Python 报 `invalid character '（' (U+FF08)` 错误，但浏览器打开 JS 正常执行

**根因**：`compile(js_code, '<prototype>', 'exec')` 编译的是 **Python** 语法，不是 JavaScript。全角括号 `（` 在 JS 注释里完全合法，但在 Python 语法里是非法字符。

**避坑规则**：
- 🔴 **不要用 Python `compile()` 校验 JS 语法**，它只能校验 Python
- ✅ 校验 JS 语法用 Node.js：`node --check script.js` 或 `node -e "new Function(fs.readFileSync('...','utf-8'))"`
- ✅ HTML 原型的最终验证靠**浏览器实际打开**，不是静态分析
- ✅ 静态检查只验证 HTML 结构完整性（标签闭合、CDN 链接、关键字符串存在）

---

## 原型 HTML 开发检查清单

每次交付原型 HTML 前，逐项验证：

### 编码与加载
- [ ] 文件编码：UTF-8 without BOM（文件头是 `<!DOCTYPE html>` 不是 `﻿<!DOCTYPE html>`）
- [ ] CDN 全部用 bootcdn（国内用户）或确认目标用户网络可访问
- [ ] 加了 `[v-cloak]` 样式 + `#app` 上 `v-cloak` 属性
- [ ] 加了加载提示 spinner

### 滚动与交互
- [ ] 每个表格容器按实际数据量决定是否需要纵向滚动（不用 CSS 类一刀切）
- [ ] 滚动条样式完整（track + thumb + hover），滑块颜色可见（不透明）
- [ ] `overflow-x:auto` 的容器同步设了 `overflow-y:hidden`（反之亦然）
- [ ] 不存在嵌套滚动（同一方向不会出现两条滚动条）

### 工具使用
- [ ] 文本替换用 Edit 工具或 Python，不用 PowerShell
- [ ] JS 语义验证用浏览器打开实测，不用 Python compile()
- [ ] 最终验证走浏览器，不是命令行

---

## 关联记忆

- [[feedback_first_principle_objective_facts]] — 客观事实校验
- [[reference_knowledge_platform_bugs_lessons]] — 25 个 bug 教训（知识管理平台）
- [[feedback_delete_check_parent]] — 删代码前向上读 3 层父级
- [[feedback_financial_system_doc_sync]] — 文档同步规则
