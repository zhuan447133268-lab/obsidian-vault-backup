---
date: 2026-10-21
source: OpenFilm 实战产出（Remotion 招生片移植重制）
type: 输出卡
tags: [AI工具, 视频生成, OpenFilm, 招生片, 交付物, 对比Remotion, MIT]
---

# OpenFilm 重制招生片（产出物 + 验证结论）

## 一句话定义

把原 Remotion 版"教师 AI 素养训练营"招生宣传片，用 OpenFilm（纯 HTML + frame(t) + Studio）重做一版的落地成果。验证目标：**Studio 精修闭环是否真比改 React 省事**。

## 产出物（都在 `D:/培训temp/openfilm_demo/`）

- **`promo/promo.mp4`**：OpenFilm 渲染成品，16s @ 1920×1080 / 30fps，h264 + AAC，约 60s 渲完。
- **`promo/` 工程**：`film.html`（总装，10 个轨道 section）+ `pages/`（bg 极光 / brand 角标 / fadeout 黑场 + 5 个场景页）+ `assets/`（bgm.wav、3 个音效、4 张 UI 截图）。
- **`OpenFilm_vs_Remotion_对比.md`**：逐维对比 + 取舍结论（也见 [[OpenFilm 视频智能体]] 内嵌简表）。
- **`film/` 最小示例**：film.html + scenes/title.html + scenes/caption.html（首跑通的 4s 验证件）。

## 抽帧验证结论（已目检）

| 帧(秒) | 内容 | 状态 |
|---|---|---|
| t=2 | Hook「交给 AI」+ 角标 + 极光 | ✅ |
| t=5 | 三问场景 | ✅ |
| t=8 | 能力场景 + UI 截图 | ✅ |
| t=11 | 案例场景（文献综述界面） | ✅ |
| t=14 | CTA「60 分钟 · 信懂会想用」 | ✅ |
| 末帧 | 淡出至黑场 | ✅ |
| 音轨 | 各段 max_volume ≈ -3.4dB（BGM+音效） | ✅ |

## 最终结论（回答"Studio 闭环 vs 改 React"）

- **OpenFilm 胜在闭环**：一次 DOM/CSS 移植成本（已付）换来的后续 = 改文案/配色/时长直接改 HTML 或开 Studio 拖改写回，**零构建、MIT 全免商用**；渲染 60s 出片。
- **Remotion 仍强在**：程序化组合（spring/interpolate 原语、类型安全、serverless 规模渲染）——批量/模板化生成视频选它。
- 两者不互斥，按活分（见 [[OpenFilm 视频智能体]] 取舍表）。

## 避坑已固化（详见 [[OpenFilm 视频技能]]）

1. 第一个 `<section>` 最上层，overlay 放首节。
2. 音视频 `#t=in,out` 不得超文件真实长度（ffprobe 先探）。
3. page 必须 `window.film.duration`，frame(t) 纯函数确定性。

## 相关链接

- [[OpenFilm 视频智能体]]（概念 / 协议）
- [[OpenFilm 视频技能]]（环境 / 命令 / 写法 / 血坑）
- [[Skill库 MOC]]
