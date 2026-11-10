---
date: 2026-11-09
source: GitHub `AragornZJF/bigdata-dashboard-skill` / Gitee 镜像 `scedm/bigdata-dashboard-skill` + 本机 360 文件全量拉取、5 处修复、双模式实跑与 Chrome 实渲
url: https://github.com/AragornZJF/bigdata-dashboard-skill
type: 技能卡
tags: [AI工具, 数据可视化, 大屏, ECharts, 单文件HTML, 离线自包含, AGPL, Skill修复, 财务看板, 交付自检, 视觉改造, 实渲验收, 真实数据, 口径自洽]
---

# bigdata-dashboard：Excel/JSON → 单文件离线大屏（本地修复版 v1.3）

> 本机安装：`~/.workbuddy/skills/bigdata-dashboard/`（365 文件 / 46 MB）
> 同目录：`PATCHES.md`（修复明细）· `NOTICE.md`（授权边界）· `README.upstream.md`（上游原文）· `SKILL.md`（AI 调用入口）
> 2026-11-09 修好并安装；同日按验收反馈追加 **v1.2 视觉重写**（字体 / 配色 / 卡片 / 12+ 类图表 / showcase 样例），再用真实财务 xlsx 走完整链路追加 **v1.3 真实数据检验**（口径自洽 / 表格自适应 / 图表按数据形状自动降级）。双模式实跑 + Chrome 1920×1080 实渲验收通过

## 一句话定义

一个 AI skill：**Excel / JSON → 单文件 HTML 数据大屏**，15 套行业骨架 + 1 套自动布局引擎，ECharts / CSS / 图片全部内联，双击离线可开。纯 Python 标准库 + `openpyxl`，构建过程零网络请求。

上游宣称「无 CDN、完全自包含、1–8 MB」，实测**默认路径根本出不了图**。所以这张卡的重点不是"它会做什么"，而是**修了什么、为什么这么修**——这套排查方法比 skill 本身值钱。

## 修好了什么（5 处，全部实测定位到行）

| # | 上游问题 | 根因 | 修复 |
|---|---|---|---|
| 1 | 默认模式断网白屏 | `_build_layout_mode` 直接把 `renderer.html` 原样写出，**从不调用仓库自带的 `_inline_assets()`**（只有模式2 调用），残留 `cdn.jsdelivr.net` | renderer 改本地 `vendor/echarts.min.js`；布局模式统一走内联；新增构建时零外链强制自检 |
| 2 | 4 张背景图是外链 | `renderer.html` 引用 `raw.githubusercontent.com/jianlli/BigDataView_/...` 的 bg/head_bg/bg01/bg02 | 全改纯 CSS 渐变，顺带移除第三方素材依赖 |
| 3 | **8 个组件只显示统计卡，图表区全空** | `#dash-root` 没有任何尺寸定义 → `.dash-body{height:calc(100% - header)}` 与各行 `15% / 28.3%` 全部失去参照 → 图表容器高 0 | `#dash-root{width:100%;height:100%;overflow:hidden}` |
| 4 | 左下角一张图只有坐标轴 | `layout_builder.py` 没有 `radar` 分支，radar 类型落进默认 `bar`，多维 value 数组被塞进 `series.data` | 新增 radar option 构造（indicator 自动取维度与上浮最大值） |
| 5 | 文档互相打架 | 上游 README 说「11 自带源 / 4 需 `--source-dir`」，SKILL/CLAUDE/菜单说 15 全自带；子智能体让人查 `--help` 但脚本会把 flag 当数据路径报错 | 核实源码后统一口径：**15 个全自带源**；补 `--help/-h`；上游 README 归档，重写修复版说明 |

**排查经验（可迁移到任何"生成了但看不见"的 HTML 产物）**：
`--dump-dom` 数 `<canvas>` → 7 个都在 → 说明 JS/ECharts 正常，是 **CSS 高度塌陷**而不是脚本错误。这类"假成功"光看构建日志和文件体积永远发现不了，**必须实渲截图**。我上次做定制财务大屏踩的是同一个坑（`.chart{flex:1;min-height:0}`）。

### 实测对比

| 项 | 修复前 | 修复后 |
|---|---|---|
| 模式1 产物 | 37 KB，CDN 外链，图表全空 | **1.02 MB，ECharts 内联，4 行 8 组件全渲染** |
| 模式1 外链 | 1 个 CDN + 4 张第三方图 | **0** |
| 模式2 `smart_city` | 15.8 MB（最小子集） | 19.12 MB（完整仓库，43 图内联，`DASHBOARD_DATA` 注入成功），0 外链 |
| `--help` | 当数据路径报错 | 正常输出，退出码 0 |
| 雷达图 | 空白 | 正常渲染 |
| `verify_offline.py` | 无 | **2/2 PASS** |

> 上游说产物 1–8 MB，实测 `smart_city` 19 MB（单张背景图就 4.5 MB）。宣传数字别信，自己量。

## v1.2 视觉重写（验收反馈驱动）

第一版实渲反馈「字体难看、饼图扎堆、不高级」。核查是两个原因叠加：

1. 模式1 复用的 `generic/example.json` **其实是模式2 骨架的 schema 样例**——7 张图里 3 张 `pie`，id 是 `pe01` / `echarts1` 这类骨架专用名。默认路径拿它出图，当然饼图扎堆。
2. 上游渲染器是 Microsoft YaHei + Impact + 亮黄 `#fef000` 大数字 + 粗暴 rem 缩放。`examples/` 里那些精致截图**全部来自模式2 行业骨架**，根本不是默认路径。

改了三层（CSS 覆写可回退，不动原有逻辑）：

| 层 | 改动 |
|---|---|
| CSS 覆写 | `assets/renderer.html` 加 `PREMIUM VISUAL LAYER`：深色高级配色、无衬线 + 等宽数字字体栈、卡片细边框 / 圆角 / 渐变高光、顶栏副标题、KPI 语义化 |
| 图表主题 | 新增 `themeChart()` 全局注入，统一 tooltip / axis / legend / 配色 / 动画；换掉上游黄绿蓝调色板 |
| 图表类型 | `layout_builder.py` 7 → **12+ 类**：donut / gauge / funnel / heatmap / stackBar / stackArea / combo / bubble / polarBar / treemap / radar / hbar；顺带修 `has_chart_config()` 把 `{categories, series}` 误判成 ECharts option、以及 `ctype.lower()` 让驼峰类型名全部失配 |

新增 `assets/templates/data/generic/showcase.json`，12 类图表一次跑全。**以后看效果 / 做演示用 showcase，别用 example.json**：

```bash
"$PY" scripts/build_dashboard.py assets/templates/data/generic/showcase.json \
    --theme dark --title "集团数字化运营驾驶舱" --output output/showcase.html
```

**逐轮实渲修的细节**：热力图色标压 X 轴 → 移底部；极坐标标签挤团 → 缩短文案 + 调半径；环形 / 雷达偏小 → 放大；环内合计两行贴死 → `itemGap` 2→7、`top` 40%→36%；KPI 末卡被 grid gap 挤出裁切 → flex 等分；单位被 `display:block` 顶到第二行 → inline。每处都是 1920×1080 截图驱动，不是猜的。

**实测**：5 行 13 组件全渲染、1.04 MB、零外链 PASS；模式2 `generic` 骨架回归 1.59 MB / 17 图内联 / PASS；全脚本 `py_compile` 通过。

> **可迁移经验**：① 渲染器改造必须**双模式回归**——CSS 覆写与全局主题对两条路都生效，只验一条会漏掉骨架模板被改样式。② 用户说「不好看」时，先确认他看到的参照物是哪条路径生成的——这次 demo 截图和默认产物压根不是同一个模式。

## v1.3 真实数据检验（2026-11-09 17:00–18:00）

用户反馈「这版比上一版好多了」后，拿真实 `集团整体报告.xlsx`（142 园 / 98 在营 / 13+1 区域 / 4 类建园类型）走**装好的 skill 模式1**，不自写 HTML。适配层 `财务经营大屏/to_skill_data.py` 把明细转成 `{title, subtitle, statCards, charts, tables}`，11 类图表全部由 xlsx 真实聚合，**一个数都没构造**。

**最有价值的发现不是视觉，是口径**：自动生成的环形图中心显示 60,445 万，顶部 KPI 却写 48,666.93 万。查下来汇总 sheet 是全 142 园口径（60,444.52 万），KPI 是 98 在营（48,666.93 万），差 44 关园的 11,777.59 万；另外汇总 sheet 只有 13 区、明细有 14 区（多出「未分配」5 园 / 2,502.56 万），KPI 与区域图也在打架。**自动布局会同时生成多个合计型图表，口径一混用立刻同屏穿帮；自写单图时反而容易忽略。** 最终统一按在营明细重算：环形 / 树图 / 区域排行三个合计精确等于 KPI，KPI 覆盖区域改 14，差异全部写进「数据体检」表。

**v1.3 补的三类通用能力**（不针对某份数据硬编码）：

| 能力 | 触发 / 说明 |
|---|---|
| 可配置 `subtitle` | 顶层字段，中文业务屏不再顶着硬编码英文 `Real-time Analytics` |
| `renderTable()` 的 `fitRows()` | 按容器高度动态压缩行高，体检表 6 行全部常驻可见（大屏投屏没人滚表格） |
| `polarBar` 自动降级 | 数据 max/min > 8 倍 → 自动改横向柱 + 外置数值标签；财务 `72/5=14.4×` 降级，showcase `3820/980=3.9×` 保留。**图表选型服从数据形状**，数据本身不做对数 / 截断 |

**skill 版 vs 自写版（同一份财务数据）**：

| | skill 版（本轮） | 自写版（上午） |
|---|---|---|
| 观感 | v1.2 后接近，11 类图表更丰富 | 更克制，6 图 + 数据体检 |
| 数据贴合 | 需写一次适配层；合计型图表多，口径必须统一 | 完全自定义，口径天然贴合 |
| 工作量 | 一个 JSON + 一条构建命令；换数据重跑 3 个脚本 | 要写 `template.html` + `build.py` + 手写 ECharts option |
| 授权 | AGPL-3.0，对外商业交付有边界 | 代码与产物完全自有 |
| 适合 | 快速汇报大屏、投屏、教学演示、内部评审 | 正式业务看板、对外交付、需长期维护的产品 |

**手感结论**：写适配层是一次性成本，之后换数据只重跑 `extract_data.py → to_skill_data.py → build_dashboard.py`；但**口径自查这一步不能省**，它比选图表类型更决定交付质量。正式对外交付仍走自写版（授权干净），内部快速出屏可以放心用 skill 版了——这修正了下面「真实业务口径明确的正式看板都不适合」的旧判断，准确说法是：**适配层做对了口径，skill 也能接真实业务数据；拦路的是 AGPL 授权，不是能力。**

## 双模式与适用边界

| | 模式1 布局引擎（默认） | 模式2 骨架模板（`--template`） |
|---|---|---|
| 输入 | 任意 Excel/JSON，按数据形状自动排 9 类组件 | 符合该骨架 `example.json` schema 的数据 |
| 风格 | 通用深色科技风（本次已换成自有纯 CSS 渐变） | 15 套行业风：智慧城市 / 电厂 / 医药 / LPL / 新能源车… |
| 体积 | ~1 MB | 1–19 MB |
| 授权风险 | 低（自有 renderer，本次已清掉第三方图） | 高（第三方 BigDataView_ 模板，见下） |
| 适合 | 有数据不挑风格、快速出样、内部汇报 | 演示 / 风格参考 / Mock 先行预览 |

**模式2 骨架不适合**真实业务口径明确的正式看板：15 套骨架的字段是通用演示结构，跟 [[经营分析看板模块-看板维度规范]] 那套维度对不上。**模式1 经适配层可以**（见上面 v1.3 节，本轮已用真实财务 xlsx 验证）。2026-11-09 上午做集团经营大屏时选了自写单文件 ECharts（`D:/03-个人文档/学习空间/财务经营大屏/集团经营分析大屏.html`），1.12 MB、零外链、每个数值可追溯 xlsx、无授权包袱；下午用 skill 版又出了一张（`skill版_集团经营大屏.html`，1.05 MB / 13 组件）。**数据口径优先于模板风格；对外交付优先自写版是因为 AGPL，不是因为 skill 做不出来。**

## 使用速查

```bash
PY="C:/Users/dfjq/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd ~/.workbuddy/skills/bigdata-dashboard && mkdir -p output

# 模式1（有数据、不挑风格）
"$PY" scripts/build_dashboard.py <数据>.json --theme dark --output output/demo.html

# 模式1 · 图表丰富版（v1.2；演示 / 验收优先，12 类图表）
"$PY" scripts/build_dashboard.py assets/templates/data/generic/showcase.json \
    --theme dark --title "集团数字化运营驾驶舱" --output output/showcase.html

# 模式1 · 真实业务数据（v1.3；先定口径、所有合计型图表从同一份明细重算）
"$PY" scripts/build_dashboard.py <适配层产出的>.json --theme dark --output output/业务大屏.html
# JSON 顶层可选 subtitle（中文副标题）、tables（数据体检表，行数自适应）

# 模式2（要行业风格；15 个骨架全部自带源，不用 --source-dir）
"$PY" scripts/build_dashboard.py assets/templates/data/smart_city/example.json \
    --template smart_city --output output/smart_city.html

# 交付前必跑
"$PY" scripts/verify_offline.py output/
```

`--help` / `--list` / `--list-data-templates` 查参数与模板。Excel 可直接喂给构建脚本（三分支自动识别：模板回填 / legacy / 启发式）。
`verify_offline.py` 检查资源型外链、ECharts 内联、数据注入标记、`{{...}}` 占位符残留、体积；先剔除 `<script>` 块内部文本，避免内联库里的 http 字面量误报。

## 关键事实 / 踩坑

1. **43 MB 全包拉不下来**：`git clone`、codeload zip、Gitee archive 全部在 4.8 MB 附近断流。可行解 = Gitee `api/v5/repos/.../git/trees/master?recursive=1` 拿 360 文件清单（含 size）→ Gitee **raw 单文件通道** 10 并发逐文件下载 → 逐个校验字节数，360/360 通过。GitHub API 直连被代理 502，但 Gitee API 通。
2. **脚本依赖 `openpyxl`**，不是纯标准库（上游只分析 `build_dashboard.py` 时容易漏看其他 7 个脚本）。本机 managed venv 已装。
3. `.claude/agents/bigdata-dashboard-expert.md` 是 **Claude Code 专有**，WorkBuddy / 其他 Agent 不加载；能力全部由 `SKILL.md` 驱动。README 里「自动委派子智能体」的说法在非 CC 环境不成立。
4. 只验了 `generic` 布局引擎与 `smart_city` 骨架的 Chrome 实渲，其余 14 套未逐一验收；用到别的骨架，交付前跑一次 `verify_offline.py` + 截图。
5. `device_monitor` 注释里的 CSDN 链接、`telecom_store` 的 HTML4 DOCTYPE DTD URL 是 http 字面量，不是资源加载，不影响离线。
6. 上游 2026-10-30 建仓、单人约 20 commits、25 stars、0 issues，10 天新项目；文档与实现有版本差，遇到矛盾以源码 + 实跑为准。

## 许可证边界（必须记住）

- **AGPL-3.0**，不是库里其他技能常见的 MIT/GPL。本修复版是衍生作品，同样受 AGPL 约束，不能改宽松许可。
- ✅ 个人本地使用、学习研究、内部汇报 / 投屏 / 教学演示、写进知识库（注明来源）。
- ⚠️ 对外分发修改版、或把它做成网络服务（AGPL 第 13 条），须提供对应源码并以相同许可授权。
- ⚠️ **生成产物内联了模板 HTML/CSS/JS，授权链随产物一起走**——"单文件自包含"是技术属性，不等于授权干净。
- ⚠️ 15 套骨架疑似源自 `jianlli/BigDataView_` 模板集，上游未给独立授权文件，二次授权链未核实。**对外商业交付优先只用模式1**，或换成自有模板。详见 `NOTICE.md`。

## 与相邻能力的关系

| 能力 | 定位 | 何时用 |
|---|---|---|
| 本 skill | 快速出样 / 演示 / 一次性静态汇报大屏 | 领导要看、投屏、U 盘带走，且数据口径不复杂 |
| 自有 Vue3 + ECharts + MySQL 全栈 | 产品级经营分析看板 | 要交互、要下钻、要接库、要长期维护 |
| 自写单文件 ECharts 大屏 | 定制交付（财务经营大屏那条路） | 维度规范明确、要求每个数值可追溯、要避开 AGPL |
| bento 课件 / `course-maker` | 培训内容 | 讲方法论，不是生产工具 |

## 课程 / 教师场景适配

- **能当"数据大屏快速出样"的演示素材**，但不能原样给老师装：链路含 `openpyxl`、CLI、schema、CDN、AGPL 等黑话，与面向教师材料「去技术术语、HTML 带复制按钮」的要求冲突。
- 更值钱的是当 `course-maker` 里「**AI 产物验收标准**」的教学案例：构建成功 ≠ 能看 → 必须实渲截图；宣传口径 ≠ 实测 → 自己量体积和外链；文档 ≠ 源码 → 矛盾时以实跑为准。这组三条判断层规则可脱离本 skill 单独教。
- 若要做教师版，只保留「给一份 Excel → 出一张屏」的黑盒演示，把修复、授权、CLI 全部藏在讲师手册里。

## 相关链接

- [[Skill库 MOC]]
- [[pixel2motion 位图转平滑矢量动效技能]]（同样强调「实渲验收 / 证据链」而非"生成成功"）
- [[经营分析看板模块-看板维度规范]] · [[经营分析看板模块-最终确认结论]]（真实业务口径示例）
- [[搭建自生长知识库]] · [[保存对话并提取可沉淀内容]]
