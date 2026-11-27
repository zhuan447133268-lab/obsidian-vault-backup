---
date: 2026-09-21
source: 自建索引
type: MOC
tags: [MOC, Skill库]
---

# Skill库 MOC

> 可沉淀、可复用的 AI 技能 / 工具工作流索引。重复出现三次以上的事，就做成 Skill。

## 技能卡片

- [[scroll-world 滚动探索网页技能]] — 滚动控制视频进度的品牌叙事网页（付费视频生成）
- [[srt-whiteboard-animation 白板动画技能]] — SRT 字幕→手绘白板动画视频（作者已实跑 30s 实例）
- [[three-scope-map 3D中国地图技能]] — 地球入场→中国3D下钻地图（Vue3+Three.js，GPL-3.0），已改造为教师数据地图原型
- [[hanxiaoyu-visual-story-comic 漫画技能]] — 多页连续漫画（卡通/条漫/知识漫画专用，MIT），参考图锁一致性+逐页漂移检查；高校严肃场景不适用
- [[OpenFilm 视频技能]] — 纯 HTML 做视频（film.html + frame(t) + Studio），MIT 全免；已把 Remotion 招生片移植重制并渲染成功
- [[HyperFrames HTML渲视频技能]] — 确定性逐帧寻址渲 MP4（同输入同片子）；官方包 Apache-2.0 未装，本机用机制等价自写 CDP 方案跑通（零 npm 依赖，逐帧 `seek(t)` + JPEG + FFmpeg），15s demo 实测
- [[nsfc-roadmap NSFC 纵向技术路线图]] — 自研；纵向分组技术路线图出印刷级 SVG/PDF + drawio，中文配置改字 + 双击重出全套（智擎杯决赛展板实战沉淀）
- [[pixel2motion 位图转平滑矢量动效技能]] — 位图 logo→平滑 SVG→带 QA 证据的动画 HTML（MIT）；**三层能力**＝静态矢量化 / 动效配方 / 验收协议，前两层可脱离引擎单独用。本机两次实跑：Google wordmark 动效（IoU 0.8073、终帧 0 像素差）、校徽纯矢量化（分层交付：几何全矢量 + 文字保留 live text，盾形填充 IoU 1.0000）。已核实**不能**跟 bento-deck 封面文字结合，只能作课程验收素材而非课堂工具
- [[bigdata-dashboard 可视化大屏技能]] — Excel/JSON→单文件离线 HTML 大屏（15 骨架 + 布局引擎，AGPL-3.0）；2026-11-09 本地修复 5 处后安装：默认模式 CDN 白屏、第三方背景图外链、`#dash-root` 高度塌陷致图表全空、radar 空白图、文档口径矛盾。新增零外链交付自检，双模式实跑 + Chrome 实渲通过；**同日追加 v1.2 视觉重写**（字体 / 配色 / 卡片 / 12+ 类图表 / `showcase.json` 丰富样例），解决「饼图扎堆、不高级」；**再追加 v1.3 真实数据检验**（真实财务 xlsx 走安装版 → 抓出汇总 sheet 与在营明细两个口径打架并统一；新增可配置 `subtitle`、表格行数自适应、`polarBar` 按 max/min>8 自动降级横柱）；11 类图表全部由 xlsx 真实聚合，13 组件 + 6 行数据体检全可见，3/3 产物零外链 PASS；**对外商业交付优先只用模式1**（骨架源自 BigDataView_，授权链未核实）
- [[floorplan 代码库架构地图技能]] — **代码库 → 可交互架构地图**（MIT，零依赖 Node 脚本，可脱离 Claude Code/Codex 直接跑）：扫代码→AI 白话命名→单文件 HTML + Health 检查。已实测实验室准入考试项目：219/219 文件 + 80/80 接口、356 连线，挖出 3 处明文密码 + 4 个超大文件。**不是流程图 skill**；Ask bar 问答依赖 claude/codex CLI，WorkBuddy 里废了，问答走对话即可
- [[gamedev-skills 游戏开发技能合集]] — 80 本游戏开发小抄，按 `snow-ryokan` 手搓 Canvas 项目实况只装 4 本（create-game-assets / game-ui-ux / game-feel / prototype-fast）；44 本引擎说明书对本项目是废纸，`router` 会带错路；含 WorkBuddy 侧必须手动建 Junction 的安装坑
- [[photo-to-3d 照片转交互3D技能]] — **自研开源**（Apache-2.0，`zhuan447133268-lab/photo-to-3D`）：产品照片 → 单文件可交互 3D 演示页（旋转 / 点选零件 / 爆炸 / 线框），八轮生成 + 证据帧 + 六项真实浏览器断言；上游 img2threejs 只做生成，本仓库补交付后半段。**两条路线**：A = "看图手写 spec → 基础体拼装"（生成器**不读像素**、不做神经重建，辐条/连杆/铆钉做不了，只有材质从裁图逐像素提取）；B = **已有 GLB → 焊接 → 分件 → 同一套预览壳与断言**（`build_mesh.sh`，不重建、不上传、无 GPU；`demo/spoked-wheel-mesh.html` 实测 24 辐条 + 24 铆钉 = 51 个可点选零件，`file://` 可开）。B 路线是 2026-11-20 用户第二轮反馈"只是认错，不是变强"之后补的**代码能力**（`7109fd9`，v0.2.0，2026-11-20 已推送）：`mesh_rig.ts` + `render_viewer --mesh-file` + `build_mesh.sh` + 两个可再生成 fixture + traps 28–31（非索引 GLB 要焊接、折角切端面、`spatial-chunk` 不是零件、断言别瞄零件质心）。已知边界：要"照片直接长出网格"仍需 GPU 重建服务；ZCode 从 URL 一键装仍需 `.zcode-plugin/plugin.json` 清单，目前 clone 即用

## 元说明（怎么用这个库）

- [[搭建自生长知识库]]
- [[保存对话并提取可沉淀内容]]
- [[回收站清理]]

## 相关层

- [[四层闭环结构]]（01_原料库 / 02_概念库 / 03_Skill库 / 04_输出库）
