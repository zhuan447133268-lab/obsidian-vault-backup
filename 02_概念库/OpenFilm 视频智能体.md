---
date: 2026-10-21
source: OpenFilm 官方 README/MANUAL/SPEC（GitHub openfilm/openfilm，2026-10 起势 ~1.6k 星）+ 实战移植验证
url: https://github.com/openfilm/openfilm
type: 概念卡
tags: [AI工具, 视频生成, OpenFilm, HTML, film.html, Studio, 视频剪辑, MIT, 对比Remotion]
---

# OpenFilm 视频智能体

## 一句话定义

OpenFilm 是一个开源（MIT）AI 视频智能体：核心主张 **"一个 HTML 文件 + 一个 `frame(t)` 函数 + 一个真剪辑器（Studio）"**——让任意能跑命令的 agent（Claude Code / Codex）把片子写成网页，你再在本地 Studio 里手动改它生成的任何东西。

## 它是什么 / 核心模型

- **一部片子 = 一个 `film.html`**：把"页面（网页）/ 视频 / 图片 / 声音"按轨道剪在一起。轨道 = `<section>`，**第一个 `<section>` 是最上层**（堆叠叠加，首节压顶）。
- **一个镜头 = 一个网页**：每个 page 暴露 `window.film = { frame(t), duration, ready, width, height }`。唯一硬约束：**同样 `t` 必须画出同样画面**（确定性，不累积状态）——否则 Studio 不能任意拖帧。
- **`frame(t)` 收到的是 clip 的局部时间**（localT = t − at），不是影片全局时间。
- **Studio**：本地浏览器剪辑器，可拖/缩放/旋转元素、改文字颜色样式、修剪时间线，改动**写回 film 文件**供 agent 看到——这就是"人肉精修闭环"。
- **CLI**：`openfilm open / look / render / get / skills / update / doctor`。`render` 在 film.html 所在目录跑，MP4 存旁边。
- **渲染引擎**：playwright-core 起 Chromium 无头渲染；host 把 film.html 整体载入浏览器，iframe 的 `src` 被替换为 `data-film-src`，由 timeline 按时间显隐/定位每个 iframe。

## 片段类型与 clip 属性（协议要点）

- 片段：`<iframe>`(page 网页)、`<video>`、`<img>`(still 静态图)、`<audio>`(sound 音轨)。
- clip 属性：`src`（支持 `#t=in,out` 媒体片段，**不能超出文件真实长度**，否则渲染报错）、`id`、`at`（影片起点秒）、`speed`、`volume`、`size`、`style` 里的 `left/top/width/height/rotate`、`class`、`overrides`（JSON；带 `at` 选择器改页面元素；不带 `at` 则改 clip 自身 `fade:[in,out]`）。

## 与 remotion-video-toolkit 对比（定位）

| 维度 | OpenFilm | remotion-video-toolkit |
|---|---|---|
| 技术栈 | 纯 HTML/CSS/JS，无框架 | React 18+ + Remotion + TS 构建链路 |
| 人肉精修闭环 | **Studio** 浏览器真剪辑器，改完写回 film | 无官方时间线编辑器，靠改 React 或外部 NLE |
| 商用授权 | **MIT**（CLI+Studio+桌面端全免） | Remotion 框架**商用需付费 License** ⚠️ |
| 规模化/个性化 | 靠 agent 生成，无原生 serverless 渲染 | **强项**：JSON props 驱动，Lambda/Cloud Run 批量出片 |
| 成熟度 | 2026-10 才起势，生态早期 | 多年沉淀，文档/案例成熟 |
| 上手成本 | 低：agent 懂网页即可 | 中：需懂 React + Remotion API + 构建 |

> 完整逐维对比 + 取舍结论见 `D:/培训temp/openfilm_demo/OpenFilm_vs_Remotion_对比.md`（[[OpenFilm 重制招生片]] 的产出物之一）。

## 给你的取舍（直接结论）

- **选 OpenFilm**：出原型 / 招生片 / 要人能精修 / 怕商用授权 → 用它。
- **选 Remotion**：规模化数据视频 / 服务端批量 / 要成熟动画生态 → 用它。
- 两者不互斥，按活分。本结论已用"把 Remotion 招生片移植到 OpenFilm 并渲染成功"实战验证（见 [[OpenFilm 视频技能]] / [[OpenFilm 重制招生片]]）。

## 关键事实 / 避坑（协议级）

- 第一个 `<section>` 是最上层，叠加元素（字幕/标题）必须放第一个 section，否则被整屏底层页盖住。
- page 必须有 `window.film.duration`，否则只能靠 `#t=0,N` 当 still 用；有 duration 才能按整页长度播放。
- `frame(t)` 必须是纯函数：同样 t → 同样画面，禁止累积状态（否则 Studio 拖帧错乱）。
- 音/视频 `#t=in,out` 必须落在文件真实长度内，超界直接渲染失败（用 ffprobe 探真实时长）。

## 相关链接

- [[OpenFilm 视频技能]]（怎么跑通 + 实战避坑）
- [[OpenFilm 重制招生片]]（产出物 + 验证结论）
- [[three-scope-map 3D中国地图技能]]（同类"工具实跑并沉淀"的先例）
- [[Skill库 MOC]]
