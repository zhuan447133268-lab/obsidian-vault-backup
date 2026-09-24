---
date: 2026-09-24
source: 用户提供的 GitHub 仓库 https://github.com/songsummer920-dazzle/three-scope-map-skill
url: https://github.com/songsummer920-dazzle/three-scope-map-skill
type: 技能卡
tags: [AI工具, threejs, 3D地图, 中国地图, 地球, 数据可视化, 教师教具, three-scope-map, GPL-3.0, Vue3]
---

# three-scope-map：地球入场 → 中国 3D 下钻地图技能

## 一句话定义

一个 Three.js + Vue3 的三维地图 skill：真实纹理地球（星空 / 大气 / 网格扫描 / 飞线 / 涟漪）→ 点击中国进入**立体挤出地图**，省 → 市 → 区县逐层下钻；中国地图保留南海线框、外 / 内边界、hover 抬升、追光、HUD 底座环、视角保存。

## 它是什么 / 能力清单

- **地球首屏**：真实纹理、星空背景、大气辉光、网格扫描、国际飞线、常态涟漪。
- **中国 3D 地图**：`china.json` 省级 GeoJSON（34 个要素，属性 `name` 如 `浙江省`），逐省建 mesh（地形顶面 + 侧面 + 高亮叠层）、挤出厚度、侧边渐变、地形纹理、外 / 内边界、标签、hover 抬升、飞线、追光 ribbon、HUD 底座环。
- **下钻**：地球点击中国 → GSAP 相机动画进入；省 → 市 → 区县逐层。
- **共享主色一键换肤**（`MAP_THEME_PRIMARY`），地球和所有层级统一变色。默认主色 `#9fc53a`（绿）。
- **南海线框**（`ZhejiangThreeMap` 里的 south-sea inset + 球面虚线）—— 合规关键点，改造时务必保留。

## 技术栈与协议（避坑前置）

- 技术栈：Vue 3 + Three.js + GSAP + Vite。依赖锁死（lockfile）。
- 运行时要求：Node `^20.19 / >=22.12`。
- 作者：**宋夏天 Dazzle**。协议：**GPL-3.0**（强 copyleft + 署名）。**商用 / 再分发必须保留 LICENSE 与作者署名**；若嵌入闭源产品需法律评估。
- 格式：仓库是 **Codex skill**（`cp -R three-scope-map ~/.codex/skills/`），不是开箱即用的 WorkBuddy skill——直接塞 `~/.workbuddy/skills/` 跑不起来，需适配（见下方改造）。

## 与现有资产的关系（定位）

- **互补不重叠**：你已有 `geo-3d-terrain`（`~/.workbuddy/skills/geo-3d-terrain/` —— 单点真实 DEM + Esri 影像地形还原，适合局部真实地形）。`three-scope-map` 是"全国 / 省 / 市 / 区县三维下钻大屏 + 地球入场"，适合宏观尺度与层级钻取。`geo-3d-terrain` 只适合局部，全国尺度做不了（需平面专题图）。两者可并列使用。
- 可作为 `知识点演示培训包` 里"数据分布类"的可选 3D 模板（现有培训包偏 2D / 局部 3D 演示，缺全国数据大屏）。

## 怎么跑通 demo（已实测）

1. **拉仓库**：`git clone --depth 1 https://github.com/songsummer920-dazzle/three-scope-map-skill`（沙箱内若被 kill，用后台跑）。
2. **取模板**：仓库里可用工程是 `three-scope-map/assets/templates/smart-mine-vue/`（标准 Vite+Vue3，`npm run dev` 直接起地球首屏）。复制成独立工程：`cp -R .../smart-mine-vue/. three-scope-demo/`。
3. **装依赖**（managed Node 22.22.2）：
   `C:/Users/dfjq/.workbuddy/binaries/node/versions/22.22.2-3/npm.cmd install --ignore-scripts`
   ⚠️ 必须 `--ignore-scripts`：esbuild 的 postinstall 在校验二进制时会被 managed node.exe 占用报 `EBUSY`；跳过脚本后 esbuild 实际二进制走 `@esbuild/win32-x64` 可选依赖，运行 / 构建均不受影响。
4. **起服务**：`npm run dev` → http://127.0.0.1:5173/（地球首屏）。
5. **验证渲染**：无头 Edge + 软件 WebGL 截图：
   `msedge --headless=new --no-sandbox --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader --virtual-time-budget=30000 --screenshot=out.png <url>`
   ⚠️ 必须 `--use-angle=swiftshader --enable-unsafe-swiftshader`（无 GPU 环境软件渲染 WebGL）；地球入场动画 `uIntroReveal` 约 4.2s 才亮，截图 `virtual-time-budget` 需 ≥ 30s。
6. **构建校验**：`npm run build` 通过；`python scripts/check_three_map_project.py <工程> --strict` 零 blocker / warning（该脚本在仓库 `three-scope-map/scripts/`）。

## 改造为"教师数据地图"原型（核心产出，已跑通）

**动机**：原仓库是开发者模板，对老师帮助≈0（无教学内容、改不了数据、不会用）。差距在 **数据接入 + 零门槛交付 + 教学内容注入**。

**改造了什么**
- **数据注入方案**：每个省在 `z=50` 加一个**独立半透明 data-fill 叠层**（不改原有地形材质），值 → 颜色（低值深绿 `#1f5e2e` → 高值亮黄绿 `#e8ff4f`，线性插值）。数据通过 prop 从 `App.vue → EarthChinaMap → ChinaMap → ZhejiangThreeMap` 一路传入。
- **控制面板**（`App.vue`，玻璃风格）：示例数据下拉 + 应用 / 重置 + 色阶图例 + 最值显示；支持粘贴 CSV（`地区,数值`，模糊匹配 `浙江 / 浙江省 / 浙江省,1200` 等写法到 GeoJSON `name` 属性）。
- **悬停提示**：鼠标悬停省份显示 `浙江省: 6627 万人`（最初尝试 34 省同时显示徽标太挤，已改为交互式 hover tooltip）。
- **可分享链接**：`?data=population&view=china` 自动进入地图并加载指定数据集（兼做无头截图验证入口）。
- 文件：`src/components/map/teacherData.ts`（数据层：数据集定义 / CSV 解析 / 颜色比例尺）、`teacherData` prop 贯穿、`ZhejiangThreeMap` 加 data-fill mesh + hover。

**内置 3 套示例**
- 各省常住人口（万人）
- 某校招生地域分布（示例占位）
- 各省高考报名人数（万人）

**老师怎么直接受益**
- 地理课：人口 / 经济 / 气候等任何"按地区分布的数值"一键可视化。
- 学校行政：招生生源地、就业去向、学情地域分布 → 3D 大屏。
- 培训场景：本身就是"AI / 工具把数据变成可视化"的现成教具。

**验证状态**
- `npm run build`（含 `vue-tsc` 类型检查）通过。
- `check_three_map_project.py --strict` 零 blocker / warning。
- 截图 `china_data2.png` 已确认分省填色 + 图例 + hover 正常（注意：无头截图只验证首屏，中国下钻需真实浏览器点击触发，未做自动化交互截图）。

## 关键事实 / 避坑

- `npm install` 在 managed Node 下 esbuild 报 `EBUSY` → `--ignore-scripts` 绕开（二进制走可选依赖，不影响）。
- 无头 WebGL 必须 `--use-angle=swiftshader --enable-unsafe-swiftshader`，否则黑屏。
- 地球入场动画约 4.2s 才亮，截图要等。
- 默认主题色 `#9fc53a`；换肤改 `MAP_THEME_PRIMARY`。
- **南海线框务必保留**（合规）。
- GPL-3.0 强约束：保留 LICENSE + 作者署名，再分发 / 商用需合规评估。

## 后续方向（未做）

1. 接真实数据源（老师上传 Excel / 在线表格）而非手贴 CSV。
2. 市级 / 区县数据下钻（骨架已支持下钻，缺对应 GeoJSON 数据）。
3. **路线叙事模式**（丝绸之路 / 长征 / 诗人行迹飞线 + 时间轴 + 文案卡）—— 历史 / 语文更优形态。
4. 打包成 WorkBuddy skill，让老师一句话出图。

## 项目地址 & 原型位置

- 仓库：`https://github.com/songsummer920-dazzle/three-scope-map-skill`
- 原型工程：`D:/培训temp/three-scope-demo/`（⚠️ 在"培训temp"临时工作区，长期保存建议迁移到 `01-项目` 或归档）
- 在线预览：http://127.0.0.1:5173/
- 自动示例：`http://127.0.0.1:5173/?data=population&view=china`

## 相关链接

- [[geo-3d-terrain]]（局部真实地形，互补）
- [[知识点演示培训包]]（可收编为数据分布类 3D 模板）
- [[小学教师AI系列课]]（教具来源场景）
- [[Skill库 MOC]]
