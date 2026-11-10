---
date: 2026-11-09
source: GitHub `nolangz/pixel2motion` + 本机两次实跑（Google wordmark 动效 / 校徽纯矢量化）
url: https://github.com/nolangz/pixel2motion
type: 技能卡
tags: [AI工具, 动效, SVG, 矢量拟合, 品牌动画, 矢量母版, 徽标, 分层交付, QA证据, MIT, pixel2motion]
---

# pixel2motion：把位图 logo 变成可验收的平滑 SVG 动效

> 本机安装位置：`~/.workbuddy/skills/pixel2motion/`（17 文件 / 212K）

## 一句话定义

一个 AI skill：**位图 logo → 最低复杂度的平滑可编辑 SVG → 带 QA 证据的独立动画 HTML**。它的核心不是"把图动起来"，而是先用原生圆/弧/贝塞尔把图形重新拟合一遍（smoothness gate 是硬门槛，IoU 只作诊断不作及格线），再按 Disney 12 原则编舞，最后用确定性帧捕获证明动画确实落在验过的静态矢量上。

## 三层可迁移能力（定位：最值钱的不是「会动的 logo」）

| 层 | 拿走什么 | 能否脱离引擎单独用 |
|---|---|---|
| 1 · 静态矢量化 | 位图标志 → 最少曲线、可编辑、放大不糊的 SVG + 叠图 / IoU / 平滑度证据 | ✅ 完全不做动画也能用（校徽实战走的就是这条） |
| 2 · 动效配方 | `reveal-patterns.md` 里 6 种入场 / 4 种待机循环 / hover 微交互，加 20/50/30、部件错峰、字面值 easing 两条硬规则 | ✅ 可抄进任意 CSS（Vue 看板加载态、卡片依次入场） |
| 3 · 验收协议 | 先固定静态基准 → `?t=` 确定性定帧 → 要求动态产物精确落回基准（同管线 0 像素差）→ 探针验缓动 → 连续性扫描查 stall+pop | ✅ 整套「防 AI 生成漂移」可搬到课件 / 科研图 / PPT 动画验收 |

> 一句话：**别只看它动起来那一眼，要问它停在谁身上。**
> 若主要做教师培训，它 90% 的价值是教学案例 + 验收方法论，不是日常生产工具；只有真做部门品牌物料 / 纪念册电子版时才回到生产工具角色。

## 它适合 / 不适合什么

- ✅ 适合：几何化品牌标（拉丁字母、圆环、弧线、色块）、logo reveal / 开场 / splash、把截图里的标转成可无限缩放的矢量母版（校徽 / 院徽 / 活动徽标 / 公众号截图小图标）、需要交付"证据"的专业 motion design 场景。
- ⚠️ 不适合：复杂中文标题字形、插画/照片、要零确认一键出片、追求"改字即改动画"的可编辑课件封面。
- ❌ **不能跟 `bento-deck` 封面文字结合**（已核代码）：bento 产物 = 官方壳 HTML + `<script type="application/bento+json">` JSON 块，`T()` 白名单仅 `<b><i><br><code><span>`，`fx` 只有参数位与 `ambient: kenburns`，**没有自定义 CSS / `@keyframes` 通道**；标题一旦矢量化就变成图片，毁掉「数据即内容、收到的人双击就能改」的立身之本；汉字笔画只能退回位图描摹，而 skill 明令「描摹只能当量测辅助，永远不能当终稿」；且 bento 的 SKILL.md 禁止手改 `.bento.html`。唯一验证过的动效注入口是 `ambient_bg()`（SMIL SVG 转 data-URI 当 `image` 插到页最前），只能做**文字之外**的动态视觉层。
  - 真正值得做的结合在**课程层而非引擎层**：把 demo 当 `course-maker` Step 6 样例成品 / 「AI 产物验收标准」判断层素材；或只迁方法论到 kicker、色块、分隔条，标题仍是 HTML 文本。
- ⚠️ 不画坐标轴 / 柱状图 / 统计误差棒：平滑度规则是给圆形弧线标志设计的，科研图走 diagram-design / nsfc-figure。
- ⚠️ 链路偏重：要 headless Chrome 做叠图渲染，Motion QA 还要真实浏览器逐帧截图。不是给零基础老师的课堂演示工具。

## 关键事实（避坑，全部实测过）

1. **`npx skills add` 装不进 WorkBuddy**。该命令来自 Vercel Labs `skills` CLI v1.7.6，支持 77 个 agent，但**列表里没有 WorkBuddy**；只有 `codebuddy`（路径 `~/.codebuddy/skills/`，与 `~/.workbuddy/skills/` 不是一回事）。CLI 也没有 `--path/--dir` 自定义目标目录。原始命令缺 `-a`/`-g`/`-y` 时默认装当前项目且交互式选 agent，非交互 shell 会卡住。
   - 要在 Claude Code 里用：`npx skills add nolangz/pixel2motion --skill pixel2motion -g -a claude-code -y`
   - 通用做法：`git clone --depth 1` 后把 `SKILL.md` + `references/` + `scripts/` 拷进 `~/.workbuddy/skills/<name>/`，剔掉 docs/GIF 和 `.git`（整仓 6.7M → 212K）。
2. **`@keyframes` 里的 easing 必须写死 `cubic-bezier(...)`**。写 `animation-timing-function: var(--token)` 会被 Chromium **静默丢弃并退化成 linear**，不报任何错，肉眼看播放也难发现。Token 只能用在 `animation:` shorthand 的 duration/delay 上。
3. **绝对不要放 infinite 循环动画**。`?static=1` 靠 `animation.finish()` 实现，对无限动画会抛错并 `cancel()` 回初态，直接毁掉 Final Frame Contract。
4. **单时钟、零 `animation-delay`**。`?t=<ms>` 用 Web Animations API 给每个 animation 设 `currentTime`，相位偏移必须写成关键帧百分比，否则时间戳对不上编舞。
5. **Python Playwright 在本机装不上**（2026-11-09）：managed venv pip 撞沙箱代理 502（换 7897 也不通）、`uv --offline` 缺 Pillow 缓存、跨 venv 注入 site-packages 会报 numpy ABI 不兼容。可行解 = **全局 Node Playwright 1.61.1 + 系统 Chrome**（`chromium.launch({channel:"chrome"})`）截 `?t=` 帧，本机 Python 复用 skill 模块做 strip/diff。skill 源码零改动。
6. **IoU 不是主战场**。实测把笔画整体调细 IoU 几乎不涨（0.752→0.760），真正的问题是结构错位（横杠 y 差 2px、字母整体偏 1.5px）。剩下的 `src_only`/`render_only` 是位图与 Chrome SVG 的抗锯齿边缘晕，别过拟合。
7. 仓库 MIT、2611 stars、默认分支 `main`、根目录 `SKILL.md`（frontmatter `name: pixel2motion`）。脚本只依赖 Pillow/numpy/标准库，无外联、无读密钥、无危险删除。
8. **`svg_path_audit.py` 默认只审一条 path**（自动挑最长的），单次跑出「0 警告」是假象。校徽 19 条 path 必须用 `--path-index` 全量审，才查出 `shield-outline-left` 一个 16.7° 真实折角。菱形 / 燕尾 / 尖顶 / 盾形尖底报 90°~158° 折角是设计上就该硬折，不算缺陷——只按「该平滑的曲线」判合格。
9. **分区 IoU 别用「文字区 vs 几何区」含混二分**：弧文字区大半是纯蓝环带，会把数字撑高（实测 `geometry_only 0.715` 反低于 `lettering_only 0.817`，结论完全反过来）。改成按语义区域逐个报（外环带 / 细圆线 / 盾形填充 / 收口 / 绶带 / 三段字形）。
10. **平滑优先于数字**：校徽第三版宁可让整图 IoU 掉 0.005，也要修掉那个真实切线跳变。IoU 是诊断量，不是及格线。
11. `export_claude_videos.mjs` 别碰：硬编码 macOS Chrome 路径与作者自己的 Claude 演示目标，Windows 跑不了；安装时剔掉的 docs/GIF 素材就是给它配套的。

## 本机实跑记录（2026-11-09，两次）

源图：318×138 RGB 白底 Google wordmark 截图（四色 `#3186FF / #FC413D / #FFBE00 / #00AF57`）。成品全在 `D:/03-个人文档/学习空间/pixel2motion-demo/`。

| 项 | 结果 |
|---|---|
| 几何拟合 | 用 PIL 逐色 bbox + ASCII 字符画反推，全原生 `<circle>`/`<path A>`/cubic，零描摹轮廓 |
| IoU | 0.7517 → **0.8073**（`src_only` 719 / `render_only` 844） |
| 路径平滑审计 | 3 段（2 cubic + 1 line），**0 短段警告 / 0 切线跳变** |
| 终帧契约（同管线） | `?static=1` vs `?t=1600` **0 像素差** |
| Easing 生效 | `stroke-dashoffset` 1→0.958→0.748→0.252→0.042→0，明确非线性 |
| 运行时 | Chrome 0 page error |

交付物：`logo_motion.html`(22.7KB 零依赖) / `logo.svg` / `motion.css` / `motion_spec.md` / `outputs/`（overlay 进度条、motion strip、10 帧+静态帧、各项 JSON）/ `capture_frames.cjs` / `qa_report.py`。

编舞：1600ms 单时钟，20/50/30；6 个 400ms draw-on 各错开 80ms（=单个部件时长的 20%），绿色竖条改用 scaleY，收尾整体 scale 1→1.045→0.987→1。

### 实战二：校徽纯矢量化（只走第 1 层，不出动画）

源图：732×615 白底、单色蓝 `#0067A4` 的校徽截图。成品在 `D:/03-个人文档/学习空间/cambridge-seal-vector/`，主交付 `seal.svg` + `compare.html`（源图 / 矢量 / 叠图三栏对照）。

**分层交付策略（可复用的通用配方）**：几何层（双圆环、环带、菱形、1996 绶带、书页弧、盾形）19 条 path 全用原生圆 / 弧 / 贝塞尔、每部件独立 id + `pathLength="1"`；文字层**保留 live `<text>` + `<textPath>`**，双击可改字。全程零描摹轮廓，放大不糊；改主色只需全文替换 `#0067A4`。

| 项 | 结果 |
|---|---|
| 四轮整图 IoU | 0.7487 → 0.7764 → 0.7713 → **0.7748** |
| 盾形纯蓝填充区 | **IoU 1.0000，0 像素差**（几何大面积极准） |
| 外环带 r=215–267 | 0.8819 |
| 曲线类 path 平滑审计 | **0 切线跳变 / 0 短段警告** |
| 对比页运行时 | 4 张图全加载，0 page error |

**三轮修正里最值钱的两条**：① 第一版卡在 0.7487，调笔画没用——真因是**多画了一条源图根本不存在的内细圆**（白送 3680 个多余像素）+ 盾形蓝块一直填到尖点，而源图从 y≈440 就急剧收口；② 宁可掉 0.005 IoU 也修掉 16.7° 折角。

**诚实边界**：中文是系统楷体/宋体近似，不是官方书法体；花体 S/J 用 Times italic 近似，差别最大；1996 也不是原图哥特数字。分区 IoU 0.55–0.84 全落在字形替换，属不可约误差，追下去就是过拟合。这是**可编辑母版，不是像素级复刻**；要精确只能拿学校 VI 官方 AI/EPS 字稿整体替换 `<g id="lettering">`，几何层一行不用动。校徽属学校 VI 资产，对外正式发布须走官方文件。

## 制作流程（复现要点）

1. **读源图**：记尺寸/alpha/前景色/语义部件；先写 motion brief（3 个品牌动效词、使用场景、编舞草图）再碰几何。
2. **复杂度阶梯**：primitives → 组合 → 少量解析弧 → 平滑轮廓 → 描摹（描摹只能当量测辅助，永远不能当最终稿）。每个动画部件独立 id，draw-on 路径带 `pathLength="1"`。
3. **几何 QA**：Chrome 渲染 → 青色叠图 → 记 IoU 与像素差 → 逐轮存 overlay 证据（默认预算 10 轮，收敛或耗尽就选 best-of-run）。
4. **编舞**：读 `references/html-delivery-template.md`，生成 showcase HTML（主舞台 `#logo-root` + 原子动效 + Replay/慢放/调速 + 原则 pill + `?t=`/`?static=1`/`window.__p2mReady` + `prefers-reduced-motion`）。
5. **Motion QA**：按关键时间点确定性截图 → 目检帧条 → easing probe 确认没退化成 linear → 同管线终帧 0 diff（决定性）；跨管线 diff 只是重采样噪声，视觉确认即可。自交路径才需要 ink-delta 连续性扫描。

### 复杂徽标 / 含中文的分层配方（纯矢量化路线）

1. 先做像素级量测：颜色 + 逐色 bbox + 径向扫描求同心圆半径与圆心 + 水平/垂直扫描求轮廓 runs + 放大图目检，别靠目测猜坐标。
2. **几何层**全用原生 `<circle>` / `<path A>` / cubic 拟合，每个语义部件独立 id + `pathLength="1"`（为将来接 draw-on 留口）。
3. **文字层**保留 live `<text>` / `<textPath>`（`startOffset` 控制弧排位置），白色反白直接写 `fill`，绝不描摹字形轮廓。
4. 用 `--path-index` **全量**审路径；分区 IoU 按语义区域报，把「字形替换」明确标为不可约误差，**不追数字**。
5. 交付时附三栏对照页 + 迭代进度条 + 诚实边界说明；若要精确到官方字稿，只替换 `<g id="lettering">`。

## 与相邻技能的区别

| | pixel2motion | srt-whiteboard-animation | OpenFilm | scroll-world |
|---|---|---|---|---|
| 输入 | 位图 logo | SRT 字幕 | 时间轴脚本 `frame(t)` | 品牌故事 |
| 产物 | SVG + 动画 HTML + QA 证据 | 手绘白板动画视频 | 纯 HTML 视频页面 | 滚动 scrub 网页 |
| 硬门槛 | smoothness gate + 终帧契约 | 分镜/线稿/绘制顺序 | 无 | 付费视频生成 |
| 是否实跑 | ✅ 本机 1600ms 全流程 + 0 像素差 | ✅ 作者 30s 实例 | ✅ 招生片重制 | ❌ 仅流程 |

## 做课程 / 推荐给老师的适配性

- **能当教学素材，不能当课堂工具**。它最值钱的是"可验收"这套纪律：叠图证据、easing 探针、终帧一致性、诚实边界——适合做成 `course-maker` 里「AI 产物的验收标准」这类判断层内容，或作为 Step 6 的样例成品。
- 原样给老师会踩雷：链路含 headless Chrome、Playwright、`?t=` 时间戳、IoU 等术语，与面向小学/高校教师材料"去技术黑话、HTML 带复制按钮"的要求冲突。要进课件必须先做三层过滤（可教 / 只做不讲 / 不碰）。
- 商标提醒：Google 及 wordmark 是商标，demo 仅技术验证，不是官方资产。

**两个现成的教学案例**（比讲工具界面抗过时，正好是 `course-maker` 核心原则 7「诚实边界」的教具）：

| 实测现象 | 能教什么 |
|---|---|
| 笔画调细 IoU 只从 0.752 涨到 0.760；改结构错位一步到 0.807 | 别被单一指标牵着走，先找结构性根因 |
| 缓动被 Chromium 静默降级成匀速，肉眼看不出，探针才查得到 | 「看起来对」≠「真的对」，AI 交付物要有证据链 |

**四个落点**：做课（判断层模块，需去黑话三层过滤）/ 课件封面（只迁方法论到 kicker、色块、分隔条，标题仍是 HTML 文本）/ 公众号·小红书·纪念册电子版（开场片头、logo 墙待机）/ Vue 经营看板（只动品牌层，**数据图表本身别动**，会误导读数）。

## 相关链接

- [[Skill库 MOC]]
- [[srt-whiteboard-animation 白板动画技能]] · [[OpenFilm 视频技能]] · [[scroll-world 滚动探索网页技能]]（同属动效/视频类）
- [[course-maker-C端直播课设计方法论]]（判断层模块与样例成品的落点）
- [[搭建自生长知识库]] · [[保存对话并提取可沉淀内容]]
- [[Skill判定标准]]（02_概念库）
