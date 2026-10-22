---
date: 2026-10-21
source: OpenFilm 0.2.4 实战跑通（npm 包解压 + 本地渲染）+ Remotion 招生片全量移植
url: https://github.com/openfilm/openfilm
type: 技能卡
tags: [AI工具, 视频生成, OpenFilm, 渲染, CLI, film.html, Studio, 避坑, 招生片, MIT]
---

# OpenFilm 视频技能（本地渲染 + film.html 写法）

## 一句话定义

一套"用纯 HTML 做视频"的本地工作流：agent 写 `film.html` + 一堆 page 网页，一条命令渲染成 MP4；改文案/配色/时长直接改 HTML 或开 Studio 可视化拖改写回。**MIT 全免商用**，无 React 构建链。

## 环境（已实测定版）

- **Chromium 落点**：`D:\dev-cache\ms-playwright\chromium-1228\chrome-win64\chrome.exe`（playwright-core 1.61.1 默认解析此处，**不是** `~/.cache`），用 `PLAYWRIGHT_BROWSERS_PATH=D:/dev-cache/ms-playwright` 指向。
- **openfilm 包**：从 `https://registry.npmmirror.com/openfilm/-/openfilm-0.2.4.tgz` 下载解压（npm 仓库在国内被墙时走 npmmirror），解压目录里有 `bin/openfilm.mjs`、`src/film-doc.mjs`、`src/host.mjs`、`src/timeline.mjs`、`SPEC.md`。
- **依赖**：仅需 `playwright-core@1.61.1`（CLI `npm i --no-save playwright-core@1.61.1` 装到包目录）。
- **ffmpeg**：`C:\Users\dfjq\.workbuddy\binaries\ffmpeg\bin\ffmpeg`（OpenFilm 调用）。

## 渲染命令（定版）

```bash
cd <film.html 所在目录>
PLAYWRIGHT_BROWSERS_PATH=D:/dev-cache/ms-playwright \
  node <openfilm包>/bin/openfilm.mjs render
```

- MP4 渲染完存 film.html 旁边（如 `promo.mp4`）。
- 其它：`openfilm look`（逐帧预览）、`openfilm doctor`（环境自检）、`openfilm open`（起 Studio 编辑器）。
- Studio 在沙箱里起子进程会被 EPERM 拦（非致命），但 `render` 走独立浏览器启动正常。

## film.html 写法要点

- 轨道 = `<section>`，**第一个 `<section>` 在最上层**。叠加 UI（角标/字幕/黑场）要放第一个 section，否则被底层整屏页盖住。
- 片段：`<iframe src="pages/xxx.html" at="0" size="1920x1080" style="left:0;top:0;width:1920px;height:1080px" overrides='[{"fade":[0.4,0.4]}]'></iframe>`，`<audio src="assets/bgm.wav" at="0" volume="0.6"></audio>`。
- page 网页必须暴露 `window.film = { frame(localT){...}, duration, ready, width, height }`，`frame()` 是**纯函数**（同 t 同画面，不累积状态，收到的是 clip 局部时间）。
- 想让 page 自己预览，可在末尾加 `if(!window.filmHost){ /* 自播放 loop */ }`（宿主加载时 `window.filmHost` 存在，自播放不触发）。

## 关键事实 / 避坑（血坑级）

1. **第一个 section 最上层**：字幕/标题/黑场 overlay 必须放第一个 section，否则被整屏主视觉盖死（首次渲染就栽了，调换顺序即好）。
2. **音/视频 `#t=in,out` 不能超文件真实长度**：超了直接渲染报错 `ends past the file's length of X s`。先用 ffprobe 探真实时长：`ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 file.wav`，再写 `#t=0,0.42`（例：sfx_impact.wav 实际 0.42s）。
3. **page 无 duration 当 still 用**：page 必须声明 `window.film.duration`（如 16），否则只能靠 `#t=0,N` 给定长度；有 duration 才能整页长度播放、Studio 才能拖帧。
4. **frame(t) 确定性**：禁止 `let t0=...` 这类在 frame 里累积的写法，否则 Studio 任意拖帧会错乱。
5. **验证渲染是否真的出画面**：抽帧目检比看时长靠谱——`ffmpeg -i promo.mp4 -vf "select=eq(n\,FRAME)" -frames:v 1 f.png`；分段验音用 `ffmpeg -ss T -t LEN -i promo.mp4 -af volumedetect -f null -`，看 `max_volume` 是否非 `-inf`（静音说明音轨没进）。

## 实战案例：Remotion 招生片 → OpenFilm 全量移植（已渲染成功）

- **动机**：验证"Studio 精修闭环是否比改 React 省事"。把 remotion-demo 的 Promo.tsx 五场景（16s@30fps/1920×1080）重做成 film.html + 8 个 page（bg 极光背景 / brand 角标 / fadeout 黑场 + 5 个场景页，DOM/CSS + 本地 `springish()` 复刻原 Remotion 弹簧动画），assets 从 `remotion-demo/build/public` 复制。
- **结果**：`promo.mp4` 渲染成功（16s/1920×1080/h264+AAC，约 60s 渲完）。抽帧验证五场景 + 角标 + 极光背景 + 音轨（max_volume ≈ -3.4dB）+ 结尾黑场全部正确。
- **迁移成本**：一次手写 DOM/CSS 重写 + 复刻弹簧动画（真功夫），但换来的后续微调闭环 = 改 HTML 或开 Studio，零构建、MIT 全免。
- **结论**：一次性宣传片后续微调，OpenFilm 闭环确实比改 React 省事；批量/模板化生成仍选 Remotion。

## 与现有资产的关系（定位）

- 互补不重叠：你已有 `remotion-video-toolkit` skill（React 程序化、serverless 强项）。OpenFilm 补"人能精修 + 商用零授权成本"这一侧。
- 同类"工具实跑并沉淀"先例：`three-scope-map 3D中国地图技能`、`srt-whiteboard-animation 白板动画技能`。

## 项目地址 & 产物位置

- 仓库：`https://github.com/openfilm/openfilm`；文档/桌面版：`https://openfilm.dev`
- 最小示例：`D:/培训temp/openfilm_demo/film/`（film.html + scenes/）
- 招生片重制：`D:/培训temp/openfilm_demo/promo/`（film.html + pages/ + assets/ + promo.mp4）
- 对比清单：`D:/培训temp/openfilm_demo/OpenFilm_vs_Remotion_对比.md`
- openfilm 解压包：`D:/培训temp/openfilm_demo/package/`

## 相关链接

- [[OpenFilm 视频智能体]]（概念 / 协议 / 对比定位）
- [[OpenFilm 重制招生片]]（产出物 + 验证结论）
- [[remotion-video-toolkit 避坑]]（若建了卡则链，否则见 [[OpenFilm 视频智能体]] 对比表）
- [[Skill库 MOC]]
